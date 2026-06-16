"""
Figure 3-a: Annual mean outdoor temperature comparison (Guangzhou vs Shenzhen).
Reads EPW files across 7 scenarios, plots grouped bar chart with RCP range error bars.
"""
import os, warnings
import matplotlib.pyplot as plt
import numpy as np

warnings.filterwarnings('ignore', r'All-NaN (slice|axis) encountered')

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
epw_base = os.path.join(PROJECT_ROOT, "input", "epw")

scenarios = [
    '2020',
    '2040-rcp2.6', '2040-rcp4.5', '2040-rcp8.5',
    '2060-rcp2.6', '2060-rcp4.5', '2060-rcp8.5'
]

city_mapping = {
    '440100': 'Guangzhou',
    '440300': 'Shenzhen',
}

def get_epw_annual_avg_temp(filepath):
    """Extract annual mean dry-bulb temperature from an EPW file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        temps = []
        for line in lines[8:]:
            parts = line.strip().split(',')
            if len(parts) > 6:
                try:
                    temps.append(float(parts[6]))
                except ValueError:
                    pass
        return sum(temps) / len(temps) if temps else None
    except Exception:
        return None

# Collect data
data = {city_name: [] for city_name in city_mapping.values()}

print("Reading EPW temperature data...")
for scenario in scenarios:
    folder_path = os.path.join(epw_base, scenario)
    temp_dict = {city_name: None for city_name in city_mapping.values()}

    if os.path.exists(folder_path):
        files_found = 0
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".epw"):
                city_code = filename[:6]
                if city_code in city_mapping:
                    city_name = city_mapping[city_code]
                    filepath = os.path.join(folder_path, filename)
                    temp_dict[city_name] = get_epw_annual_avg_temp(filepath)
                    files_found += 1
        print(f"  {scenario}: {files_found} EPW files matched")
    else:
        print(f"  [WARN] {folder_path} not found")

    for city_name in city_mapping.values():
        data[city_name].append(temp_dict[city_name])

print("Data reading complete.\n")

def safe_array(data_list):
    """Convert list to float array, replacing None with NaN."""
    return np.array([x if x is not None else np.nan for x in data_list], dtype=float)

cities = list(city_mapping.values())
x_cities = np.arange(len(cities))

hist_2020 = safe_array([data[city][0] for city in cities])

# 2040 data across 3 RCP scenarios
temps_2040_26 = safe_array([data[city][1] for city in cities])
temps_2040_45 = safe_array([data[city][2] for city in cities])
temps_2040_85 = safe_array([data[city][3] for city in cities])
avg_2040 = np.nanmean([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
min_2040 = np.nanmin([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
max_2040 = np.nanmax([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
errors_2040_y = np.array([avg_2040 - min_2040, max_2040 - avg_2040])

# 2060 data across 3 RCP scenarios
temps_2060_26 = safe_array([data[city][4] for city in cities])
temps_2060_45 = safe_array([data[city][5] for city in cities])
temps_2060_85 = safe_array([data[city][6] for city in cities])
avg_2060 = np.nanmean([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
min_2060 = np.nanmin([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
max_2060 = np.nanmax([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
errors_2060_y = np.array([avg_2060 - min_2060, max_2060 - avg_2060])

# SCI-style plot
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(8, 6))

width = 0.25
capsize = 4

# Hollow bar style: facecolor='none', bold edges
ax.bar(x_cities - width, hist_2020, width,
       facecolor='none', edgecolor='#72AACE', linewidth=3.5)
ax.bar(x_cities, avg_2040, width,
       facecolor='none', edgecolor='#FDBA6D', linewidth=3.5)
ax.bar(x_cities + width, avg_2060, width,
       facecolor='none', edgecolor='#A70327', linewidth=3.5)

# Error bars for RCP range
ax.errorbar(x_cities, avg_2040, yerr=errors_2040_y, fmt='none',
            ecolor='black', capsize=capsize, elinewidth=1.2)
ax.errorbar(x_cities + width, avg_2060, yerr=errors_2060_y, fmt='none',
            ecolor='black', capsize=capsize, elinewidth=1.2)

# SCI axis style
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.tick_params(axis='both', direction='out', length=5, width=1)

ax.set_ylabel('Annual Average Temperature (C)', fontsize=12, fontweight='bold')
ax.set_xticks(x_cities)
ax.set_xticklabels(cities, fontsize=11)
ax.tick_params(axis='y', labelsize=11)

# Dynamic Y range, floor at 18
valid_data = np.concatenate([hist_2020, avg_2040, avg_2060])
valid_data = valid_data[~np.isnan(valid_data)]
if len(valid_data) > 0:
    ax.set_ylim(18, np.max(valid_data) + 2)

plt.tight_layout()
output_dir = os.path.join(PROJECT_ROOT, "output", "figure3")
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, "Fig3-a_Annual_Temperature_Comparison.png")
plt.savefig(output_path, dpi=600, bbox_inches='tight')
plt.close()
print(f"[OK] {output_path}")
