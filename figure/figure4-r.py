"""
Figure 4 (right): Hourly discomfort profiles — top floor vs non-top floor,
weighted by real building counts from the Shenzhen cluster map.

Reads raw EnergyPlus CSVs, computes SET for all hours, aggregates by date and hour
to produce daily profile curves (thin lines = individual days, thick line = mean).

Data source: raw simulation CSVs in input/GeiMingHao_27Degree/
Strategy: Baseline (2020), Fixed (2040/2060).
Scenarios: 2020 Baseline, 2040 RCP 8.5, 2060 RCP 8.5.
"""

import os, sys, re, glob, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("NUMBA_NUM_THREADS", "1")

from Code.core.epw_handler import extract_epw_pressure, get_epw_start_offset
from Code.core.set_calculator import calculate_constrained_rh, compute_set_vectorized
from Code.config.parameters import AIR_VELOCITY, RH_LIMIT, SET_THRESHOLD, NIGHT_HOURS

# Daytime (awake, light residential activity):
#   MET=1.2 — ASHRAE 55, standing relaxed / sedentary in dwelling (70 W/m²)
#   CLO=0.50 — lightweight trousers + short-sleeve shirt (ASHRAE 55-2020 summer)
# Nighttime (sleeping, 22:00-07:00):
#   MET=0.7 — ASHRAE 55, sleeping
#   CLO=0.8 — sleepwear + bedding insulation
MET_DAY   = 1.2; CLO_DAY   = 0.5
MET_NIGHT = 0.7; CLO_NIGHT = 0.8

# ================= Configuration =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SIM_BASE = os.path.join(PROJ, "data", "input data", "GeiMingHao_27Degree", "GeiMingHao_IndoorEnv")
EPW_DIR = os.path.join(PROJ, "data", "input data", "epw_files")
CLUSTER_MAP = os.path.join(PROJ, "data", "other data", "cluster_maps", "cluster_440300_深圳市.csv")
OUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "figure4r_output")

CITY = "shen1zhen4shi4"
BLDG_TYPES = [2, 1, 0]
TYPE_LABELS = {2: "High-rise (Type 2)", 1: "Mid-rise (Type 1)", 0: "Low-rise (Type 0)"}

# (strategy_dir, scenario_subfolder)
SCENARIOS = [
    ("2020", "Baseline_2020", "2020"),
    ("2040", "Fixed_capacity", "2040-rcp8.5"),
    ("2060", "Fixed_capacity", "2060-rcp8.5"),
]

# ---- Plotting ----
FIG_SIZE = (22, 14)
COLOR_TOP = '#931832'
COLOR_NONTOP = '#475894'
SHADOW_COLOR = 'dimgray'
BG_LINE_ALPHA = 0.27
BG_LINE_WIDTH = 0.45
AVG_LINE_WIDTH = 1.73
DPI = 300
HIDE_ALL_TEXT = False


def get_storey_num(col_name):
    m = re.search(r'STOREY\s*_?\s*(\d+)', str(col_name), re.IGNORECASE)
    return int(m.group(1)) if m else -1


def load_building_weights():
    """(LandNum, Cluster) → real building count from cluster map."""
    df = pd.read_csv(CLUSTER_MAP, encoding='utf-8')
    df['landUseTyp'] = df['landUseTyp'].astype(str).str.strip()
    df = df[df['landUseTyp'].str.startswith('Residential', na=False)]
    df['LandNum'] = pd.to_numeric(df['LandNum'], errors='coerce').fillna(-1).astype(int)
    df['Cluster'] = pd.to_numeric(df['Cluster'], errors='coerce').fillna(-1).astype(int)
    return df[df['LandNum'] >= 0].groupby(['LandNum', 'Cluster']).size().to_dict()


def find_epw(keyword):
    sd = os.path.join(EPW_DIR, keyword)
    if not os.path.isdir(sd): sd = EPW_DIR
    m = glob.glob(os.path.join(sd, f"*{CITY}*.epw"))
    if m: return m[0]
    m2 = glob.glob(os.path.join(EPW_DIR, "*", f"*{CITY}*.epw"))
    return m2[0] if m2 else None


def compute_building_set(csv_path, epw_pressure):
    """Compute SET for ALL hours of one building with day/night-specific MET & CLO.
    Nighttime (22:00-07:00): MET=0.7, CLO=0.8 (sleeping + bedding)
    Daytime   (07:00-22:00): MET=1.2, CLO=0.5 (awake, shorts+short-sleeve)"""
    try:
        df = pd.read_csv(csv_path, low_memory=False, encoding='utf-8', engine='c')
    except Exception:
        df = pd.read_csv(csv_path, low_memory=False, encoding='gbk', engine='c')
    if len(df) == 0: return None

    start_idx = get_epw_start_offset(str(df.iloc[0, 0]))
    ml = min(len(df), len(epw_pressure) - start_idx)
    if ml <= 0: return None
    df = df.iloc[:ml].reset_index(drop=True)
    pressure = epw_pressure[start_idx:start_idx + ml]

    ts = df.iloc[:, 0].astype(str).str.strip()
    dates = ts.str.extract(r'(\d{2}/\d{2})')[0]
    hours = ts.str.extract(r'(\d{2}):00:00')[0].astype(int).replace(24, 0)

    # Nighttime mask: 22,23,0,1,...,7
    night_set = {22, 23, 0, 1, 2, 3, 4, 5, 6, 7}
    is_night = hours.isin(night_set).values

    # Filter: only hours with HVAC on AND cooling active (matching 1.12SET.py logic)
    cool_cols = [c for c in df.columns if "COOLING_PERIOD_SCHEDULE" in c]
    hvac_cols = [c for c in df.columns if "HVAC_CONDITIONEDTIME_SCHEDULE" in c]
    if cool_cols and hvac_cols:
        ac_mask = (df[cool_cols[0]] > 0) & (df[hvac_cols[0]] > 0)
        df = df[ac_mask].copy().reset_index(drop=True)
        pressure = pressure[ac_mask.values]
        dates = dates[ac_mask.values].reset_index(drop=True)
        hours = hours[ac_mask.values].reset_index(drop=True)
        is_night = is_night[ac_mask.values]

    temp_cols = [c for c in df.columns if "Zone Air Temperature" in c]
    prefixes = sorted(set(c.split(":Zone Air Temperature")[0] for c in temp_cols),
                      key=lambda p: get_storey_num(p) or 99999)

    out = pd.DataFrame({'Date': dates, 'Hour': hours})
    for prefix in prefixes:
        try:
            col_ta = next(c for c in df.columns if c.startswith(f"{prefix}:") and "Zone Air Temperature" in c)
            col_mrt = next(c for c in df.columns if c.startswith(f"{prefix}:") and "Mean Radiant Temperature" in c)
            col_hr = next(c for c in df.columns if c.startswith(f"{prefix}:") and "Humidity Ratio" in c)
        except StopIteration:
            continue
        tdb = df[col_ta].values.astype(float)
        tr = df[col_mrt].values.astype(float)
        w = df[col_hr].values.astype(float)
        rh = calculate_constrained_rh(tdb, w, pressure, RH_LIMIT)

        # Compute SET with both param sets, then blend by hour
        sv_day = compute_set_vectorized(tdb, tr, AIR_VELOCITY, rh, MET_DAY, CLO_DAY)
        sv_night = compute_set_vectorized(tdb, tr, AIR_VELOCITY, rh, MET_NIGHT, CLO_NIGHT)
        sv = np.where(is_night, sv_night, sv_day)

        sn = get_storey_num(prefix)
        out[f"STOREY_{sn}_SET"] = sv

    set_cols = [c for c in out.columns if c.endswith('_SET')]
    if not set_cols:
        return None
    return out, set_cols


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    weights = load_building_weights()
    print(f"Weights: {len(weights)} (LandNum,Cluster) pairs")

    # ---- Style ----
    plt.rcParams['font.sans-serif'] = ['Arial']
    plt.rcParams['axes.unicode_minus'] = False

    # ---- Compute hourly discomfort per scenario × building type ----
    # Structure: data[era_key][b_type] = DataFrame of (date, hour, top_count, nontop_count)
    data = {}

    for era_key, strategy_dir, sc_keyword in SCENARIOS:
        scenario_dir = os.path.join(SIM_BASE, strategy_dir, CITY, sc_keyword)
        if not os.path.isdir(scenario_dir):
            print(f"  [WARN] Missing: {scenario_dir}")
            continue

        epw_file = find_epw(sc_keyword)
        pressure = extract_epw_pressure(epw_file) if epw_file else np.full(8760, 101325.0)
        print(f"\n{era_key} ({sc_keyword})")

        # Initialize accumulators per building type
        data[era_key] = {bt: [] for bt in BLDG_TYPES}

        csv_files = [f for f in glob.glob(os.path.join(scenario_dir, "*.csv"))
                     if "_SET_Result" not in f and not re.search(r'_dup\d*', os.path.basename(f), re.IGNORECASE)]

        for cf in csv_files:
            bid = os.path.basename(cf).replace('.csv', '')
            m = re.match(r'shen1zhen4shi4_(\d+)_(\d+)_\d+_S0', bid)
            if not m:
                continue
            b_type, b_id = int(m.group(1)), int(m.group(2))
            real_count = weights.get((b_type, b_id), 0)
            if real_count == 0:
                continue

            result = compute_building_set(cf, pressure)
            if result is None:
                continue
            set_df, set_cols = result

            set_cols_sorted = sorted(set_cols, key=get_storey_num)
            top_col = set_cols_sorted[-1]
            nontop_cols = set_cols_sorted[:-1]

            # Discomfort flags weighted by real building count
            set_df['top_disc'] = ((set_df[top_col] > SET_THRESHOLD).fillna(False).astype(int)
                                  * real_count)
            if nontop_cols:
                nontop_max = set_df[nontop_cols].max(axis=1)
                set_df['nontop_disc'] = ((nontop_max > SET_THRESHOLD).fillna(False).astype(int)
                                         * real_count)
            else:
                set_df['nontop_disc'] = 0

            # Aggregate by date+hour
            agg = set_df.groupby(['Date', 'Hour'])[['top_disc', 'nontop_disc']].sum().reset_index()
            data[era_key][b_type].append(agg)

        # Merge all buildings of same type
        for bt in BLDG_TYPES:
            if data[era_key][bt]:
                merged = pd.concat(data[era_key][bt])
                data[era_key][bt] = merged.groupby(['Date', 'Hour']).sum().reset_index()
            else:
                data[era_key][bt] = pd.DataFrame(columns=['Date', 'Hour', 'top_disc', 'nontop_disc'])

    # ================= Plot =================
    print("\nPlotting...")

    time_config = {
        '2020': '2020',
        '2040': '2040 (RCP 8.5)',
        '2060': '2060 (RCP 8.5)',
    }
    x_hours = np.arange(24)
    xticks_h = [0, 5, 11, 17, 23]
    xtick_labels_h = ['1am', '6am', 'Noon', '6pm', 'Midnight']

    shadow_effect = [
        pe.SimpleLineShadow(shadow_color=SHADOW_COLOR, alpha=0.3, offset=(1.5, -1.5)),
        pe.Normal()
    ]

    fig, axes = plt.subplots(nrows=3, ncols=3, figsize=FIG_SIZE, sharex=True, sharey='row')

    for row_idx, bt in enumerate(BLDG_TYPES):
        for col_idx, era_key in enumerate(['2020', '2040', '2060']):
            ax = axes[row_idx, col_idx]
            df = data[era_key][bt]

            if df.empty:
                if not HIDE_ALL_TEXT:
                    ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                            transform=ax.transAxes, fontsize=14)
                ax.set_ylim(bottom=0); ax.set_xlim(0, 23)
                ax.tick_params(labelbottom=False, labelleft=False)
                continue

            # Pivot: (date, hour) → daily profiles
            top_pivot = df.pivot_table(index='Date', columns='Hour',
                                        values='top_disc', aggfunc='sum', fill_value=0)
            nontop_pivot = df.pivot_table(index='Date', columns='Hour',
                                           values='nontop_disc', aggfunc='sum', fill_value=0)

            for full in [top_pivot, nontop_pivot]:
                for h in range(24):
                    if h not in full.columns:
                        full[h] = 0
            top_pivot = top_pivot[range(24)]
            nontop_pivot = nontop_pivot[range(24)]

            # Non-top: daily thin lines + mean thick line
            for _, row in nontop_pivot.iterrows():
                ax.plot(x_hours, row.values, color=COLOR_NONTOP,
                        alpha=BG_LINE_ALPHA, linewidth=BG_LINE_WIDTH, zorder=1)
            avg_nontop = nontop_pivot.mean(axis=0)
            ax.plot(x_hours, avg_nontop.values, color=COLOR_NONTOP,
                    linewidth=AVG_LINE_WIDTH, label='Non-top mean', zorder=10,
                    path_effects=shadow_effect)

            # Top: daily thin lines + mean thick line
            for _, row in top_pivot.iterrows():
                ax.plot(x_hours, row.values, color=COLOR_TOP,
                        alpha=BG_LINE_ALPHA, linewidth=BG_LINE_WIDTH, zorder=2)
            avg_top = top_pivot.mean(axis=0)
            ax.plot(x_hours, avg_top.values, color=COLOR_TOP,
                    linewidth=AVG_LINE_WIDTH, label='Top mean', zorder=11,
                    path_effects=shadow_effect)

            ax.set_ylim(bottom=0)
            ax.grid(axis='y', linestyle='--', alpha=0.5, zorder=0)
            ax.set_xlim(0, 23)
            ax.tick_params(axis='both', which='major', labelsize=14)

            if HIDE_ALL_TEXT:
                ax.tick_params(labelbottom=False, labelleft=False)
            else:
                if row_idx == 0:
                    ax.set_title(time_config[era_key], fontsize=20, fontweight='bold', pad=10)
                if col_idx == 0:
                    ax.set_ylabel(f"{TYPE_LABELS[bt]}\nBuilding Count", fontsize=14,
                                  fontweight='bold', labelpad=10)

            if row_idx == 2:
                ax.set_xticks(xticks_h)
                if not HIDE_ALL_TEXT:
                    ax.set_xticklabels(xtick_labels_h, fontsize=14)
                    if col_idx == 1:
                        ax.set_xlabel('Hour of Day', fontsize=14, fontweight='bold', labelpad=10)
                else:
                    ax.set_xticklabels([])

            if not HIDE_ALL_TEXT:
                ax.legend(loc='upper left', fontsize=14, frameon=True,
                          framealpha=0.9, edgecolor='lightgray')

    plt.subplots_adjust(left=0.06, right=0.98, top=0.90, bottom=0.06,
                        wspace=0.04, hspace=0.08)

    save_path = os.path.join(OUT_DIR, "Discomfort_Hourly_Top_vs_NonTop.png")
    fig.savefig(save_path, dpi=DPI, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] {save_path}")


if __name__ == '__main__':
    main()
