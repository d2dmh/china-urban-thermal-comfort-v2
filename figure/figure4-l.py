"""
Figure 4 (left): Vertical thermal disparity — per-storey discomfort hours
for three representative Shenzhen building archetypes.

Data source: Step 1 summary_uncomfortable_hours.csv (new pipeline).
Strategy: Fixed (future scenarios), Baseline (2020).
Scenarios: 2020 Baseline, 2040 RCP 8.5, 2060 RCP 8.5.
"""

import os, re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ================= Configuration =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SUMMARY_PATH = os.path.join(PROJECT_ROOT, "input", "pipeline_outputs", "hourly_set",
                            "summary_uncomfortable_hours.csv")
OUT_DIR = os.path.join(PROJECT_ROOT, "output", "figure4")

CITY = "shen1zhen4shi4"
SCENARIOS = ["2020 Baseline", "2040 RCP 8.5", "2060 RCP 8.5"]

BUILDINGS_CONFIG = [
    ("High-rise", "shen1zhen4shi4_2_6_2005_S0"),
    ("Mid-rise",  "shen1zhen4shi4_1_10_2005_S0"),
    ("Low-rise",  "shen1zhen4shi4_0_6_1980_S0"),
]

# ---- Plotting params ----
DPI = 600
FIG_WIDTH = 2.5
STOREY_HEIGHT_FACTOR = 0.12
MIN_FIG_HEIGHT = 3

COLORS = {
    "2020 Baseline": '#4575b4',
    "2040 RCP 8.5":  '#fdae61',
    "2060 RCP 8.5":  '#d73027',
}
MARKERS = {
    "2020 Baseline": 'o',
    "2040 RCP 8.5":  's',
    "2060 RCP 8.5":  '^',
}

FONT_FAMILY = 'serif'
FONT_SERIF = ['Times New Roman', 'DejaVu Serif']
FONT_SIZE_LABEL = 12
FONT_SIZE_TICK = 10
LINE_WIDTH_AXES = 1.0
LINE_WIDTH_DATA = 1.5
MARKER_SIZE = 6

SHOW_LABELS = True


def parse_storey(floor_str):
    m = re.search(r'STOREY_(\d+)', str(floor_str))
    return int(m.group(1)) if m else None


def load_building_data(summary_df, building_id):
    """Extract per-storey discomfort hours for one building across 3 scenarios."""
    bdf = summary_df[
        (summary_df['BuildingID'] == building_id) &
        (summary_df['City'] == CITY) &
        (summary_df['Scenario'].isin(SCENARIOS))
    ].copy()
    bdf['StoreyNum'] = bdf['Floor'].apply(parse_storey)
    bdf = bdf.dropna(subset=['StoreyNum']).sort_values('StoreyNum')

    result = {}
    storeys = sorted(bdf['StoreyNum'].unique())
    for sc in SCENARIOS:
        strategy = "Baseline" if sc == "2020 Baseline" else "Fixed"
        sc_df = bdf[(bdf['Scenario'] == sc) & (bdf['Strategy'] == strategy)]
        sc_df = sc_df.set_index('StoreyNum')
        result[sc] = np.array([sc_df.loc[s, 'UncomfortableHours'] if s in sc_df.index else 0
                               for s in storeys])
    return storeys, result


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- Style ----
    plt.rcParams['font.family'] = FONT_FAMILY
    plt.rcParams['font.serif'] = FONT_SERIF
    plt.rcParams['axes.labelsize'] = FONT_SIZE_LABEL
    plt.rcParams['axes.linewidth'] = LINE_WIDTH_AXES
    plt.rcParams['xtick.labelsize'] = FONT_SIZE_TICK
    plt.rcParams['ytick.labelsize'] = FONT_SIZE_TICK
    plt.rcParams['xtick.direction'] = 'out'
    plt.rcParams['ytick.direction'] = 'out'
    plt.rcParams['xtick.top'] = False
    plt.rcParams['ytick.right'] = False
    plt.rcParams['xtick.major.width'] = LINE_WIDTH_AXES
    plt.rcParams['ytick.major.width'] = LINE_WIDTH_AXES
    plt.rcParams['xtick.major.size'] = 4
    plt.rcParams['ytick.major.size'] = 4

    # ---- Load data ----
    if not os.path.exists(SUMMARY_PATH):
        print(f"[ERROR] Summary CSV not found: {SUMMARY_PATH}")
        print("Run Code/pipeline/step1_compute_set.py first.")
        return

    df = pd.read_csv(SUMMARY_PATH, encoding='utf-8-sig')

    for b_label, building_id in BUILDINGS_CONFIG:
        storeys, sc_data = load_building_data(df, building_id)
        if not storeys:
            print(f"[WARN] {b_label}: no data found")
            continue

        # Compute max X across scenarios
        max_val = 0
        for sc in SCENARIOS:
            v = sc_data.get(sc)
            if v is not None and len(v) > 0:
                max_val = max(max_val, np.max(v))

        fig_height = max(MIN_FIG_HEIGHT, len(storeys) * STOREY_HEIGHT_FACTOR + 1.5)
        fig, ax = plt.subplots(figsize=(FIG_WIDTH, fig_height))

        # Plot scenarios in reverse (2060 first = bottom layer)
        for sc in reversed(SCENARIOS):
            v = sc_data.get(sc)
            if v is None:
                continue
            ax.fill_betweenx(storeys, 0, v, color=COLORS[sc], alpha=0.2)
            ax.plot(v, storeys, color=COLORS[sc], linewidth=LINE_WIDTH_DATA,
                    marker=MARKERS[sc], markersize=MARKER_SIZE)

        # Axes
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.set_xlim(left=-5, right=max_val * 1.05 if max_val > 0 else 10)
        ax.set_ylim(bottom=min(storeys) - 0.5, top=max(storeys) + 0.5)

        max_tick = max(ax.get_xticks())
        ax.set_xticks(np.linspace(0, max_tick, 5))

        if SHOW_LABELS:
            ax.set_xlabel("Thermal Discomfort Hours (h)", fontweight='bold')
            ax.set_ylabel("Storey Level", fontweight='bold')
        else:
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.tick_params(labelbottom=False, labelleft=False)

        ax.grid(True, axis='y', linestyle='--', linewidth=0.5, alpha=0.5)
        plt.tight_layout()

        save_path = os.path.join(OUT_DIR, f"Discomfort_{b_label.replace(' ', '_')}.png")
        fig.patch.set_alpha(0.0)
        ax.patch.set_alpha(0.0)
        fig.savefig(save_path, dpi=DPI, bbox_inches='tight', transparent=True)
        plt.close(fig)
        print(f"[OK] {b_label}: {save_path}")

    print("\n[OK] All figures saved to:", OUT_DIR)


if __name__ == '__main__':
    main()
