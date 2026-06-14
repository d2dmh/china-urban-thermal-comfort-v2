"""
Figure 6 — Step 1: SET computation pipeline (6 cities × 6 strategies).

Data source: data/figure6_data/GeiMingHao_IndoorEnv (download from Zenodo).
Output: hourly SET Excel files + summary CSV + per-capita CSV.
"""

import os
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import sys, re, glob, time, multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code.config.parameters import (
    MET, CLO, AIR_VELOCITY, RH_LIMIT, SET_THRESHOLD,
    NIGHT_HOURS, MAX_WORKERS, SCENARIO_ORDER,
)
from Code.core.epw_handler import extract_epw_pressure, get_epw_start_offset
from Code.core.set_calculator import calculate_constrained_rh, compute_set_vectorized, warm_up_numba
from Code.core.city_matcher import get_storey_number, get_unique_sheet_name, parse_sheet_metadata
from Code.core.excel_exporter import normalize_datetime_column, filter_columns_for_export

FIGURE6_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.join(PROJECT_ROOT, "data", "figure6_data", "GeiMingHao_IndoorEnv")
EPW_ROOT = os.path.join(PROJECT_ROOT, "data", "input data", "epw_files")
POPULATION_ROOT = os.path.join(PROJECT_ROOT, "data", "other data", "cluster_maps")
CLUSTER_MAP_ROOT = os.path.join(PROJECT_ROOT, "data", "other data", "cluster_maps")

SET_OUTPUT_DIR = os.path.join(FIGURE6_DIR, "output", "set_calculations")
PER_CAPITA_DIR = os.path.join(FIGURE6_DIR, "output", "per_capita_hours")
BASELINE_LABEL = "Hybrid (26/27°C)"

# ---- 6 cities ----
CITY_LIST = [
    {"pinyin": "bei3jing1shi4",  "chn": "Beijing",  "code": "110000", "prov": "110000Beijing"},
    {"pinyin": "guang3zhou1shi4", "chn": "Guangzhou", "code": "440100", "prov": "440000Guangdong"},
    {"pinyin": "shang4hai3shi4", "chn": "Shanghai",  "code": "310000", "prov": "310000Shanghai"},
    {"pinyin": "shen1zhen4shi4", "chn": "Shenzhen",  "code": "440300", "prov": "440000Guangdong"},
    {"pinyin": "wu3han4shi4",   "chn": "Wuhan",     "code": "420100", "prov": "420000Hubei"},
    {"pinyin": "xia4men2shi4",  "chn": "Xiamen",    "code": "350200", "prov": "350000Fujian"},
]

# ---- 6 strategies (S6 excludes Shanghai) ----
STRATEGY_DEFS = [
    {"label": "S1 (Baseline_Evening27)",   "d2020": "S1a_2020_Evening27",
     "dfuture": "S1b_Future_FixedCap_Evening27", "all": True},
    {"label": "S2 (FixedCap_Evening26)",    "d2020": None,
     "dfuture": "S2_Future_FixedCap_Evening26", "all": True},
    {"label": "S3 (FixedCap_AllDay_32_27)", "d2020": None,
     "dfuture": "S3_Future_FixedCap_AllDay_32_27", "all": True},
    {"label": "S4 (FixedCap_AllDay_32_26)", "d2020": None,
     "dfuture": "S4_Future_FixedCap_AllDay_32_26", "all": True},
    {"label": "S5 (AutoSize_AllDay_32_26)", "d2020": None,
     "dfuture": "S5_Future_AutoSize_AllDay_32_26", "all": True},
    {"label": "S6 (Capacity130_AllDay_32_26)", "d2020": None,
     "dfuture": "S6_Future_Capacity130_AllDay_32_26", "all": False,
     "exclude": ["shang4hai3shi4"]},
]

SCENARIO_MAP = {
    "2020": "2020 Baseline", "2040-rcp2.6": "2040 RCP 2.6", "2040-rcp4.5": "2040 RCP 4.5",
    "2040-rcp8.5": "2040 RCP 8.5", "2060-rcp2.6": "2060 RCP 2.6",
    "2060-rcp4.5": "2060 RCP 4.5", "2060-rcp8.5": "2060 RCP 8.5",
}
SCENARIO_KEYWORDS = {v: k for k, v in SCENARIO_MAP.items()}


def match_scenario(folder_name):
    fl = folder_name.lower()
    for k, v in SCENARIO_MAP.items():
        if k.lower() in fl:
            return v
    return None


def _find_epw_demo(scenario_keyword, city_pinyin):
    """Find EPW file by pinyin matching, fall back to global search."""
    sd = os.path.join(EPW_ROOT, scenario_keyword)
    if not os.path.isdir(sd):
        sd = EPW_ROOT
    m = glob.glob(os.path.join(sd, f"*{city_pinyin}*.epw"))
    if m:
        return m[0]
    m2 = glob.glob(os.path.join(EPW_ROOT, "*", f"*{city_pinyin}*.epw"))
    return m2[0] if m2 else None


def process_single_building(args):
    csv_file, strategy, city_pinyin, scenario_label, scenario_keyword, epw_pressure = args
    try:
        try:
            df = pd.read_csv(csv_file, low_memory=False, encoding='utf-8', engine='c')
        except Exception:
            df = pd.read_csv(csv_file, low_memory=False, encoding='gbk', engine='c')
        if len(df) == 0 or len(epw_pressure) == 0:
            return None, None, None

        start_idx = get_epw_start_offset(str(df.iloc[0, 0]))
        end_idx = start_idx + len(df)
        pressure = epw_pressure[start_idx:end_idx]
        ml = min(len(df), len(pressure))
        if ml == 0:
            return None, None, None
        df = df.iloc[:ml].reset_index(drop=True)
        pressure = pressure[:ml]

        try:
            hours = df.iloc[:, 0].astype(str).str.strip().str.extract(r'(\d{2}):00:00')[0].astype(int)
        except Exception:
            return None, None, None

        hvac_cols = [c for c in df.columns if "HVAC_CONDITIONEDTIME_SCHEDULE" in c]
        cool_cols = [c for c in df.columns if "COOLING_PERIOD_SCHEDULE" in c]
        sched_mask = df[hvac_cols[0]] > 0 if hvac_cols else pd.Series([True] * len(df))
        if sched_mask.sum() == 0:
            return None, None, None

        df_f = df[sched_mask].copy().reset_index(drop=True)
        pressure_f = pressure[sched_mask.values]
        cooling_mask_f = (df.loc[sched_mask, cool_cols[0]] > 0).values if cool_cols else np.ones(len(df_f), dtype=bool)

        try:
            hours_f = df_f.iloc[:, 0].astype(str).str.strip().str.extract(r'(\d{2}):00:00')[0].astype(int)
        except Exception:
            hours_f = pd.Series([0] * len(df_f))
        night_mask_f = hours_f.isin([h if h != 24 else 0 for h in NIGHT_HOURS]) | hours_f.isin(NIGHT_HOURS)
        night_cooling_mask_f = night_mask_f.values & cooling_mask_f

        temp_cols = [c for c in df_f.columns if "Zone Air Temperature" in c]
        prefixes = sorted(set(c.split(":Zone Air Temperature")[0] for c in temp_cols),
                          key=lambda p: get_storey_number(p) if get_storey_number(p) is not None else 99999)

        out = pd.DataFrame()
        out['Date/Time'] = df_f.iloc[:, 0].values
        out['Outdoor_Pressure_Pa'] = pressure_f
        summary_rows = []
        building_id = os.path.basename(csv_file).replace('.csv', '')
        floor_data = {}

        for prefix in prefixes:
            try:
                col_ta = next(c for c in df_f.columns if c.startswith(f"{prefix}:") and "Zone Air Temperature" in c)
                col_mrt = next(c for c in df_f.columns if c.startswith(f"{prefix}:") and "Mean Radiant Temperature" in c)
                col_hr = next(c for c in df_f.columns if c.startswith(f"{prefix}:") and "Humidity Ratio" in c)
            except StopIteration:
                continue

            tdb = df_f[col_ta].values.astype(float)
            tr = df_f[col_mrt].values.astype(float)
            w = df_f[col_hr].values.astype(float)
            rh = calculate_constrained_rh(tdb, w, pressure_f, RH_LIMIT)
            set_vals = compute_set_vectorized(tdb, tr, AIR_VELOCITY, rh, MET, CLO)

            sn = get_storey_number(prefix)
            nm = f"STOREY_{sn}" if sn is not None else prefix[-10:].replace(" ", "_")
            floor_data[f"{nm}_SET"] = set_vals
            floor_data[f"{nm}_RH"] = rh
            floor_data[f"{nm}_Ta"] = tdb
            floor_data[f"{nm}_Tr"] = tr

            ncs = set_vals[night_cooling_mask_f]
            nt = int(np.sum(night_cooling_mask_f))
            uh = int(np.nansum(ncs > SET_THRESHOLD))
            summary_rows.append({
                'Baseline': BASELINE_LABEL, 'Strategy': strategy, 'City': city_pinyin,
                'Scenario': scenario_label, 'BuildingID': building_id, 'Floor': nm,
                'NightHours': nt, 'UncomfortableHours': uh,
            })

        if not summary_rows:
            return None, None, None
        out = pd.concat([out, pd.DataFrame(floor_data)], axis=1)
        return summary_rows, out, building_id
    except Exception as e:
        print(f"   [ERROR] {os.path.basename(csv_file)}: {e}")
        return None, None, None


def build_task_list_city(city_info):
    cp = city_info["pinyin"]
    tasks = []
    ec = {}
    for sd in STRATEGY_DEFS:
        if not sd["all"] and cp in sd.get("exclude", []):
            continue
        for dk in ["d2020", "dfuture"]:
            dn = sd.get(dk)
            if not dn:
                continue
            dp = os.path.join(DATA_ROOT, dn, cp)
            if not os.path.isdir(dp):
                continue
            for sf in os.listdir(dp):
                sp = os.path.join(dp, sf)
                if not os.path.isdir(sp):
                    continue
                sl = match_scenario(sf)
                if sl is None:
                    continue
                sk = SCENARIO_KEYWORDS.get(sl, "2020")
                ck = (cp, sk)
                if ck not in ec:
                    ef = _find_epw_demo(sk, cp)
                    ec[ck] = extract_epw_pressure(ef) if ef else np.full(8760, 101325.0)
                pr = ec[ck]
                cf = glob.glob(os.path.join(sp, "*.csv"))
                cf = [f for f in cf if "_SET_Result" not in f and not re.search(r'_dup\d*', os.path.basename(f), re.IGNORECASE)]
                for f in cf:
                    tasks.append((f, sd["label"], cp, sl, sk, pr))
    return tasks


def _read_csv_robust(path):
    for enc in ['gbk', 'utf-8-sig', 'utf-8']:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception:
            continue
    raise ValueError(f"Cannot read {path}")


def build_population_lookup(city_info):
    code = city_info['code']
    chn = city_info['chn']
    prov = city_info['prov']
    mf = os.path.join(CLUSTER_MAP_ROOT, f"cluster_{code}_{chn}.csv")
    pf = os.path.join(POPULATION_ROOT, prov, f"T{code}_{chn}_building_pop.csv")
    if not os.path.exists(pf):
        alt = os.path.join(POPULATION_ROOT, prov, f"{code}_{chn}_building_pop_attributes.csv")
        if os.path.exists(alt):
            pf = alt
    if not os.path.exists(mf) or not os.path.exists(pf):
        return None

    dc = _read_csv_robust(mf)
    dp = _read_csv_robust(pf)
    dc.columns = dc.columns.str.strip()
    dp.columns = dp.columns.str.strip()
    if 'landUseTyp' in dc.columns:
        dc['landUseTyp'] = dc['landUseTyp'].astype(str).str.strip()
        dc = dc[dc['landUseTyp'].str.startswith('Residential', na=False)].copy()
    for d in (dc, dp):
        d['BuildingID'] = d['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True)
    mg = pd.merge(dc, dp, on='BuildingID', how='inner')
    fc = next((c for c in ['Fnum', 'Fnum_x', 'Fnum_y'] if c in mg.columns), None)
    if fc is None:
        return None
    mg['Cluster'] = pd.to_numeric(mg['Cluster'], errors='coerce').fillna(0).astype(int)
    mg[fc] = pd.to_numeric(mg[fc], errors='coerce').fillna(0).astype(int)
    mg['popNum_2'] = pd.to_numeric(mg['popNum_2'], errors='coerce').fillna(0)
    gk = ['Cluster', fc]
    if 'LandNum' in mg.columns:
        mg['LandNum'] = pd.to_numeric(mg['LandNum'], errors='coerce').fillna(0).astype(int)
        gk = ['LandNum', 'Cluster', fc]
    lk = mg.groupby(gk)['popNum_2'].sum().reset_index()
    return lk.rename(columns={fc: 'Fnum', 'popNum_2': 'Total_Pop'})


def compute_per_capita(all_summary, city_info):
    df = pd.DataFrame(all_summary)
    cdf = df[df['City'] == city_info['pinyin']]
    if cdf.empty:
        return []
    pl = build_population_lookup(city_info)
    if pl is None:
        return []
    results = []
    for st in df['Strategy'].unique():
        for sc in SCENARIO_ORDER:
            sub = cdf[(cdf['Strategy'] == st) & (cdf['Scenario'] == sc)]
            if sub.empty:
                continue
            sph = 0.0
            stp = 0.0
            for bid, grp in sub.groupby('BuildingID'):
                meta = parse_sheet_metadata(bid)
                if meta is None:
                    continue
                bt, ci = meta
                fn = len(grp)
                if 'LandNum' in pl.columns:
                    mt = pl[(pl['LandNum'] == bt) & (pl['Cluster'] == ci) & (pl['Fnum'] == fn)]
                else:
                    mt = pl[(pl['Cluster'] == ci) & (pl['Fnum'] == fn)]
                if mt.empty:
                    continue
                tp = float(mt['Total_Pop'].values[0])
                if tp <= 0:
                    continue
                apf = tp / fn
                stp += tp
                for _, fr in grp.iterrows():
                    if fr['UncomfortableHours'] > 0:
                        sph += apf * fr['UncomfortableHours']
            hpr = sph / stp if stp > 0 else 0
            results.append({
                'Baseline': BASELINE_LABEL, 'Strategy': st, 'City': city_info['chn'],
                'Scenario': sc, 'Total_Person_Hours': sph, 'Total_Population': stp,
                'Hours_Per_Resident': hpr,
            })
    return results


def process_city(city_info):
    cp = city_info["pinyin"]
    cn = city_info["chn"]
    print(f"\n{'='*60}\n  {cn} ({cp})\n{'='*60}")
    tasks = build_task_list_city(city_info)
    if not tasks:
        return [], []
    print(f"  {len(tasks)} tasks")
    eb = {}
    asm = []
    sw = min(MAX_WORKERS, os.cpu_count() or 2)
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=sw) as ex:
        fs = {ex.submit(process_single_building, t): t for t in tasks}
        done = 0
        for fu in as_completed(fs):
            done += 1
            sr, od, bid = fu.result()
            if sr is None:
                continue
            tsk = fs[fu]
            _, st, ci, sl, _, _ = tsk
            gk = (st, ci, sl)
            eb.setdefault(gk, []).append((bid, od))
            asm.extend(sr)
            if done % 100 == 0 or done == len(tasks):
                print(f"   {done}/{len(tasks)}  {time.time()-t0:.0f}s")

    cd = os.path.join(SET_OUTPUT_DIR, cp)
    os.makedirs(cd, exist_ok=True)
    for (st, ci, sl), blds in eb.items():
        ssl = sl.replace(" ", "_")
        sst = st.replace(" ", "_").replace("(", "").replace(")", "")[:40]
        fn = f"{cn}_{sst}_{ssl}.xlsx"
        try:
            with pd.ExcelWriter(os.path.join(cd, fn), engine='openpyxl') as w:
                used = set()
                for bid, od in blds:
                    od = normalize_datetime_column(od, reference_year=2020)
                    od = filter_columns_for_export(od)
                    sh = get_unique_sheet_name(used, bid)
                    used.add(sh)
                    od.to_excel(w, sheet_name=sh, index=False)
        except Exception as e:
            print(f"   [ERROR] {fn}: {e}")
    pc = compute_per_capita(asm, city_info)
    print(f"   Excel: {len(eb)} files, Per-capita: {len(pc)} rows, elapsed {time.time()-t0:.0f}s")
    return asm, pc


def main():
    os.makedirs(SET_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PER_CAPITA_DIR, exist_ok=True)
    print(">> Warming up Numba...")
    warm_up_numba()
    print(">> Done.\n")
    print(f"{'='*60}\n  6 cities × 6 strategies SET computation\n  Data: {DATA_ROOT}\n{'='*60}")

    acs = []
    acp = []
    for ci in CITY_LIST:
        sr, pc = process_city(ci)
        acs.extend(sr)
        acp.extend(pc)

    if acs:
        df = pd.DataFrame(acs)
        df.to_csv(os.path.join(SET_OUTPUT_DIR, "summary_uncomfortable_hours.csv"),
                  index=False, encoding='utf-8-sig')
        print(f"\n>> Summary: {len(df)} rows")
    if acp:
        dfp = pd.DataFrame(acp)
        dfp.to_csv(os.path.join(PER_CAPITA_DIR, "per_capita_hours_summary.csv"),
                   index=False, encoding='utf-8-sig')
        print(f">> Per-capita: {len(dfp)} rows")
    print("\n>> Step 1 done.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
