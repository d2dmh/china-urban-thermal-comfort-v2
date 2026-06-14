"""
Step 2: Generate two pivot tables from Step 1's CSV output.

Table A: Total discomfort hours cross-comparison (4-row header, 21 data columns = 7 scenarios × 3 strategies)
Table B: Per-capita discomfort hours cross-comparison (rows = City + Scenario, columns = Strategy)

Reads CSV directly (no re-opening of Excel), avoiding redundant computation.
"""

import os
import sys
from collections import defaultdict

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Code.config.paths import get_set_output_dir, get_per_capita_output_dir, get_pivot_output_dir, ensure_output_dirs
from Code.config.parameters import BASELINES, CITY_CONFIGS


def _pinyin_to_en(pinyin):
    """Convert city pinyin to English name."""
    for c in CITY_CONFIGS:
        if c['pinyin'] == pinyin:
            return c['chn_name']
    return pinyin


# ================= Table A: Total discomfort hours cross-comparison =================

SCENARIOS = ['2020 Baseline', '2040 RCP 2.6', '2040 RCP 4.5', '2040 RCP 8.5',
             '2060 RCP 2.6', '2060 RCP 4.5', '2060 RCP 8.5']
STRATEGIES = ['Baseline', 'Expansion', 'Fixed']


def build_pivot_a(baseline):
    """Read summary CSV and generate a 4-row-header pivot table (total discomfort hours),
    with city subtotals and multi-city averages appended."""
    summary_path = os.path.join(get_set_output_dir(baseline), "summary_uncomfortable_hours.csv")
    if not os.path.exists(summary_path):
        print(f"   [ERROR] Summary CSV not found: {summary_path}")
        return None

    df = pd.read_csv(summary_path, encoding='utf-8-sig')
    df['City'] = df['City'].apply(_pinyin_to_en)

    # Collect data
    data = defaultdict(lambda: {'night_hours': None})

    for _, row in df.iterrows():
        key = (row['City'], row['BuildingID'], row['Floor'])
        data[key][(row['Scenario'], row['Strategy'])] = row['UncomfortableHours']
        if data[key]['night_hours'] is None:
            data[key]['night_hours'] = row['NightHours']

    if not data:
        return None

    # Build multi-row header
    h0 = [f'Baseline: {baseline}°C', '', '', '']
    h1 = ['', '', '', 'NightHours']
    h2 = ['', '', '', '']
    h3 = ['City', 'BuildingID', 'Floor', '']

    for sc in SCENARIOS:
        display = sc.replace(' Baseline', '').replace(' ', '-').lower()
        h0.extend([''] * len(STRATEGIES))
        h1.append(display)
        h1.extend([''] * (len(STRATEGIES) - 1))
        h2.extend(STRATEGIES)
        h3.extend([''] * len(STRATEGIES))

    # Build data rows
    rows = []
    sorted_keys = sorted(data.keys(), key=lambda x: (x[0], x[1], x[2]))
    cur_city = None
    cur_building = None

    # Group by city, collect per-city subtotals
    city_totals = defaultdict(lambda: defaultdict(float))
    city_counts = defaultdict(int)

    for city, bid, floor in sorted_keys:
        rd = data[(city, bid, floor)]
        row = [
            city if cur_city != city else '',
            bid if cur_building != bid else '',
            floor,
            rd.get('night_hours', ''),
        ]
        cur_city = city
        cur_building = bid

        for sc in SCENARIOS:
            for st in STRATEGIES:
                val = rd.get((sc, st), 0)
                row.append(val if val != '' else '')
                if isinstance(val, (int, float)):
                    city_totals[city][(sc, st)] += val
        rows.append(row)

    # Insert city subtotal rows and blank separators
    final_rows = []
    prev_city = None
    for row in rows:
        city_name = row[0]
        if city_name and prev_city and prev_city != city_name:
            # Insert subtotal for the previous city
            _append_city_summary(final_rows, prev_city, city_totals[prev_city])
            final_rows.append([''] * len(row))  # blank separator row
        final_rows.append(row)
        prev_city = city_name or prev_city
    # Last city subtotal
    if prev_city:
        _append_city_summary(final_rows, prev_city, city_totals[prev_city])
        final_rows.append([''] * len(final_rows[0]))

    # n-city average
    _append_grand_avg(final_rows, list(city_totals.keys()), city_totals)

    return pd.DataFrame([h0, h1, h2, h3] + final_rows)


def _append_city_summary(rows, city_name, totals):
    """Add a single-city subtotal row (sum of all floors × buildings)."""
    row = [city_name, 'Subtotal', '', '']
    for sc in SCENARIOS:
        for st in STRATEGIES:
            v = totals.get((sc, st), 0)
            row.append(int(v) if v else '')
    rows.append(row)


def _append_grand_avg(rows, city_names, city_totals):
    """Add an n-city average row."""
    n = len(city_names)
    if n == 0:
        return
    label = f'{n}-city average'
    row = [label, '', '', '']
    for sc in SCENARIOS:
        for st in STRATEGIES:
            total = sum(city_totals[c].get((sc, st), 0) for c in city_names)
            row.append(round(total / n, 1) if total else '')
    rows.append(row)


# ================= Table B: Per-capita discomfort hours cross-comparison =================

def build_pivot_b(baseline):
    """Read per-capita CSV and generate a City+Scenario × Strategy pivot table,
    with multi-city averages appended."""
    pc_path = os.path.join(get_per_capita_output_dir(baseline), "per_capita_hours_summary.csv")
    if not os.path.exists(pc_path):
        print(f"   [ERROR] Per-capita CSV not found: {pc_path}")
        return None

    df = pd.read_csv(pc_path, encoding='utf-8-sig')
    df['Label'] = df['City'].str.replace(' City', '') + ' - ' + df['Scenario']

    pivot = df.pivot_table(
        index='Label',
        columns='Strategy',
        values='Hours_Per_Resident',
        aggfunc='first'
    )
    ordered_cols = [s for s in STRATEGIES if s in pivot.columns]
    pivot = pivot[ordered_cols]
    pivot = pivot.round(2)

    # Compute n-city averages (grouped by scenario)
    n_cities = df['City'].nunique()
    avg_rows = []
    for sc in SCENARIOS:
        sc_data = df[df['Scenario'] == sc]
        if sc_data.empty:
            continue
        avg_row = {'Label': f'{n_cities}-city average - {sc}'}
        for st in ordered_cols:
            st_data = sc_data[sc_data['Strategy'] == st]['Hours_Per_Resident']
            avg_row[st] = round(st_data.mean(), 2) if not st_data.empty else ''
        avg_rows.append(avg_row)

    pivot = pivot.reset_index()
    pivot.columns.name = None

    # Append average rows
    if avg_rows:
        pivot = pd.concat([pivot, pd.DataFrame(avg_rows)], ignore_index=True)

    return pivot


# ================= Main flow =================

def process_baseline(baseline):
    pivot_dir = get_pivot_output_dir(baseline)
    os.makedirs(pivot_dir, exist_ok=True)

    print(f"\n{'='*70}")
    print(f"  Step 2: Pivot tables [{baseline}°C]")
    print(f"{'='*70}")

    # Table A
    print(">> Generating Table A: Total discomfort hours cross-comparison...")
    df_a = build_pivot_a(baseline)
    if df_a is not None:
        path_a = os.path.join(pivot_dir, "total_uncomfortable_hours_pivot.xlsx")
        df_a.to_excel(path_a, index=False, header=False)
        print(f"   [OK] {path_a}  ({df_a.shape})")

    # Table B
    print(">> Generating Table B: Per-capita discomfort hours cross-comparison...")
    df_b = build_pivot_b(baseline)
    if df_b is not None:
        path_b = os.path.join(pivot_dir, "per_capita_hours_pivot.xlsx")
        df_b.to_excel(path_b, index=False)
        print(f"   [OK] {path_b}  ({df_b.shape})")


def main():
    ensure_output_dirs()
    for baseline in BASELINES:
        if not os.path.isdir(get_set_output_dir(baseline)):
            print(f"[WARN] [{baseline}°C] Data directory not found, skipping")
            continue
        process_baseline(baseline)
    print("\n>> Step 2 complete.")


if __name__ == "__main__":
    main()
