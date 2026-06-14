import os
import matplotlib.pyplot as plt
import numpy as np
import warnings

# 忽略因为数据缺失（全为 NaN）时 numpy 报出的警告
warnings.filterwarnings('ignore', r'All-NaN (slice|axis) encountered')

# 1. 设置基础路径和参数
base_dir = r"C:\Users\31080\Desktop\zhongzi1"

scenarios = [
    '2020',
    '2040-rcp2.6', '2040-rcp4.5', '2040-rcp8.5',
    '2060-rcp2.6', '2060-rcp4.5', '2060-rcp8.5'
]

# 仅保留广州和深圳
city_mapping = {
    '440100': '广州',
    '440300': '深圳',
}

# 2. 读取 EPW 文件计算年平均温度
def get_epw_annual_avg_temp(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        temps = []
        for line in lines[8:]:  # EPW 数据通常从第9行开始
            parts = line.strip().split(',')
            if len(parts) > 6:
                try:
                    temps.append(float(parts[6]))  # 第7列为干球温度
                except ValueError:
                    pass # 忽略无法转换为数字的行
        return sum(temps) / len(temps) if temps else None
    except Exception as e:
        return None

# 3. 收集数据
data = {city_name: [] for city_name in city_mapping.values()}

print("--- 开始诊断数据读取 ---")
for scenario in scenarios:
    folder_path = os.path.join(base_dir, scenario)
    temp_dict = {city_name: None for city_name in city_mapping.values()}

    if os.path.exists(folder_path):
        files_found = 0
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".epw"):
                city_code = filename[:6] # 截取前6位作为城市代码
                if city_code in city_mapping:
                    city_name = city_mapping[city_code]
                    filepath = os.path.join(folder_path, filename)
                    temp_dict[city_name] = get_epw_annual_avg_temp(filepath)
                    files_found += 1
        print(f"文件夹 '{scenario}' 中找到了 {files_found} 个匹配的气象文件。")
    else:
        print(f"警告: 找不到文件夹 '{folder_path}'")

    for city_name in city_mapping.values():
        data[city_name].append(temp_dict[city_name])

print("--- 数据读取完成 ---\n")

# 4. 数据预处理（将 None 转为 np.nan 避免运算报错）
def safe_array(data_list):
    return np.array([x if x is not None else np.nan for x in data_list], dtype=float)

cities = list(city_mapping.values())
x_cities = np.arange(len(cities))

hist_2020 = safe_array([data[city][0] for city in cities])

# 提取并计算 2040 的数据
temps_2040_26 = safe_array([data[city][1] for city in cities])
temps_2040_45 = safe_array([data[city][2] for city in cities])
temps_2040_85 = safe_array([data[city][3] for city in cities])
avg_2040 = np.nanmean([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
min_2040 = np.nanmin([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
max_2040 = np.nanmax([temps_2040_26, temps_2040_45, temps_2040_85], axis=0)
errors_2040_y = np.array([avg_2040 - min_2040, max_2040 - avg_2040])

# 提取并计算 2060 的数据
temps_2060_26 = safe_array([data[city][4] for city in cities])
temps_2060_45 = safe_array([data[city][5] for city in cities])
temps_2060_85 = safe_array([data[city][6] for city in cities])
avg_2060 = np.nanmean([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
min_2060 = np.nanmin([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
max_2060 = np.nanmax([temps_2060_26, temps_2060_45, temps_2060_85], axis=0)
errors_2060_y = np.array([avg_2060 - min_2060, max_2060 - avg_2060])


# 5. 数据可视化 (SCI 风格)
plt.rcParams['font.sans-serif'] = ['SimSun'] # 宋体或 Arial
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(8, 6))

width = 0.25
capsize = 4

# 空心效果：facecolor='none'
bars_hist = ax.bar(x_cities - width, hist_2020, width, 
                   facecolor='none', edgecolor='#72AACE', linewidth=3.5)
bars_mid = ax.bar(x_cities, avg_2040, width,
                  facecolor='none', edgecolor='#FDBA6D', linewidth=3.5)
bars_long = ax.bar(x_cities + width, avg_2060, width,
                   facecolor='none', edgecolor='#A70327', linewidth=3.5)

# 绘制误差带
ax.errorbar(x_cities, avg_2040, yerr=errors_2040_y, fmt='none', ecolor='black', capsize=capsize, elinewidth=1.2)
ax.errorbar(x_cities + width, avg_2060, yerr=errors_2060_y, fmt='none', ecolor='black', capsize=capsize, elinewidth=1.2)

# SCI 坐标轴风格：隐藏顶部和右侧边框
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# 【修改1】刻度线朝外 (direction='out')
ax.tick_params(axis='both', direction='out', length=5, width=1)

ax.set_ylabel('Annual Average Temperature (°C)', fontsize=12, fontweight='bold')
ax.set_xticks(x_cities)
ax.set_xticklabels(cities, fontsize=11)
ax.tick_params(axis='y', labelsize=11)

# 动态设置 Y 轴范围，将下限固定为 18
valid_data = np.concatenate([hist_2020, avg_2040, avg_2060])
valid_data = valid_data[~np.isnan(valid_data)]
if len(valid_data) > 0:
    ax.set_ylim(18, np.max(valid_data) + 2)

# 【修改2】已删除图例代码 (ax.legend(...))

plt.tight_layout()
plt.show()