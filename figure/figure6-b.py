"""
单层制冷容量云雨图 (Raincloud Plot) — SCI 横向矩阵定制版 (单RCP情景 + 纯净模式 + 强制统一Y轴)
(已更新为整栋建筑总面积 Total_Area_m2 + 城市 Excel 动态匹配 + 中文编码容错)
"""

import os, sys, warnings
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from matplotlib.ticker import LinearLocator

# =====================================================================
# 🔴 核心参数控制面板
# =====================================================================
REMOVE_TEXT = False  # 【主文字开关】True: 强制去除坐标轴、标题以及【均值数字】 | False: 保留学术文本
SHARE_Y = True      # 【纵轴一致】True: 六个城市强制绝对相同的 Y 轴范围及刻度线 

TARGET_SCENARIO = '8.5'         # 【情景过滤】默认 '8.5'
SHOW_MEAN_ANNOTATION =True   # 【均值线开关】True: 显示指示虚线 | False: 彻底隐藏虚线
PRINT_CONSOLE_STATS = True      # 【控制台静默开关】False: 关闭终端数据打印
# =====================================================================

# ---- 路径配置 ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "input", "figure6")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output", "figure6")

# 基础能耗数据路径
EC_PATH = os.path.join(DATA_DIR, "energy_capacity_summary.csv")
# 存放各城市逐栋建筑能耗 Excel 的目录
EXCEL_DIR = DATA_DIR

# ---- 常数及颜色设定 ----
CITIES = [
    ('北京市', 'Beijing',   'bei3jing1shi4', '110000'),
    ('上海市', 'Shanghai',  'shang4hai3shi4', '310000'),
    ('广州市', 'Guangzhou', 'guang3zhou1shi4', '440100'),
    ('深圳市', 'Shenzhen',  'shen1zhen4shi4', '440300'),
    ('武汉市', 'Wuhan',     'wu3han4shi4', '420100'),
    ('厦门市', 'Xiamen',    'xia4men2shi4', '350200'),
]

STRAT_SHORT = {
    '策略1 (Baseline_Evening27)': 'S1', 
    '策略2 (FixedCap_Evening26)': 'S2',
    '策略3 (FixedCap_AllDay_32_27)': 'S3', 
    '策略4 (FixedCap_AllDay_32_26)': 'S4',
    '策略5 (AutoSize_AllDay_32_26)': 'S5',
}

PALETTE = {'2040': '#475894', '2060': '#931832'}

def setup_style():
    plt.rcParams.update({
        'font.family': 'Arial',
        'axes.unicode_minus': False,
        'axes.linewidth': 1.2,
        'xtick.direction': 'in',
        'ytick.direction': 'in',
        'xtick.major.width': 1.2,
        'ytick.major.width': 1.2,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })

def build_prototype_area():
    """
    🔴 核心重构：彻底抛弃旧的复杂目录，直接从各城市能耗 Excel 中提取 Total_Area_m2
    建立 城市拼音+LandNum+Cluster+Fnum_x -> 整栋楼建筑总面积 的映射字典
    """
    proto_area = {}
    
    print(">> 正在从各城市能耗 Excel 构建整栋建筑总面积映射表 (Total Area Mapping)...")
    for chn, en, pinyin, code in CITIES:
        file_name = f"{chn}_building_energy.xlsx"
        file_path = os.path.join(EXCEL_DIR, file_name)
        
        if not os.path.exists(file_path):
            print(f"  [!] {chn} 跳过: 找不到能耗 Excel 文件 -> {file_path}")
            continue
        
        try:
            # 仅读取需要的结构特征与整栋建筑总面积列
            df_excel = pd.read_excel(file_path, usecols=['LandNum', 'Cluster', 'Fnum_x', 'Total_Area_m2'])
            
            # 按照原型三元组求建筑总面积均值（确保数据唯一健壮性）
            df_grouped = df_excel.groupby(['LandNum', 'Cluster', 'Fnum_x'])['Total_Area_m2'].mean().reset_index()
            
            for _, row in df_grouped.iterrows():
                # 存入字典，Key格式: (城市拼音, LandNum, Cluster, Fnum)
                key = (pinyin, str(int(row['LandNum'])), str(int(row['Cluster'])), int(row['Fnum_x']))
                proto_area[key] = row['Total_Area_m2']
                
            print(f"  [√] {chn} 匹配成功，载入 {len(df_grouped)} 种原型建筑总面积。")
        except Exception as e:
            print(f"  [X] 处理 {chn} Excel 数据时出错: {e}")
            
    print(f">> 总面积映射表构建完成，共包含 {len(proto_area)} 种建筑原型组合。\n")
    return proto_area

def draw_raincloud_panel(ax, data, title, show_ylabel=True, panel_letter="", y_limits=None):
    groups = [
        ('S1', '2040', 0.0),
        ('S1', '2060', 0.5),
        ('S5', '2040', 1.2),  
        ('S5', '2060', 1.7)
    ]

    for sl, yr, pos in groups:
        y_data = data[(data['SL'] == sl) & (data['Year'] == yr)]['AvgCap_Wm2'].dropna().values
        if len(y_data) < 3: 
            continue
            
        color = PALETTE[yr]

        # 1. 右侧：核密度估计 (云)
        try:
            kde = stats.gaussian_kde(y_data)
            y_grid = np.linspace(y_data.min() - y_data.std()*0.3, y_data.max() + y_data.std()*0.3, 200)
            x_grid = kde(y_grid)
            x_grid = x_grid / x_grid.max() * 0.30  
            ax.fill_betweenx(y_grid, pos, pos + x_grid, 
                             facecolor=color, alpha=0.55, edgecolor='black', lw=1.2, zorder=2)
        except np.linalg.LinAlgError:
            pass

        # 2. 中间：窄箱线图 (伞)
        box_pos = pos + 0.05
        ax.boxplot(y_data, positions=[box_pos], widths=0.05, patch_artist=True,
                   boxprops=dict(facecolor='white', color='black', lw=1.2, alpha=0.9),
                   medianprops=dict(color='black', lw=1.8),
                   whiskerprops=dict(color='black', lw=1.2),
                   capprops=dict(color='black', lw=1.2),
                   showfliers=False, zorder=3)

        # 3. 左侧：均值标注
        if SHOW_MEAN_ANNOTATION:
            mean_val = np.mean(y_data)
            ax.plot([pos - 0.08, pos], [mean_val, mean_val], color=color, lw=1.2, ls='--', zorder=4)
            
            if not REMOVE_TEXT:
                ax.text(pos - 0.10, mean_val, f"{mean_val:.1f}", 
                        color=color, ha='right', va='center', fontsize=10, fontweight='bold', zorder=5)

    if y_limits is not None:
        ax.set_ylim(y_limits)
        ax.set_yticks(np.linspace(y_limits[0], y_limits[1], 5))
    else:
        ax.yaxis.set_major_locator(LinearLocator(5))

    ax.set_xlim(-0.4, 2.1) 
    ax.set_xticks([0.25, 1.45])

    # 文本控制开关逻辑
    if REMOVE_TEXT:
        ax.set_title('')
        ax.set_ylabel('')
        ax.set_xlabel('')
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(axis='both', which='both', left=True, labelleft=False, bottom=True, labelbottom=False)
    else:
        ax.set_title(title, fontsize=14, fontweight='bold', pad=10)
        ax.set_xticklabels(['S1-S4\n(Fixed Capacity)', 'S5\n(AutoSize)'], fontsize=11)
        ax.tick_params(labelsize=11)
        
        if show_ylabel:
            ax.set_ylabel('Cooling Capacity (W/m$^2$)', fontsize=12, fontweight='bold')
            ax.tick_params(axis='y', left=True, labelleft=True)
        else:
            ax.set_ylabel('')
            ax.tick_params(axis='y', left=True, labelleft=False)

        if panel_letter:
            offset_x = -0.15 if show_ylabel else -0.05
            ax.text(offset_x, 1.05, f'({panel_letter})', transform=ax.transAxes,
                    fontsize=14, fontweight='bold', va='top', ha='right')

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_style()
    
    # ---- 0. 建立基于 Excel Total_Area_m2 的建筑总面积映射表 ----
    proto_area_dict = build_prototype_area()
    if not proto_area_dict:
        print("\n[致命错误] 面积映射表为空，请检查路径。程序退出。")
        sys.exit(1)

    # ---- 1. 数据加载与精准过滤 ----
    print(f">> 正在加载基础能耗数据: {EC_PATH}")
    if not os.path.exists(EC_PATH):
        print(f"\n[致命错误] 找不到能耗总表，请检查路径: {EC_PATH}")
        sys.exit(1)
        
    df = pd.read_csv(EC_PATH, encoding='utf-8-sig')
    df['SL'] = df['策略'].map(STRAT_SHORT)
    df['Year'] = df['情景'].str.extract(r'(20\d{2})')[0]
    
    df = df[df['SL'].notna() & df['Year'].notna()]
    df = df[df['情景'].str.contains(TARGET_SCENARIO, na=False)]
    
    if df.empty:
        raise ValueError(f"⚠️ 未找到包含 '{TARGET_SCENARIO}' 的情景数据！")

    cap_cols = [c for c in df.columns if 'Capacity' in str(c)]
    
    # 计算物理基础指标 (W)
    df['Total_W'] = df[cap_cols].sum(axis=1)          # 总容量(W)
    df['Fnum_actual'] = df[cap_cols].gt(0).sum(axis=1)

    # 提取 LandNum 和 Cluster
    extracted = df['建筑ID'].astype(str).str.extract(r'_(\d+)_(\d+)_')
    df['LandNum'] = extracted[0]
    df['Cluster'] = extracted[1]

    def get_area(row):
        if pd.isna(row['LandNum']) or pd.isna(row['Cluster']) or pd.isna(row['Fnum_actual']):
            return np.nan
        key = (row['城市'], str(int(row['LandNum'])), str(int(row['Cluster'])), int(row['Fnum_actual']))
        return proto_area_dict.get(key, np.nan)

    # 映射得到整栋建筑总面积并计算 W/m2
    print(">> 正在将能耗数据与建筑总面积匹配...")
    df['Area_m2'] = df.apply(get_area, axis=1)
    
    # 丢弃匹配不到面积的建筑
    missing_area_count = df['Area_m2'].isna().sum()
    if missing_area_count > 0:
        print(f"  [!] 提示: 有 {missing_area_count} 行数据未能匹配到建筑总面积，已自动剔除。")
        
    df = df.dropna(subset=['Area_m2'])
    df['AvgCap_Wm2'] = df['Total_W'] / df['Area_m2']
    
    # 清理计算异常的值
    df = df.dropna(subset=['AvgCap_Wm2']).copy()
    df_f = df[df['Year'].isin(['2040', '2060']) & df['SL'].isin(['S1', 'S5'])].copy()

    # ---- 2. 3×IQR 稳健过滤 ----
    grouped = df_f.groupby(['城市', 'SL', 'Year'])['AvgCap_Wm2']
    q1 = grouped.transform(lambda x: x.quantile(0.25))
    q3 = grouped.transform(lambda x: x.quantile(0.75))
    iqr = q3 - q1
    df_clean = df_f[(df_f['AvgCap_Wm2'] >= q1 - 3*iqr) & (df_f['AvgCap_Wm2'] <= q3 + 3*iqr)].copy()

    # ---- 3. 高级科学取整算法 (基于 W/m2 绝对范围控制) ----
    global_y_limits = None
    if SHARE_Y:
        ymax = df_clean['AvgCap_Wm2'].max()
        ymin_round = 0
        
        # 将最大值向上取整到 100 的整数倍
        ymax_round = math.ceil(ymax / 100) * 100
        while ymax_round % 4 != 0:
            ymax_round += 100
            
        global_y_limits = (ymin_round, ymax_round)

    # ---- 4. 绘制横 3 竖 2 汇总大矩阵拼图 ----
    print(">> 正在生成云雨图图表...")
    fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(14, 8.5), sharey=SHARE_Y)
    axes_flat = axes.flatten()
    letters = 'abcdef'

    for i, (chn, en, pinyin, _) in enumerate(CITIES):
        ax = axes_flat[i]
        cdf = df_clean[df_clean['城市'] == pinyin]
        if cdf.empty: continue
        
        show_yl = (i % 3 == 0) and (not REMOVE_TEXT)
        draw_raincloud_panel(ax, cdf, title=en, show_ylabel=show_yl, 
                             panel_letter=letters[i], y_limits=global_y_limits)

    if not REMOVE_TEXT:
        handles = [
            plt.Rectangle((0,0),1,1, facecolor=PALETTE['2040'], edgecolor='black', lw=1.2, alpha=0.55),
            plt.Rectangle((0,0),1,1, facecolor=PALETTE['2060'], edgecolor='black', lw=1.2, alpha=0.55)
        ]
        fig.legend(handles, ['2040', '2060'], title='Year', title_fontsize=13, fontsize=12,
                   frameon=False, loc='lower center', ncol=2, bbox_to_anchor=(0.5, 0.02))
        fig.suptitle(f'Cooling Capacity Density Distribution (RCP {TARGET_SCENARIO} Only)', fontsize=16, fontweight='bold', y=0.98)
        fig.subplots_adjust(top=0.88, bottom=0.15, left=0.06, right=0.96, hspace=0.30, wspace=0.15)
    else:
        fig.subplots_adjust(top=0.96, bottom=0.06, left=0.05, right=0.97, hspace=0.12, wspace=0.06)
                 
    output_filename = os.path.join(OUTPUT_DIR, f'Fig3_CapacityDensity_2x3_Raincloud_RCP{TARGET_SCENARIO}.svg')
    fig.savefig(output_filename, format='svg', transparent=True, bbox_inches='tight')
    plt.close(fig)
    
    if PRINT_CONSOLE_STATS:
        print(f"\n{'='*60}")
        print(f" 📊 2060年 S5(AutoSize) 相较于 S1(FixedCap) 单位面积容量平均提升幅度")
        print(f"    (注：当前数据仅包含极端气候情景 RCP {TARGET_SCENARIO} | 单位: W/m²)")
        print(f"{'='*60}")
        for chn, en, pinyin, _ in CITIES:
            cdf_2060 = df_clean[(df_clean['城市'] == pinyin) & (df_clean['Year'] == '2060')]
            if cdf_2060.empty: 
                continue
            s1_mean = cdf_2060[cdf_2060['SL'] == 'S1']['AvgCap_Wm2'].mean()
            s5_mean = cdf_2060[cdf_2060['SL'] == 'S5']['AvgCap_Wm2'].mean()
            
            if pd.notna(s1_mean) and pd.notna(s5_mean) and s1_mean > 0:
                pct_increase = (s5_mean - s1_mean) / s1_mean * 100
                print(f" 👉 [{en:<10}] 传统 S1均值: {s1_mean:>6.1f} W/m²  |  自适应 S5均值: {s5_mean:>6.1f} W/m²  |  相对提升: +{pct_increase:>4.1f}%")

    print(f"\n>> Done. 图表已生成并保存至 {OUTPUT_DIR}！")

if __name__ == '__main__':
    main()