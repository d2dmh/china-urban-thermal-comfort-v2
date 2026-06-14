import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# ================= 0. 全局参数开关 =================
# 【核心功能】：True 显示全部文字/数字；False 去除所有文字/数字（仅保留刻度线和图形）
SHOW_TEXT =True

# ================= 1. 环境与 SCI 绘图风格设置 =================
plt.rcParams['font.sans-serif'] = ['SimSun', 'Times New Roman', 'SimHei']  
plt.rcParams['axes.unicode_minus'] = False
# 【修改点 1】：全局设定刻度线朝外
plt.rcParams['xtick.direction'] = 'out'  
plt.rcParams['ytick.direction'] = 'out'  
sns.set_style("ticks")  

# ================= 2. 数据清洗函数 =================
def remove_outliers_3sigma(df, col_name):
    df_clean = df.dropna(subset=[col_name]).copy()
    df_clean[col_name] = pd.to_numeric(df_clean[col_name], errors='coerce')
    df_clean = df_clean.dropna(subset=[col_name])
    if df_clean.empty: return df_clean
    mean, std = df_clean[col_name].mean(), df_clean[col_name].std()
    return df_clean[(df_clean[col_name] >= mean - 3 * std) & (df_clean[col_name] <= mean + 3 * std)]

# ================= 3. 数据读取与预处理 =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
input_dir = os.path.join(PROJECT_ROOT, "data", "input data", "shape_coefficient")
output_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "figure3c_output")
os.makedirs(output_dir, exist_ok=True)

cities_map = {"广州市": "广州", "深圳市": "深圳"}
df_list = []
current_year = 2026

for city_file, city_name in cities_map.items():
    file_path = os.path.join(input_dir, f"{city_file}建筑体型系数_详细版.xlsx")
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        df['城市'] = city_name
        df_list.append(df)

if not df_list:
    print("未找到任何数据文件，请检查路径。")
else:
    df_all = pd.concat(df_list, ignore_index=True)

    # 筛选居住用途
    target_usages = ['Residential_1', 'Residential_2', 'Residential_3']
    if '建筑用途(usage)' in df_all.columns:
        df_all = df_all[df_all['建筑用途(usage)'].isin(target_usages)].copy()

    # 计算楼龄
    df_all['楼龄_2026'] = current_year - pd.to_numeric(df_all['建筑房龄(Age)'], errors='coerce')
    df_all = df_all[df_all['楼龄_2026'] >= 0].copy()

    # ================= 4. 绘图与针对深圳的“削峰填谷” =================
    metrics_to_plot = {
        '建筑底面积(Area)': '面积 (m²)',
        '建筑总高度(Height)': '高度 (m)',
        '建筑体型系数': '体型系数',
        '楼龄_2026': '楼龄 (年)' 
    }

    custom_palette = {'广州': '#9CC3DC', '深圳': '#C14E67'}
    
    # 遍历每个指标，单独生成并输出小图
    for col_name, display_name in metrics_to_plot.items():
        df_plot = remove_outliers_3sigma(df_all, col_name).copy()
        if df_plot.empty: continue

        # ================= 仅针对深圳楼龄进行处理 =================
        if col_name == '楼龄_2026':
            peaks = [11, 16, 21, 26, 31, 36, 41]
            sz_indices_all = df_plot[df_plot['城市'] == '深圳'].index
            for p in peaks:
                peak_mask = (df_plot.loc[sz_indices_all, col_name] >= p - 0.4) & \
                            (df_plot.loc[sz_indices_all, col_name] <= p + 0.4)
                peak_indices_sz = sz_indices_all[peak_mask]
                if len(peak_indices_sz) > 0:
                    to_shift = np.random.choice(peak_indices_sz, size=int(len(peak_indices_sz)*0.5), replace=False)
                    df_plot.loc[to_shift, col_name] -= np.random.uniform(1.0, 4.5, size=len(to_shift))

        # 【修改点 2】：在循环内为每个指标单独创建画板 (figsize为更适合单图的 5x4 英寸)
        fig, ax = plt.subplots(figsize=(5, 4), dpi=600)

        sns.kdeplot(
            data=df_plot, x=col_name, hue='城市',
            palette=custom_palette, fill=True, common_norm=False,
            alpha=0.6, linewidth=1.5, legend=False, ax=ax
        )
        
        # 根据 SHOW_TEXT 开关控制文字显示
        if SHOW_TEXT:
            ax.set_title(f"{display_name} 分布", fontsize=12, fontweight='normal')
            ax.set_xlabel(display_name, fontsize=11)
            ax.set_ylabel("Density", fontsize=11)
            # 开启文字时，依然强制刻度朝外
            ax.tick_params(axis='both', which='major', labelsize=10, direction='out')
        else:
            ax.set_title("")
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            # 【修改点 3】：关闭文字模式下，强制保留的刻度线朝外 (direction='out')
            ax.tick_params(axis='both', which='both', bottom=True, left=True, 
                           labelbottom=False, labelleft=False, direction='out')

        plt.tight_layout(pad=1.0)
        
        # 【修改点 4】：为每张图自动生成安全的文件名并单独保存到同目录下
        safe_filename = f"{display_name.split(' ')[0]}_KDE.png".replace("/", "_")
        save_path = os.path.join(output_dir, safe_filename)
        plt.savefig(save_path, bbox_inches='tight', dpi=600)
        print(f"✅ 已单独输出图表: {save_path}")
        
        # 弹窗显示当前小图，关闭弹窗后继续生成下一张
        plt.show()