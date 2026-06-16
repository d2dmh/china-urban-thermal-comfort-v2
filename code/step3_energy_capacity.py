"""
Figure 6 — Step 3: Energy consumption + cooling capacity + coincident peak load
(6 cities × 6 strategies).

Reads indoor environment, energy meter, and capacity table files.
Outputs: energy_capacity_summary.csv + coincident_peak_load.csv
"""

import os, sys, re, glob, time, multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code.config.parameters import MAX_WORKERS

FIGURE6_DIR = os.path.dirname(os.path.abspath(__file__))
INDOOR_ROOT = os.path.join(PROJECT_ROOT, "data", "figure6_data", "GeiMingHao_IndoorEnv")
ENERGY_ROOT = os.path.join(PROJECT_ROOT, "data", "figure6_data", "GeiMingHao_Energy")
CAPACITY_ROOT = os.path.join(PROJECT_ROOT, "data", "figure6_data", "GeiMingHao_Capacity")
CLUSTER_MAP_ROOT = os.path.join(PROJECT_ROOT, "data", "other data", "cluster_maps")
OUTPUT_DIR = os.path.join(FIGURE6_DIR, "output", "energy_capacity")

CITY_LIST = ["bei3jing1shi4", "shang4hai3shi4", "guang3zhou1shi4",
             "shen1zhen4shi4", "wu3han4shi4", "xia4men2shi4"]

CITY_CODE_MAP = {
    "bei3jing1shi4": ("110000", "Beijing"), "shang4hai3shi4": ("310000", "Shanghai"),
    "guang3zhou1shi4": ("440100", "Guangzhou"), "shen1zhen4shi4": ("440300", "Shenzhen"),
    "wu3han4shi4": ("420100", "Wuhan"), "xia4men2shi4": ("350200", "Xiamen"),
}

STRATEGY_DEFS = [
    {"label": "S1 (Baseline_Evening27)",  "d2020": "S1a_2020_Evening27",
     "dfuture": "S1b_Future_FixedCap_Evening27", "cities": CITY_LIST},
    {"label": "S2 (FixedCap_Evening26)",   "d2020": None,
     "dfuture": "S2_Future_FixedCap_Evening26", "cities": CITY_LIST},
    {"label": "S3 (FixedCap_AllDay_32_27)", "d2020": None,
     "dfuture": "S3_Future_FixedCap_AllDay_32_27", "cities": CITY_LIST},
    {"label": "S4 (FixedCap_AllDay_32_26)", "d2020": None,
     "dfuture": "S4_Future_FixedCap_AllDay_32_26", "cities": CITY_LIST},
    {"label": "S5 (AutoSize_AllDay_32_26)", "d2020": None,
     "dfuture": "S5_Future_AutoSize_AllDay_32_26", "cities": CITY_LIST},
    {"label": "S6 (Capacity130_AllDay_32_26)", "d2020": None,
     "dfuture": "S6_Future_Capacity130_AllDay_32_26",
     "cities": ["bei3jing1shi4", "guang3zhou1shi4", "shen1zhen4shi4", "wu3han4shi4", "xia4men2shi4"]},
]

SCENARIO_MAP = {
    "2020": "2020 Baseline", "2040-rcp2.6": "2040 RCP 2.6", "2040-rcp4.5": "2040 RCP 4.5",
    "2040-rcp8.5": "2040 RCP 8.5", "2060-rcp2.6": "2060 RCP 2.6",
    "2060-rcp4.5": "2060 RCP 4.5", "2060-rcp8.5": "2060 RCP 8.5",
}


# ---- Building count lookup ----
def _load_building_counts(city_pinyin):
    """Load (LandNum, Cluster, Fnum) → building count mapping from cluster map."""
    code, chn = CITY_CODE_MAP[city_pinyin]
    cf = os.path.join(CLUSTER_MAP_ROOT, f'cluster_{code}_{chn}.csv')
    if not os.path.exists(cf):
        return {}
    df = None
    for enc in ['utf-8-sig', 'gbk']:
        try:
            df = pd.read_csv(cf, encoding=enc, low_memory=False)
            break
        except Exception:
            pass
    if df is None:
        return {}
    df.columns = df.columns.str.strip()
    df['landUseTyp'] = df['landUseTyp'].astype(str).str.strip()
    df = df[df['landUseTyp'].str.startswith('Residential', na=False)].copy()
    df['LandNum'] = pd.to_numeric(df['LandNum'], errors='coerce').fillna(0).astype(int)
    df['Cluster'] = pd.to_numeric(df['Cluster'], errors='coerce').fillna(0).astype(int)
    df['Fnum'] = pd.to_numeric(df['Fnum'], errors='coerce').fillna(0).astype(int)
    return df.groupby(['LandNum', 'Cluster', 'Fnum']).size().to_dict()


# ---- Single building processing ----
def process_single_building(args):
    building_id, strategy_label, scenario_label, data_dir_name, scenario_folder, city, counts_lookup = args
    try:
        indoor_path = os.path.join(INDOOR_ROOT, data_dir_name, city, scenario_folder, f"{building_id}.csv")
        if not os.path.exists(indoor_path):
            return None

        # Step 1: Effective cooling hours
        df_i = pd.read_csv(indoor_path, low_memory=False, encoding='utf-8', engine='c')
        cool_cols = [c for c in df_i.columns if "COOLING_PERIOD_SCHEDULE" in c]
        hvac_cols = [c for c in df_i.columns if "HVAC_CONDITIONEDTIME_SCHEDULE" in c]
        if not cool_cols or not hvac_cols:
            return None
        eff_mask = (df_i[cool_cols[0]] > 0) & (df_i[hvac_cols[0]] > 0)
        eff_hours = int(eff_mask.sum())
        time_arr = df_i.iloc[:, 0].astype(str).str.strip()

        # Step 2: Net cooling energy
        meter_path = os.path.join(ENERGY_ROOT, data_dir_name, city, scenario_folder,
                                  f"{building_id}-meter.csv")
        cooling_kwh = 0.0
        if os.path.exists(meter_path) and eff_hours > 0:
            df_m = pd.read_csv(meter_path, encoding='utf-8', engine='c')
            f_cols = [c for c in df_m.columns if "Electricity:Facility" in c]
            b_cols = [c for c in df_m.columns if "Electricity:Building" in c]
            if f_cols and b_cols:
                facility = pd.to_numeric(df_m[f_cols[0]], errors='coerce').fillna(0)
                building = pd.to_numeric(df_m[b_cols[0]], errors='coerce').fillna(0)
                m_time = df_m.iloc[:, 0].astype(str).str.strip()
                m_time_idx = {t.strip(): i for i, t in enumerate(m_time)}
                total_j = 0.0
                for i, t in enumerate(time_arr):
                    if eff_mask[i] and t.strip() in m_time_idx:
                        idx = m_time_idx[t.strip()]
                        total_j += (facility[idx] - building[idx])
                cooling_kwh = total_j / 3_600_000

        # Step 3: AC capacity (prefer User-Specified over Design Size)
        cap_path = os.path.join(CAPACITY_ROOT, data_dir_name, city, scenario_folder,
                                f"{building_id}-table.htm")
        storey_caps = {}
        if os.path.exists(cap_path):
            try:
                with open(cap_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                try:
                    with open(cap_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except Exception:
                    content = ""
            if content:
                cs = content.find("Coil:Cooling:DX:SingleSpeed")
                if cs > -1:
                    nc = content.find("<b>Coil:", cs + 30)
                    section = content[cs:(nc if nc > 0 else cs + 3000)]
                    rows_html = re.findall(r'<tr>(.*?)</tr>', section, re.DOTALL)
                    us_idx, ds_idx = None, None
                    for rh in rows_html:
                        cells = re.findall(r'<td[^>]*>(.*?)</td>', rh, re.DOTALL)
                        cells_c = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                        if not cells_c:
                            continue
                        joined = ' '.join(cells_c)
                        if 'Total Cooling Capacity' in joined:
                            for j, c in enumerate(cells_c):
                                if 'User-Specified' in c and 'Gross Rated Total Cooling Capacity' in c:
                                    us_idx = j
                                elif 'Design Size' in c and 'Gross Rated Total Cooling Capacity' in c:
                                    ds_idx = j
                            continue
                        if us_idx is not None or ds_idx is not None:
                            name = cells_c[0]
                            sm = re.search(r'STOREY\s*(\d+)', name, re.IGNORECASE)
                            if sm and "COOLING COIL" in name.upper():
                                sn = int(sm.group(1))
                                cv = 0.0
                                for idx in [us_idx, ds_idx]:
                                    if idx is not None and idx < len(cells_c):
                                        try:
                                            v = float(cells_c[idx])
                                            if v > 0:
                                                cv = v
                                                break
                                        except ValueError:
                                            pass
                                if cv > 0:
                                    storey_caps[sn] = cv

        # Building count lookup
        m = re.search(r'_(\d+)_(\d+)_', building_id)
        if m and counts_lookup:
            ln, cl = int(m.group(1)), int(m.group(2))
            fn = len(storey_caps) if storey_caps else 1
            bld_cnt = counts_lookup.get((ln, cl, fn), 1)
        else:
            bld_cnt = 1

        row = {
            'BuildingID': building_id, 'Strategy': strategy_label,
            'Scenario': scenario_label, 'City': city,
            'EffectiveCoolingHours': eff_hours,
            'CoolingEnergy_kWh': round(cooling_kwh, 4),
            'BuildingCount': bld_cnt,
            'CitywideCoolingEnergy_kWh': round(cooling_kwh * bld_cnt, 4),
        }
        for sn in sorted(storey_caps.keys()):
            row[f'Storey_{sn}_Capacity_W'] = round(storey_caps[sn], 2)
        return row
    except Exception as e:
        print(f"   [ERROR] {building_id}: {e}")
        return None


def build_task_list():
    tasks = []
    for sdef in STRATEGY_DEFS:
        for city in sdef["cities"]:
            counts_lookup = _load_building_counts(city)
            for dk in ["d2020", "dfuture"]:
                dn = sdef.get(dk)
                if not dn:
                    continue
                dp = os.path.join(INDOOR_ROOT, dn, city)
                if not os.path.isdir(dp):
                    continue
                for sf in os.listdir(dp):
                    sp = os.path.join(dp, sf)
                    if not os.path.isdir(sp):
                        continue
                    sl = None
                    for k, v in SCENARIO_MAP.items():
                        if k.lower() in sf.lower():
                            sl = v
                            break
                    if sl is None:
                        continue
                    csvs = glob.glob(os.path.join(sp, "*.csv"))
                    csvs = [f for f in csvs if "_SET_Result" not in f
                            and not re.search(r'_dup\d*', os.path.basename(f), re.IGNORECASE)]
                    for cf in csvs:
                        bid = os.path.basename(cf).replace('.csv', '')
                        tasks.append((bid, sdef["label"], sl, dn, sf, city, counts_lookup))
    return tasks


def build_coincident_peak_table():
    """Nighttime coincident peak load (by city, strategy × scenario)."""
    combos = []
    for sdef in STRATEGY_DEFS:
        for city in sdef["cities"]:
            for dk in ["d2020", "dfuture"]:
                dn = sdef.get(dk)
                if not dn:
                    continue
                dp = os.path.join(INDOOR_ROOT, dn, city)
                if not os.path.isdir(dp):
                    continue
                for sf in os.listdir(dp):
                    sp = os.path.join(dp, sf)
                    if not os.path.isdir(sp):
                        continue
                    sl = None
                    for k, v in SCENARIO_MAP.items():
                        if k.lower() in sf.lower():
                            sl = v
                            break
                    if sl is None:
                        continue
                    combos.append((sdef["label"], sl, dn, sf, city))

    print(f"\n>> Coincident peak: {len(combos)} combos...")
    rows = []
    NIGHT_SET = {22, 23, 24, 1, 2, 3, 4, 5, 6, 7}

    for sl, scene, dn, sf, city in combos:
        meter_dir = os.path.join(ENERGY_ROOT, dn, city, sf)
        if not os.path.isdir(meter_dir):
            continue
        csvs = glob.glob(os.path.join(meter_dir, "*-meter.csv"))
        if not csvs:
            continue

        counts = _load_building_counts(city)
        aggregated = {}

        for cf in csvs:
            bid = os.path.basename(cf).replace('-meter.csv', '')
            m = re.search(r'_(\d+)_(\d+)_', bid)
            # Get floor count from capacity
            cap_path = os.path.join(CAPACITY_ROOT, dn, city, sf, f"{bid}-table.htm")
            fn = 1
            if os.path.exists(cap_path):
                try:
                    with open(cap_path, 'r', encoding='utf-8') as f:
                        fc = f.read()
                    if 'Coil:Cooling:DX:SingleSpeed' in fc:
                        storeys = len(re.findall(r'STOREY\s*(\d+)\s+PTAC\s+COOLING\s+COIL', fc))
                        if storeys > 0:
                            fn = storeys
                except Exception:
                    pass

            if m and counts:
                ln, cl = int(m.group(1)), int(m.group(2))
                cnt = counts.get((ln, cl, fn), 1)
            else:
                cnt = 1

            df = pd.read_csv(cf, encoding='utf-8', engine='c')
            f_cols = [c for c in df.columns if "Electricity:Facility" in c]
            b_cols = [c for c in df.columns if "Electricity:Building" in c]
            if not f_cols or not b_cols:
                continue
            facility = pd.to_numeric(df[f_cols[0]], errors='coerce').fillna(0)
            building = pd.to_numeric(df[b_cols[0]], errors='coerce').fillna(0)
            tstamps = df.iloc[:, 0].astype(str).str.strip()
            for ts, fv, bv in zip(tstamps, facility, building):
                hm = re.search(r'(\d{2}):00:00', ts)
                if hm and int(hm.group(1)) in NIGHT_SET:
                    cooling_j = max(fv - bv, 0)
                    aggregated[ts] = aggregated.get(ts, 0) + cooling_j * cnt

        if aggregated:
            max_j = max(aggregated.values())
            peak_ts = max(aggregated, key=aggregated.get)
            rows.append({
                'City': city, 'Strategy': sl, 'Scenario': scene,
                'NightPeak_kW': round(max_j / 3_600_000, 2), 'PeakTime': peak_ts,
            })

    if rows:
        df_pk = pd.DataFrame(rows)
        op = os.path.join(OUTPUT_DIR, "coincident_peak_load.csv")
        df_pk.to_csv(op, index=False, encoding='utf-8-sig')
        print(f">> Peak table: {op} ({len(df_pk)} rows)")
        return df_pk
    return None


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  Figure 6 — Step 3: Energy + Capacity + Peak Load")
    print(f"{'='*60}")

    print(">> Scanning tasks...")
    tasks = build_task_list()
    print(f"   {len(tasks)} building × strategy × scenario × city combinations")

    if not tasks:
        print("[WARN] No tasks. Exiting.")
        return

    safe_workers = min(MAX_WORKERS, os.cpu_count() or 2)
    print(f">> Processing with {safe_workers} workers...")
    results = []
    done = 0
    start = time.time()

    with ProcessPoolExecutor(max_workers=safe_workers) as executor:
        futures = {executor.submit(process_single_building, t): t for t in tasks}
        for future in as_completed(futures):
            done += 1
            row = future.result()
            if row is not None:
                results.append(row)
            if done % 200 == 0 or done == len(tasks):
                print(f"   Progress: {done}/{len(tasks)}  elapsed {time.time()-start:.1f}s")

    if results:
        df = pd.DataFrame(results)
        cap_cols = sorted([c for c in df.columns if c.startswith('Storey_') and 'Capacity' in c],
                          key=lambda x: int(re.search(r'\d+', x).group()))
        fixed_cols = ['BuildingID', 'Strategy', 'Scenario', 'City', 'BuildingCount',
                      'EffectiveCoolingHours', 'CoolingEnergy_kWh', 'CitywideCoolingEnergy_kWh']
        all_cols = [c for c in fixed_cols + cap_cols if c in df.columns]
        for c in df.columns:
            if c not in all_cols:
                all_cols.append(c)
        df = df[all_cols]
        op = os.path.join(OUTPUT_DIR, "energy_capacity_summary.csv")
        df.to_csv(op, index=False, encoding='utf-8-sig')
        print(f"\n>> Output: {op} ({len(df)} rows × {len(df.columns)} cols")

        for city in CITY_LIST:
            sub = df[df['City'] == city]
            print(f"\n--- {city} ---")
            for st in sub['Strategy'].unique():
                s = sub[sub['Strategy'] == st]
                print(f"  {st[:35]}: {len(s)} records, avg energy={s['CoolingEnergy_kWh'].mean():.0f} kWh")
    else:
        print("[WARN] No results.")

    build_coincident_peak_table()
    print(f"\n>> Step 3 done. Total elapsed {time.time()-start:.1f}s")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
