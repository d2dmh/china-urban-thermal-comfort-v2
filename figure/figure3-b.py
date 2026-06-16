"""
Figure 3-b: Per-capita sleep-period discomfort hours — Guangzhou vs Shenzhen.
Floating-bar chart showing 2040-2060 RCP range with inter-decadal mean markers.
Data: extracted from main pipeline summary_uncomfortable_hours.csv.
"""
import os
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

class CONFIG:
    # ---- Data ----
    scenarios = ['2020', 'RCP 2.6', 'RCP 4.5', 'RCP 8.5']

    city_a_name = 'Guangzhou'
    city_a_2040 = [17.9, 26.2, 41.7, 43.6]
    city_a_2060 = [17.9, 62.1, 65.4, 85.9]

    city_b_name = 'Shenzhen'
    city_b_2040 = [42.8, 70.0, 80.4, 101.6]
    city_b_2060 = [42.8, 113.0, 122.9, 186.2]

    # ---- Colours ----
    city_a_color = '#72AACE'
    city_b_color = '#A70327'
    bar_alpha = 0.7
    mean_line_color = '#222222'

    # ---- Layout ----
    fig_size = (4.5, 5)
    dpi = 600
    bar_width = 0.13
    bar_offset = 0.12
    mean_line_width = 2.4
    mean_line_scale = 1.35

    # ---- Fonts ----
    font_family = 'Arial'
    axes_linewidth = 1.2
    y_label = 'Hours / Resident'
    y_label_size = 14
    x_tick_size = 14
    legend_size = 12

    # ---- Axis ----
    y_min = 0
    y_max = 200
    y_tick_step = 40


plt.rcParams['font.sans-serif'] = [CONFIG.font_family]
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.linewidth'] = CONFIG.axes_linewidth

arr_a_2040 = np.array(CONFIG.city_a_2040)
arr_a_2060 = np.array(CONFIG.city_a_2060)
arr_a_means = (arr_a_2040 + arr_a_2060) / 2

arr_b_2040 = np.array(CONFIG.city_b_2040)
arr_b_2060 = np.array(CONFIG.city_b_2060)
arr_b_means = (arr_b_2040 + arr_b_2060) / 2

fig, ax = plt.subplots(figsize=CONFIG.fig_size, dpi=CONFIG.dpi)
x = np.arange(len(CONFIG.scenarios))

for i in range(len(CONFIG.scenarios)):
    # City A (Guangzhou): floating bar from 2040 to 2060
    ax.bar(x[i] - CONFIG.bar_offset, arr_a_2060[i] - arr_a_2040[i],
           CONFIG.bar_width, bottom=arr_a_2040[i],
           color=CONFIG.city_a_color, edgecolor='none', alpha=CONFIG.bar_alpha, zorder=2)

    # City B (Shenzhen): floating bar from 2040 to 2060
    ax.bar(x[i] + CONFIG.bar_offset, arr_b_2060[i] - arr_b_2040[i],
           CONFIG.bar_width, bottom=arr_b_2040[i],
           color=CONFIG.city_b_color, edgecolor='none', alpha=CONFIG.bar_alpha, zorder=2)

    marker_w = CONFIG.bar_width * CONFIG.mean_line_scale

    # Inter-decadal mean markers
    ax.hlines(arr_a_means[i],
              x[i] - CONFIG.bar_offset - marker_w / 2,
              x[i] - CONFIG.bar_offset + marker_w / 2,
              colors=CONFIG.mean_line_color, linewidth=CONFIG.mean_line_width, zorder=3)

    ax.hlines(arr_b_means[i],
              x[i] + CONFIG.bar_offset - marker_w / 2,
              x[i] + CONFIG.bar_offset + marker_w / 2,
              colors=CONFIG.mean_line_color, linewidth=CONFIG.mean_line_width, zorder=3)

ax.set_ylabel(CONFIG.y_label, fontsize=CONFIG.y_label_size, fontweight='bold', labelpad=10)
ax.set_xticks(x)
ax.set_xticklabels(CONFIG.scenarios, fontsize=CONFIG.x_tick_size, fontweight='bold')
ax.set_ylim(CONFIG.y_min, CONFIG.y_max)
ax.set_yticks(np.arange(CONFIG.y_min, CONFIG.y_max + 1, CONFIG.y_tick_step))

ax.spines['right'].set_visible(False)
ax.spines['top'].set_visible(False)
ax.tick_params(axis='x', direction='out', length=5, width=CONFIG.axes_linewidth, pad=8, bottom=True)
ax.tick_params(axis='y', direction='out', length=5, width=CONFIG.axes_linewidth, left=True)

plt.tight_layout()
output_dir = os.path.join(PROJECT_ROOT, "output", "figure3")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "Fig3-b_Discomfort_Hours_Comparison.png")
plt.savefig(output_path, dpi=CONFIG.dpi, bbox_inches='tight')
plt.close()
print(f"[OK] {output_path}")
