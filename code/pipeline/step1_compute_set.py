"""
Step 1: Scan the three strategy × city × scenario directories and for each
building CSV:
1. Align with EPW atmospheric pressure time axis
2. Filter nighttime + HVAC-enabled hours
3. Vectorized SET calculation per storey
4. Count SET > threshold discomfort hours

Outputs:
- One Excel file per (strategy, city, scenario): each sheet = one building's hourly SET/RH
- One summary CSV: per (strategy, city, scenario, building, storey) discomfort hours
"""

import os
# Must be set first (limit Numba threads)
os.environ.setdefault("NUMBA_NUM_THREADS", "1")

import sys
import re
import glob
import time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

# Add project root to sys.path for submodule imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code.config.paths import (
    get_strategy_dirs, EPW_ROOT, get_set_output_dir, get_per_capita_output_dir,
    POPULATION_ROOT, CLUSTER_MAP_ROOT, ensure_output_dirs,
)
from Code.config.parameters import (
    MET, CLO, AIR_VELOCITY, RH_LIMIT, SET_THRESHOLD,
    NIGHT_HOURS, CITY_CONFIGS, SCENARIOS, SCENARIO_ORDER, MAX_WORKERS, BASELINES,
)
from Code.core.epw_handler import (
    extract_epw_pressure, get_epw_start_offset, find_epw_file,
)
from Code.core.set_calculator import (
    calculate_constrained_rh, compute_set_vectorized, warm_up_numba,
)
from Code.core.city_matcher import get_storey_number, get_unique_sheet_name, parse_sheet_metadata
from Code.core.excel_exporter import (
    normalize_datetime_column, filter_columns_for_export, identify_top_floor
)


# ================= EPW pinyin matching (compatible with old/new file naming) =================

def _find_epw(epw_root, scenario_keyword, city_pinyin, city_epw_keyword):
    """
    Find EPW file: prefer pinyin matching (new naming: {code}_{pinyin}_{scenario}.epw),
    fall back to English keyword matching (old naming).
    """
    scenario_dir = os.path.join(epw_root, scenario_keyword)
    if not os.path.isdir(scenario_dir):
        scenario_dir = epw_root

    # Preferred: pinyin match
    pattern = os.path.join(scenario_dir, f"*{city_pinyin}*.epw")
    matched = glob.glob(pattern)
    if matched:
        return matched[0]

    # Global pinyin search
    pattern2 = os.path.join(epw_root, "*", f"*{city_pinyin}*.epw")
    matched2 = glob.glob(pattern2)
    if matched2:
        return matched2[0]

    # Fallback: original English keyword match
    return find_epw_file(epw_root, scenario_keyword, city_epw_keyword)


# ================= Single building processing (executed in child process) =================

def process_single_building(args):
    """
    Process a single building CSV.

    Returns:
        (summary_rows, hourly_dataframe, sheet_base_name) or (None, None, None) on failure.

        summary_rows: list[dict] — one row per storey with discomfort statistics
        hourly_dataframe: DataFrame — wide-format hourly SET/RH table
        sheet_base_name: base name used as Excel sheet name
    """
    csv_file, strategy, city_pinyin, scenario_label, scenario_keyword, epw_pressure, baseline = args

    try:
        # Read CSV (compatible with utf-8 / gbk)
        try:
            df = pd.read_csv(csv_file, low_memory=False, encoding='utf-8', engine='c')
        except Exception:
            df = pd.read_csv(csv_file, low_memory=False, encoding='gbk', engine='c')

        if len(df) == 0 or len(epw_pressure) == 0:
            return None, None, None

        # ---- Time axis alignment: slice EPW pressure to match CSV start date ----
        start_date_str = str(df.iloc[0, 0])
        start_idx = get_epw_start_offset(start_date_str)
        end_idx = start_idx + len(df)
        pressure = epw_pressure[start_idx:end_idx]

        min_len = min(len(df), len(pressure))
        if min_len == 0:
            return None, None, None
        df = df.iloc[:min_len].reset_index(drop=True)
        pressure = pressure[:min_len]

        # ---- Filter nighttime + HVAC on + cooling period ----
        try:
            hours = df.iloc[:, 0].astype(str).str.strip().str.extract(r'(\d{2}):00:00')[0].astype(int)
        except Exception:
            return None, None, None

        # EnergyPlus: 24:00 means end of day (equivalent to next day 0:00)
        night_mask = hours.isin([h if h != 24 else 0 for h in NIGHT_HOURS]) | hours.isin(NIGHT_HOURS)

        cool_cols = [c for c in df.columns if "COOLING_PERIOD_SCHEDULE" in c]
        hvac_cols = [c for c in df.columns if "HVAC_CONDITIONEDTIME_SCHEDULE" in c]
        sched_mask = pd.Series([True] * len(df))
        if cool_cols and hvac_cols:
            sched_mask = (df[cool_cols[0]] > 0) & (df[hvac_cols[0]] > 0)

        final_mask = night_mask & sched_mask
        if final_mask.sum() == 0:
            return None, None, None

        df_f = df[final_mask].copy().reset_index(drop=True)
        pressure_f = pressure[final_mask.values]

        # ---- Vectorized SET calculation per storey ----
        temp_cols = [c for c in df_f.columns if "Zone Air Temperature" in c]
        prefixes = sorted(set(c.split(":Zone Air Temperature")[0] for c in temp_cols),
                          key=lambda p: get_storey_number(p) or 99999)

        out = pd.DataFrame()
        out['Date/Time'] = df_f.iloc[:, 0].values
        out['Outdoor_Pressure_Pa'] = pressure_f

        summary_rows = []
        building_id = os.path.basename(csv_file).replace('.csv', '')

        # Collect all storey data, then add to DataFrame at once
        floor_data = {}

        for prefix in prefixes:
            try:
                col_ta = next(c for c in df_f.columns
                              if c.startswith(f"{prefix}:") and "Zone Air Temperature" in c)
                col_mrt = next(c for c in df_f.columns
                               if c.startswith(f"{prefix}:") and "Mean Radiant Temperature" in c)
                col_hr = next(c for c in df_f.columns
                              if c.startswith(f"{prefix}:") and "Humidity Ratio" in c)
            except StopIteration:
                continue

            tdb = df_f[col_ta].values.astype(float)
            tr = df_f[col_mrt].values.astype(float)
            w = df_f[col_hr].values.astype(float)

            rh = calculate_constrained_rh(tdb, w, pressure_f, RH_LIMIT)
            set_vals = compute_set_vectorized(tdb, tr, AIR_VELOCITY, rh, MET, CLO)

            storey_num = get_storey_number(prefix)
            simple_name = f"STOREY_{storey_num}" if storey_num is not None else prefix[-10:].replace(" ", "_")

            # Collect data instead of adding immediately (avoids DataFrame fragmentation)
            floor_data[f"{simple_name}_SET"] = set_vals
            floor_data[f"{simple_name}_RH"] = rh
            floor_data[f"{simple_name}_Ta"] = tdb
            floor_data[f"{simple_name}_Tr"] = tr

            # Count nighttime discomfort hours for this storey
            uncomfortable_hours = int(np.nansum(set_vals > SET_THRESHOLD))
            summary_rows.append({
                'Baseline': f"{baseline}°C",
                'Strategy': strategy,
                'City': city_pinyin,
                'Scenario': scenario_label,
                'BuildingID': building_id,
                'Floor': simple_name,
                'NightHours': len(set_vals),
                'UncomfortableHours': uncomfortable_hours,
            })

        if not summary_rows:
            return None, None, None

        # Add all storey data at once
        out = pd.concat([out, pd.DataFrame(floor_data)], axis=1)

        return summary_rows, out, building_id

    except Exception as e:
        print(f"   [ERROR] Failed {os.path.basename(csv_file)}: {e}")
        return None, None, None


# ================= Main flow =================

def build_task_list(baseline):
    """
    Scan the three strategy directories and build a task list of
    (csv_file, strategy, city_pinyin, scenario_label, scenario_keyword,
     epw_pressure, baseline).

    EPW atmospheric pressure data is cached by (city, scenario) for reuse.
    """
    tasks = []
    epw_cache = {}

    strategy_dirs = get_strategy_dirs(baseline)

    for strategy_en, strategy_dir in strategy_dirs.items():
        if not os.path.isdir(strategy_dir):
            print(f"[WARN] Strategy directory not found: {strategy_dir}")
            continue

        for city_folder in os.listdir(strategy_dir):
            city_path = os.path.join(strategy_dir, city_folder)
            if not os.path.isdir(city_path):
                continue

            city_conf = next(
                (c for c in CITY_CONFIGS if c['pinyin'] == city_folder),
                None
            )
            if city_conf is None:
                continue

            for scenario_folder in os.listdir(city_path):
                scenario_path = os.path.join(city_path, scenario_folder)
                if not os.path.isdir(scenario_path):
                    continue

                scenario_label = None
                scenario_keyword = None
                for label, keyword in SCENARIOS.items():
                    if keyword.lower() in scenario_folder.lower():
                        scenario_label = label
                        scenario_keyword = keyword
                        break
                if scenario_label is None:
                    continue

                cache_key = (city_folder, scenario_keyword)
                if cache_key not in epw_cache:
                    epw_file = _find_epw(EPW_ROOT, scenario_keyword,
                                         city_folder, city_conf['epw_keyword'])
                    if epw_file:
                        epw_cache[cache_key] = extract_epw_pressure(epw_file)
                    else:
                        print(f"[WARN] EPW not found: {city_folder}/{scenario_keyword} — using default 101325 Pa")
                        epw_cache[cache_key] = np.full(8760, 101325.0)
                pressure = epw_cache[cache_key]

                csv_files = glob.glob(os.path.join(scenario_path, "*.csv"))
                csv_files = [
                    f for f in csv_files
                    if "_SET_Result" not in f and not re.search(r'_dup\d*', os.path.basename(f), re.IGNORECASE)
                ]

                for csv_file in csv_files:
                    tasks.append((
                        csv_file, strategy_en, city_folder,
                        scenario_label, scenario_keyword, pressure, baseline
                    ))

    return tasks


# ================= Population data loading =================

def _read_csv_robust(path):
    """Try multiple encodings to read a CSV file robustly."""
    for enc in ['gbk', 'utf-8-sig', 'utf-8']:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception:
            continue
    raise ValueError(f"Cannot read {path}")


def build_population_lookup(city_conf):
    """Aggregate population by (LandNum, Cluster, Fnum) triple."""
    pinyin = city_conf['pinyin']
    name_cn = city_conf['name_cn']
    code = city_conf['code']
    prov_folder = city_conf['prov_folder']

    map_file = os.path.join(CLUSTER_MAP_ROOT, f"cluster_{code}_{name_cn}.csv")
    pop_filename = city_conf.get(
        'custom_pop_filename',
        f"T{code}_{name_cn}_building_pop_attributes.csv"
    )
    pop_file = os.path.join(POPULATION_ROOT, prov_folder, pop_filename)

    if not os.path.exists(pop_file):
        alt = os.path.join(POPULATION_ROOT, prov_folder,
                           f"{code}_{name_cn}_building_pop_attributes.csv")
        if os.path.exists(alt):
            pop_file = alt

    if not os.path.exists(map_file) or not os.path.exists(pop_file):
        return None

    df_cluster = _read_csv_robust(map_file)
    df_pop = _read_csv_robust(pop_file)
    df_cluster.columns = df_cluster.columns.str.strip()
    df_pop.columns = df_pop.columns.str.strip()

    if 'landUseTyp' in df_cluster.columns:
        df_cluster['landUseTyp'] = df_cluster['landUseTyp'].astype(str).str.strip()
        df_cluster = df_cluster[df_cluster['landUseTyp'].str.startswith('Residential', na=False)].copy()

    for df in (df_cluster, df_pop):
        df['BuildingID'] = df['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True)

    merged = pd.merge(df_cluster, df_pop, on='BuildingID', how='inner')

    fnum_col = next((c for c in ['Fnum', 'Fnum_x', 'Fnum_y'] if c in merged.columns), None)
    if fnum_col is None:
        return None

    merged['Cluster'] = pd.to_numeric(merged['Cluster'], errors='coerce').fillna(0).astype(int)
    merged[fnum_col] = pd.to_numeric(merged[fnum_col], errors='coerce').fillna(0).astype(int)
    merged['popNum_2'] = pd.to_numeric(merged['popNum_2'], errors='coerce').fillna(0)

    group_keys = ['Cluster', fnum_col]
    if 'LandNum' in merged.columns:
        merged['LandNum'] = pd.to_numeric(merged['LandNum'], errors='coerce').fillna(0).astype(int)
        group_keys = ['LandNum', 'Cluster', fnum_col]

    lookup = (
        merged.groupby(group_keys)['popNum_2']
        .sum()
        .reset_index()
        .rename(columns={fnum_col: 'Fnum', 'popNum_2': 'Total_Pop'})
    )
    return lookup


def compute_per_capita(all_summary, baseline):
    """Compute per-capita discomfort hours from the summary list (no re-reading of Excel)."""
    df = pd.DataFrame(all_summary)
    results = []

    for city_conf in CITY_CONFIGS:
        pinyin = city_conf['pinyin']
        chn_name = city_conf['chn_name']

        city_df = df[df['City'] == pinyin]
        if city_df.empty:
            continue

        pop_lookup = build_population_lookup(city_conf)
        if pop_lookup is None:
            continue

        for strategy in df['Strategy'].unique():
            for scenario_label in SCENARIO_ORDER:
                subset = city_df[(city_df['Strategy'] == strategy) & (city_df['Scenario'] == scenario_label)]
                if subset.empty:
                    continue

                sum_person_hours = 0.0
                sum_total_pop = 0.0

                for building_id, group in subset.groupby('BuildingID'):
                    meta = parse_sheet_metadata(building_id)
                    if meta is None:
                        continue
                    building_type, cluster_id = meta
                    fnum = len(group)

                    if 'LandNum' in pop_lookup.columns:
                        match = pop_lookup[(pop_lookup['LandNum'] == building_type) &
                                          (pop_lookup['Cluster'] == cluster_id) &
                                          (pop_lookup['Fnum'] == fnum)]
                    else:
                        match = pop_lookup[(pop_lookup['Cluster'] == cluster_id) &
                                          (pop_lookup['Fnum'] == fnum)]
                    if match.empty:
                        continue

                    total_pop = float(match['Total_Pop'].values[0])
                    if total_pop <= 0:
                        continue

                    avg_pop_per_floor = total_pop / fnum
                    sum_total_pop += total_pop

                    for _, floor_row in group.iterrows():
                        uh = floor_row['UncomfortableHours']
                        if uh > 0:
                            sum_person_hours += avg_pop_per_floor * uh

                hours_per_resident = sum_person_hours / sum_total_pop if sum_total_pop > 0 else 0
                results.append({
                    'Baseline': f"{baseline}°C",
                    'Strategy': strategy,
                    'City': chn_name,
                    'Scenario': scenario_label,
                    'Total_Person_Hours': sum_person_hours,
                    'Total_Population': sum_total_pop,
                    'Hours_Per_Resident': hours_per_resident,
                })

    return results


def main():
    ensure_output_dirs()
    # Numba warm-up (once is sufficient)
    print(">> Warming up Numba cache in main process...")
    warm_up_numba()
    print(">> Warm-up complete.")

    for baseline in BASELINES:
        set_output_dir = get_set_output_dir(baseline)
        os.makedirs(set_output_dir, exist_ok=True)

        print("\n" + "=" * 70)
        print(f"  Step 1: SET computation + nighttime overheating statistics [{baseline}°C]")
        print(f"  Output directory: {set_output_dir}")
        print("=" * 70)

        print(">> Scanning task list...")
        tasks = build_task_list(baseline)
        print(f"   {len(tasks)} building files found")
        if not tasks:
            print("[WARN] No tasks to execute, skipping.")
            continue

        # Group by (baseline, strategy, city, scenario); each group → one Excel file
        excel_buffers = {}
        all_summary = []
        safe_workers = min(MAX_WORKERS, os.cpu_count() or 2)

        print(f">> Launching {safe_workers} parallel workers...")
        start = time.time()

        with ProcessPoolExecutor(max_workers=safe_workers) as executor:
            futures = {executor.submit(process_single_building, t): t for t in tasks}
            done = 0
            for future in as_completed(futures):
                done += 1
                summary_rows, out_df, building_id = future.result()
                if summary_rows is None:
                    continue
                task = futures[future]
                _, strategy, city, scenario_label, _, _, _ = task
                group_key = (strategy, city, scenario_label)
                excel_buffers.setdefault(group_key, []).append((building_id, out_df))
                all_summary.extend(summary_rows)

                if done % 20 == 0 or done == len(tasks):
                    print(f"   Progress: {done}/{len(tasks)}  elapsed {time.time()-start:.1f}s")

        # Write hourly SET Excel files (new format: flattened directory + time-aligned + column filtered)
        print("\n>> Writing hourly SET Excel files...")
        for (strategy, city, scenario_label), buildings in excel_buffers.items():
            # Look up city English name
            city_en = city
            for city_conf in CITY_CONFIGS:
                if city_conf['pinyin'] == city:
                    city_en = city_conf['chn_name']
                    break

            safe_label = scenario_label.replace(" ", "_")
            filename = f"{city_en}_{baseline}Degree_{strategy}_{safe_label}.xlsx"
            excel_path = os.path.join(set_output_dir, filename)

            try:
                with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                    used = set()
                    for building_id, df in buildings:
                        # Apply time alignment (unified to year 2020)
                        df = normalize_datetime_column(df, reference_year=2020)

                        # Apply column filtering (all SET columns + top-floor environmental vars only)
                        df = filter_columns_for_export(df)

                        # Write sheet
                        sheet_name = get_unique_sheet_name(used, building_id)
                        used.add(sheet_name)
                        df.to_excel(writer, sheet_name=sheet_name, index=False)

                print(f"   [OK] {filename}  ({len(buildings)} sheets)")
            except Exception as e:
                print(f"   [ERROR] Write failed {filename}: {e}")

        # Write summary CSV
        if all_summary:
            summary_df = pd.DataFrame(all_summary)
            summary_path = os.path.join(set_output_dir, "summary_uncomfortable_hours.csv")
            summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')
            print(f"\n>> Summary table: {summary_path}  ({len(summary_df)} rows)")

            # ---- Per-capita discomfort hours ----
            print(">> Computing per-capita discomfort hours...")
            per_capita_rows = compute_per_capita(all_summary, baseline)
            if per_capita_rows:
                per_capita_df = pd.DataFrame(per_capita_rows)
                per_capita_dir = get_per_capita_output_dir(baseline)
                os.makedirs(per_capita_dir, exist_ok=True)
                per_capita_path = os.path.join(per_capita_dir, "per_capita_hours_summary.csv")
                per_capita_df.to_csv(per_capita_path, index=False, encoding='utf-8-sig')
                print(f">> Per-capita summary: {per_capita_path}  ({len(per_capita_df)} rows)")

        print(f"\n>> Step 1 [{baseline}°C] complete. Total elapsed {time.time()-start:.1f}s")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
