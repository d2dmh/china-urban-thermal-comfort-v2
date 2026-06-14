"""
Figure 6 — Step 2: Pivot tables (6 cities × 6 strategies × 7 scenarios).
"""

import os, sys
from collections import defaultdict
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

FIGURE6_DIR = os.path.dirname(os.path.abspath(__file__))
SET_DIR = os.path.join(FIGURE6_DIR, "output", "set_calculations")
PER_CAPITA_DIR = os.path.join(FIGURE6_DIR, "output", "per_capita_hours")
PIVOT_DIR = os.path.join(FIGURE6_DIR, "output", "pivot_tables")

STRATEGIES = [
    "S1 (Baseline_Evening27)", "S2 (FixedCap_Evening26)",
    "S3 (FixedCap_AllDay_32_27)", "S4 (FixedCap_AllDay_32_26)",
    "S5 (AutoSize_AllDay_32_26)", "S6 (Capacity130_AllDay_32_26)",
]
STRAT_SHORT = ["S1", "S2", "S3", "S4", "S5", "S6"]

SCENARIOS = [
    "2020 Baseline", "2040 RCP 2.6", "2040 RCP 4.5", "2040 RCP 8.5",
    "2060 RCP 2.6", "2060 RCP 4.5", "2060 RCP 8.5",
]

CITY_NAME_MAP = {
    'bei3jing1shi4': 'Beijing', 'shang4hai3shi4': 'Shanghai',
    'guang3zhou1shi4': 'Guangzhou', 'shen1zhen4shi4': 'Shenzhen',
    'wu3han4shi4': 'Wuhan', 'xia4men2shi4': 'Xiamen',
}


def build_pivot_a():
    """Table A: Total discomfort hours pivot table."""
    summary_path = os.path.join(SET_DIR, "summary_uncomfortable_hours.csv")
    if not os.path.exists(summary_path):
        print(f"   [ERROR] Not found: {summary_path}")
        return None
    df = pd.read_csv(summary_path, encoding='utf-8-sig')

    # Map city column: handle both pinyin and English
    if df['City'].dropna().iloc[0] in CITY_NAME_MAP:
        df['CityName'] = df['City'].map(CITY_NAME_MAP)
    else:
        df['CityName'] = df['City']

    data = defaultdict(lambda: {'night_hours': None})
    for _, row in df.iterrows():
        key = (row['CityName'], row['BuildingID'], row['Floor'])
        data[key][(row['Scenario'], row['Strategy'])] = row['UncomfortableHours']
        if data[key]['night_hours'] is None:
            data[key]['night_hours'] = row['NightHours']

    if not data:
        return None

    h1 = ['', '', '', '']
    h2 = ['City', 'BuildingID', 'Floor', 'NightHours']
    for sc in SCENARIOS:
        h1.extend([sc] + [''] * (len(STRAT_SHORT) - 1))
        h2.extend(STRAT_SHORT)

    rows = [h1, h2]
    sorted_keys = sorted(data.keys(), key=lambda x: (x[0], x[1], x[2]))
    cur_city = None
    cur_building = None

    for city, bid, floor in sorted_keys:
        rd = data[(city, bid, floor)]
        row = [city if cur_city != city else '', bid if cur_building != bid else '',
               floor, rd.get('night_hours', '')]
        cur_city = city
        cur_building = bid
        for sc in SCENARIOS:
            for st in STRATEGIES:
                val = rd.get((sc, st), '')
                row.append(val if val != '' else '')
        rows.append(row)

    return pd.DataFrame(rows)


def build_pivot_b():
    """Table B: Per-capita discomfort hours pivot table."""
    pc_path = os.path.join(PER_CAPITA_DIR, "per_capita_hours_summary.csv")
    if not os.path.exists(pc_path):
        print(f"   [ERROR] Not found: {pc_path}")
        return None
    df = pd.read_csv(pc_path, encoding='utf-8-sig')
    df['Label'] = df['City'] + ' - ' + df['Scenario']
    pivot = df.pivot_table(index='Label', columns='Strategy',
                           values='Hours_Per_Resident', aggfunc='first')
    ordered = [s for s in STRATEGIES if s in pivot.columns]
    pivot = pivot[ordered].round(2)
    return pivot.reset_index()


def main():
    os.makedirs(PIVOT_DIR, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"  Figure 6 — Step 2: Pivot tables")
    print(f"{'='*60}")

    df_a = build_pivot_a()
    if df_a is not None:
        pa = os.path.join(PIVOT_DIR, "total_uncomfortable_hours_pivot.xlsx")
        df_a.to_excel(pa, index=False, header=False)
        print(f"   [OK] Table A: {pa} ({df_a.shape})")

    df_b = build_pivot_b()
    if df_b is not None:
        pb = os.path.join(PIVOT_DIR, "per_capita_hours_pivot.xlsx")
        df_b.to_excel(pb, index=False)
        print(f"   [OK] Table B: {pb} ({df_b.shape})")

    print(">> Step 2 done.")


if __name__ == "__main__":
    main()
