"""
Figure 6 — Step 4: Compute citywide GW-scale cooling load curves.

Bottom-up area-weighted aggregation: reads per-building meter CSV files and
scales prototype kW loads to citywide GW totals using real building stock
floor-area multipliers from Excel.

Output: pickled per-city cache files consumed by figure6-c.py for plotting.
"""

import os, sys, re, glob, time
import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FIGURE6_DIR = os.path.dirname(os.path.abspath(__file__))
EC_PATH = os.path.join(FIGURE6_DIR, "output", "energy_capacity", "energy_capacity_summary.csv")
EXCEL_DIR = os.path.join(FIGURE6_DIR, "output", "energy_capacity", "building_energy")
ENERGY_ROOT = os.path.join(PROJECT_ROOT, "data", "figure6_data", "GeiMingHao_Energy")
CACHE_DIR = os.path.join(FIGURE6_DIR, "output", "load_curve_cache")

# Only 2060 RCP 8.5 midsummer needed for Figure 6
SCENARIO_F4 = '2060-rcp8.5'

CITIES = [
    ('Beijing',  'Bei3jing1shi4',  '110000'),
    ('Shanghai', 'Shang4hai3shi4',  '310000'),
    ('Guangzhou','Guang3zhou1shi4', '440100'),
    ('Shenzhen', 'Shen1zhen4shi4',  '440300'),
    ('Wuhan',    'Wu3han4shi4',     '420100'),
    ('Xiamen',   'Xia4men2shi4',    '350200'),
]

# Strategy: (label, EnergyPlus directory name, plot color)
F4 = [
    ('S5 (AutoSize)',  'S5_Future_AutoSize_AllDay_32_26',  '#931832'),
    ('S4 (Fix_Day26)', 'S4_Future_FixedCap_AllDay_32_26',  '#D56B52'),
    ('S3 (Fix_Day32)', 'S3_Future_FixedCap_AllDay_32_27',  '#EBB97F'),
    ('S2 (Fix_Eve26)', 'S2_Future_FixedCap_Evening26',     '#CFE6ED'),
    ('S1 (Baseline)',  'S1b_Future_FixedCap_Evening27',    '#475894'),
]


def _preload_area_multipliers():
    """
    Build bottom-up area-weighted multipliers from building stock Excel data.

    Multiplier = total_area_of_all_buildings_in_class / prototype_building_area

    This is the core fix that scales prototype kW loads to citywide GW totals.

    Returns:
        area_maps: dict[pinyin] → dict[(LandNum, Cluster, Fnum)] → multiplier
        fnum_map: dict[BuildingID] → floor count
    """
    area_maps = {}
    fnum_map = {}

    # 1. Parse floor count from energy-capacity summary
    if not os.path.exists(EC_PATH):
        print(f"[WARN] Energy capacity summary not found: {EC_PATH}")
        return area_maps, fnum_map

    ec = pd.read_csv(EC_PATH, encoding='utf-8-sig')
    cap_cols = [c for c in ec.columns if c.startswith('Storey_') and 'Capacity' in c]
    for _, row in ec.iterrows():
        bid = row['BuildingID']
        fn = sum(1 for c in cap_cols if pd.notna(row[c]) and row[c] != '' and float(row[c]) > 0)
        fnum_map[bid] = max(fn, 1)

    # 2. Build area multipliers from real building stock Excel
    for chn, en, pinyin, _ in CITIES:
        file_path = os.path.join(EXCEL_DIR, f"{chn}_building_energy.xlsx")
        if not os.path.exists(file_path):
            print(f"  [WARN] Building energy Excel not found: {file_path}")
            continue

        df = pd.read_excel(file_path, usecols=['LandNum', 'Cluster', 'Fnum_x',
                                                'Total_Area_m2', 'Typical_Area_m2'])

        grouped = df.groupby(['LandNum', 'Cluster', 'Fnum_x']).agg(
            Total_Area_sum=('Total_Area_m2', 'sum'),
            Typical_Area=('Typical_Area_m2', 'first')
        ).reset_index()

        city_map = {}
        for _, row in grouped.iterrows():
            ln, cl, fn = int(row['LandNum']), int(row['Cluster']), int(row['Fnum_x'])
            typ_area = row['Typical_Area']
            tot_area = row['Total_Area_sum']
            # Multiplier = citywide total area / single prototype building area
            if typ_area > 0:
                city_map[(ln, cl, fn)] = tot_area / typ_area
            else:
                city_map[(ln, cl, fn)] = 0

        area_maps[pinyin.lower()] = city_map
        print(f"  [OK] {en}: {len(city_map)} building classes loaded")

    return area_maps, fnum_map


def compute_city_curves(pinyin, area_maps, fnum_map):
    """
    Compute all citywide GW load curves for one city across all dates and strategies.

    For each building's meter CSV:
      - Extract net cooling power (Facility − Building) in kW
      - Multiply by area-based scaling factor → citywide kW
      - Sum across all buildings → citywide total per timestamp

    Returns:
        dict: {date_key (MM/DD): {strategy_label: np.array(24) in GW}}
    """
    multipliers = area_maps.get(pinyin.lower(), {})
    all_curves = {}

    for label, dirname, color in F4:
        meter_dir = os.path.join(ENERGY_ROOT, dirname, pinyin, SCENARIO_F4)
        if not os.path.isdir(meter_dir):
            print(f"    [WARN] Meter dir not found: {meter_dir}")
            continue

        csv_files = glob.glob(os.path.join(meter_dir, '*-meter.csv'))
        n_processed = 0

        for cf in csv_files:
            bid = os.path.basename(cf).replace('-meter.csv', '')
            m = re.search(r'_(\d+)_(\d+)_', bid)
            multiplier = 0
            if m:
                ln, cl = int(m.group(1)), int(m.group(2))
                multiplier = multipliers.get((ln, cl, fnum_map.get(bid, 1)), 0)

            if multiplier == 0:
                continue

            try:
                dfm = pd.read_csv(cf, encoding='utf-8', engine='c')
            except Exception:
                continue

            facility = pd.to_numeric(dfm.iloc[:, 1], errors='coerce').fillna(0)
            build_pow = pd.to_numeric(dfm.iloc[:, 2], errors='coerce').fillna(0)
            # Net cooling power in kW (J/s ÷ 3.6e6 = J → kWh conversion, but we keep kW)
            power_kw = (facility - build_pow).clip(lower=0) / 3.6e6

            dates = dfm.iloc[:, 0].astype(str).str.strip().str[:5]
            hrs = dfm.iloc[:, 0].astype(str).str.strip().str.extract(r'(\d{2}):')[0].astype(int)
            hrs = hrs.replace(24, 0)  # EnergyPlus 24:00 → 0:00

            for dd in dates.unique():
                mask = dates == dd
                if mask.sum() == 24:
                    idx = np.argsort(hrs[mask].values)
                    # Scale: prototype kW × area multiplier → citywide kW
                    curve_kw = power_kw[mask].values[idx] * multiplier
                    if dd not in all_curves:
                        all_curves[dd] = {}
                    all_curves[dd][label] = all_curves[dd].get(label, np.zeros(24)) + curve_kw

            n_processed += 1

        print(f"    {label}: {n_processed} buildings processed")

    # Convert citywide kW → GW, apply timezone offset correction
    for dd in all_curves:
        for l in all_curves[dd]:
            all_curves[dd][l] = np.roll(all_curves[dd][l] / 1e6, -1)

    return all_curves


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Figure 6 — Step 4: Citywide GW Load Curve Computation")
    print(f"  Scenario: {SCENARIO_F4}")
    print(f"  Cache dir: {CACHE_DIR}")
    print(f"{'='*60}")

    print("\n>> Building area multipliers from Excel stock data...")
    area_maps, fnum_map = _preload_area_multipliers()
    print(f"   {len(area_maps)} cities loaded")

    for chn, en, pinyin, _ in CITIES:
        pinyin_lower = pinyin.lower()
        if pinyin_lower not in area_maps:
            print(f"\n  [SKIP] {en}: no area multiplier data")
            continue

        cache_file = os.path.join(CACHE_DIR, f'{pinyin_lower}_curves.pkl')
        if os.path.exists(cache_file):
            print(f"\n  [CACHE] {en}: already cached, skipping")
            continue

        print(f"\n  Computing {en} ({pinyin})...")
        t0 = time.time()
        all_curves = compute_city_curves(pinyin, area_maps, fnum_map)
        pd.to_pickle(all_curves, cache_file)
        print(f"  [OK] {en}: {len(all_curves)} dates cached in {time.time()-t0:.1f}s")

    print(f"\n>> Step 4 done. Load curve cache ready for figure6-c.py.")


if __name__ == "__main__":
    main()
