"""
Step 5: 策略对比散点图 — E vs U (绝对量版)，带 RCP 不确定性误差棒
SCI Publication Style Version (多城市 Excel 逐栋加总重构版 + 绝对量 S0 + TWh单位 + 兼容性修复版)
"""

import os
import sys
import warnings
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

warnings.filterwarnings('ignore') # 忽略字体与全面解析警告

# ==============================================================================
# 🔴 终极全局配置区 (所有视觉与逻辑参数均集中于此，向下代码无需修改)
# ==============================================================================

# -------------------------- [1. 路径与模式设置] --------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "input data", "figure6")
EC_DIR = DATA_DIR   # {City}_building_energy.xlsx
PC_PATH = os.path.join(DATA_DIR, "per_capita_hours_summary.csv")
FIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "figure6a_output") 

REMOVE_ALL_TEXT = True # 【开关】设为 True 时，一键去除所有坐标轴、标题、图例文字，仅保留纯图形


# -------------------------- [2. 画布比例与画质 (高度压缩)] --------------------------
FONT_FAMILY = 'Arial'        # 全局无衬线字体
OUTPUT_DPI = 600             # 输出分辨率 (600 dpi 满足顶刊要求)
FIG_SIZE = (16, 5.5)         # 画布尺寸 (宽, 高)。使图表更扁平紧凑


# -------------------------- [3. 散点与误差棒样式 (包含防遮挡图层控制)] --------------------------
SCATTER_ALPHA = 0.8          # 彩色散点的透明度
SCATTER_EDGE_WIDTH = 0.2     # 散点白色描边的粗细
SCATTER_ZORDER = 5           # 散点的图层层级

ERROR_BAR_ALPHA = 0.8        # 误差棒的透明度
ERROR_BAR_LINEWIDTH = 1.5    # 误差棒的线条粗细
ERROR_BAR_ZORDER = 6         # 误差棒的图层层级。确保短误差棒浮现

MARKER_SIZES = {
    'Beijing': 11, 'Shanghai': 10.5, 'Guangzhou': 12,  
    'Shenzhen': 12, 'Wuhan': 11, 'Xiamen': 19  
}


# -------------------------- [4. 图例位置微调] --------------------------
LEGEND_CITY_POS = (1.02, 1.0)    
LEGEND_STRAT_POS = (1.02, 0.55)  


# -------------------------- [5. 核心视觉映射字典 (包含 S0)] --------------------------
MARKERS = {
    'Beijing': 'o', 'Shanghai': 's', 'Guangzhou': '^',
    'Shenzhen': 'v', 'Wuhan': 'D', 'Xiamen': '*'
}

STRAT_COLORS = {
    'S5': '#931832', 'S4': '#D56B52', 'S3': '#EBB97F', 
    'S2': '#7B9FBC', 'S1': '#475894', 'S0': '#A6A6A6'  # S0 为灰色
}

# 关注的标准策略代号
TARGET_STRATS = ['S1', 'S2', 'S3', 'S4', 'S5']

# ==============================================================================
# 🔵 核心处理与绘图逻辑区 (日常使用无需修改以下代码)
# ==============================================================================

os.makedirs(FIG_DIR, exist_ok=True)

CITY_CN2EN = {
    '北京市': 'Beijing', '上海市': 'Shanghai', '广州市': 'Guangzhou',
    '深圳市': 'Shenzhen', '武汉市': 'Wuhan', '厦门市': 'Xiamen',
}
CITY_PY2CN = {
    'bei3jing1shi4': '北京市', 'shang4hai3shi4': '上海市', 'guang3zhou1shi4': '广州市',
    'shen1zhen4shi4': '深圳市', 'wu3han4shi4': '武汉市', 'xia4men2shi4': '厦门市',
}


def parse_excel_cooling_energy():
    """自下而上加总各城市逐栋建筑 Excel 能耗"""
    all_city_results = []
    
    for city_cn, city_en in CITY_CN2EN.items():
        file_name = f"{city_cn}_building_energy.xlsx"
        file_path = os.path.join(EC_DIR, file_name)
        
        if not os.path.exists(file_path):
            continue
            
        df_buildings = pd.read_excel(file_path)
        
        # 筛选有效的策略列
        energy_cols = [col for col in df_buildings.columns if re.match(r'^S[1-5]_\d{4}_RCP_\d{2}_kWh$', col) or col == 'S1_2020_Baseline_kWh']
        if not energy_cols:
            continue
            
        # 全市求和并转为 TWh
        city_sum = df_buildings[energy_cols].sum().reset_index()
        city_sum.columns = ['Scenario_Raw', 'Energy_kWh']
        city_sum['Energy_TWh'] = city_sum['Energy_kWh'] / 1e9
        
        for _, row in city_sum.iterrows():
            raw_name = row['Scenario_Raw']
            e_twh = row['Energy_TWh']
            
            if raw_name == 'S1_2020_Baseline_kWh':
                parsed_rows = {'城市': city_cn, 'SL': 'S1', 'Year': '2020', 'RCP': 'Baseline', 'Energy_TWh': e_twh}
                all_city_results.append(parsed_rows)
            else:
                match = re.match(r'^(S[1-5])_(\d{4})_RCP_(\d)(\d)_kWh$', raw_name)
                if match:
                    sl, year, rcp_main, rcp_sub = match.groups()
                    if sl == 'S2': sl = 'S3'
                    elif sl == 'S3': sl = 'S2'
                    rcp_str = f"RCP {rcp_main}.{rcp_sub}"
                    all_city_results.append({
                        '城市': city_cn, 'SL': sl, 'Year': year, 'RCP': rcp_str, 'Energy_TWh': e_twh
                    })
                    
    if not all_city_results:
        raise ValueError(f"[错误] 没有从 {EC_DIR} 中成功解析出任何城市的能耗数据！请确认路径和文件名。")
        
    return pd.DataFrame(all_city_results)


def build_tradeoff_data():
    if not os.path.exists(PC_PATH):
        raise FileNotFoundError(f"\n[错误] 找不到不舒适时长 CSV 文件！\n请检查 PC_PATH: {PC_PATH}")

    # A. 加载自下而上加总的真实建筑耗电数据 (TWh)
    print(">> 正在解析并加总各城市逐栋建筑能耗 Excel...")
    ec_agg = parse_excel_cooling_energy()
    
    # B. 加载并清洗人均不舒适小时数 CSV
    print(">> 正在加载人均不舒适小时数据...")
    pc = pd.read_csv(PC_PATH, encoding='utf-8-sig')
    
    STRAT_NAMES = {
        '策略3 (FixedCap_AllDay_32_27)': 'S2',  
        '策略2 (FixedCap_Evening26)': 'S3',     
        '策略4 (FixedCap_AllDay_32_26)': 'S4',
        '策略5 (AutoSize_AllDay_32_26)': 'S5',
        '策略1 (Baseline_Evening27)': 'S1',
    }
    pc['SL'] = pc['策略'].map(STRAT_NAMES)
    pc['Year'] = pc['情景'].str.extract(r'(20\d{2})')[0]
    pc['RCP'] = pc['情景'].str.extract(r'(RCP \d\.\d)')[0]
    
    pc.loc[(pc['Year'] == '2020') & (pc['策略'].str.contains('Baseline', na=False)), 'RCP'] = 'Baseline'
    pc = pc[pc['SL'].notna() & pc['Year'].notna()]
    pc = pc.rename(columns={'Hours_Per_Resident': 'U_Hours'})
    
    # 🟡 【核心修复：自适应城市名映射】
    # 检测首行。如果是拼音则映射，如果是中文则保持原样，防止全部变成 NaN
    if pc['城市'].dropna().iloc[0] in CITY_PY2CN:
        pc['城市'] = pc['城市'].map(CITY_PY2CN)

    # C. 双表内连接合并 (未来预测部分)
    m = pd.merge(ec_agg[ec_agg['Year'].isin(['2040','2060'])],
                 pc[pc['Year'].isin(['2040','2060'])][['城市', 'Year', 'RCP', 'SL', 'U_Hours']],
                 on=['城市', 'Year', 'RCP', 'SL'], how='inner')

    # 🟡 【安全检修：防止因匹配为空而报错】
    if m.empty:
        print("\n[数据对齐失败调试快照]")
        print("--- 能耗表(Excel) 前5行 ---")
        print(ec_agg[ec_agg['Year'].isin(['2040','2060'])].head())
        print("--- 不舒适时长表(CSV) 前5行 ---")
        print(pc[pc['Year'].isin(['2040','2060'])][['城市', 'Year', 'RCP', 'SL']].head())
        raise ValueError("[错误] 两个数据表合并后结果为空！请检查两表的 城市名格式、RCP名称(如 RCP 2.6) 或 策略代号 是否能对应上。")

    # D. 提取 2020 真实值作为未来的基础锚点 S0
    e_2020 = ec_agg[(ec_agg['Year'] == '2020') & (ec_agg['SL'] == 'S1')].set_index('城市')['Energy_TWh'].to_dict()
    u_2020 = pc[(pc['Year'] == '2020') & (pc['SL'] == 'S1')].groupby('城市')['U_Hours'].first().to_dict()

    results = []
    for city in e_2020.keys():
        if city in u_2020:
            for year in ['2040', '2060']:
                results.append({
                    '城市': city, 'Year': year, 'RCP': 'Baseline',
                    'SL': 'S0', 'Abs_E': e_2020[city], 'Abs_U': u_2020[city],
                })

    for _, row in m.iterrows():
        results.append({
            '城市': row['城市'], 'Year': row['Year'], 'RCP': row['RCP'],
            'SL': row['SL'], 'Abs_E': row['Energy_TWh'], 'Abs_U': row['U_Hours'],
        })

    df = pd.DataFrame(results)

    # E. 聚合计算最大/最小区间（用于不确定性误差棒）
    agg = df.groupby(['城市', 'Year', 'SL']).agg(
        E_mean=('Abs_E', 'mean'), E_min=('Abs_E', 'min'), E_max=('Abs_E', 'max'),
        U_mean=('Abs_U', 'mean'), U_min=('Abs_U', 'min'), U_max=('Abs_U', 'max'),
    ).reset_index()

    agg['City_EN'] = agg['城市'].map(CITY_CN2EN)
    return agg


def plot_tradeoff():
    df = build_tradeoff_data()

    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': [FONT_FAMILY], 
        'font.size': 12,                                     
        'axes.unicode_minus': False,
        'axes.linewidth': 1.5,                               
        'xtick.major.width': 1.5,            
        'ytick.major.width': 1.5,            
        'xtick.major.size': 6,               
        'ytick.major.size': 6,
        'xtick.direction': 'in',             
        'ytick.direction': 'in',
        'axes.spines.top': False,            
        'axes.spines.right': False,          
        'figure.dpi': OUTPUT_DPI,                   
    })

    fig, axes = plt.subplots(1, 2, figsize=FIG_SIZE, sharey=True)

    all_x = pd.concat([df['E_min'], df['E_max']])
    x_hi = all_x.max() * 1.05
    x_lo = 0 

    for ax, year in zip(axes, ['2040', '2060']):
        ydf = df[df['Year'] == year]
        
        for _, row in ydf.iterrows():
            city_en = row['City_EN']
            sl = row['SL']
            
            xerr = np.array([[row['E_mean'] - row['E_min']], [row['E_max'] - row['E_mean']]])
            yerr = np.array([[row['U_mean'] - row['U_min']], [row['U_max'] - row['U_mean']]])
            
            # A. 绘制不确定性误差棒
            ax.errorbar(row['E_mean'], row['U_mean'],
                        xerr=xerr, yerr=yerr,
                        fmt='none',                               
                        ecolor=STRAT_COLORS[sl],                 
                        capsize=0, 
                        elinewidth=ERROR_BAR_LINEWIDTH,               
                        alpha=ERROR_BAR_ALPHA, 
                        zorder=ERROR_BAR_ZORDER)                    

            # B. 绘制彩色散点
            ax.plot(row['E_mean'], row['U_mean'],
                    marker=MARKERS[city_en], 
                    markersize=MARKER_SIZES[city_en], 
                    color=STRAT_COLORS[sl], 
                    linestyle='none',
                    markeredgewidth=SCATTER_EDGE_WIDTH, markeredgecolor='white', 
                    alpha=SCATTER_ALPHA, 
                    zorder=SCATTER_ZORDER)
        
        ax.set_xlim(left=x_lo, right=x_hi)
        
        if REMOVE_ALL_TEXT:
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.set_title('')
        else:
            ax.set_title(f'{year}', fontsize=16, fontweight='bold', pad=15)
            ax.set_xlabel('Total Cooling Energy Demand (TWh)', fontsize=14, fontweight='bold')
            if ax == axes[0]:
                ax.set_ylabel('Per Capita Discomfort Hours (h)', fontsize=14, fontweight='bold')

    if not REMOVE_ALL_TEXT:
        city_handles = [mlines.Line2D([], [], marker=m, color='#666666', linestyle='none',
                                      markersize=MARKER_SIZES[n] * 0.8, label=n)
                        for n, m in MARKERS.items()]
        
        leg1 = axes[1].legend(handles=city_handles, title='City', title_fontsize=13,
                              fontsize=11, frameon=False, loc='upper left',
                              bbox_to_anchor=LEGEND_CITY_POS)

        strat_handles = [mlines.Line2D([], [], marker='o', color=c, linestyle='none',
                                       markersize=10, label=sl, markeredgecolor='white', markeredgewidth=0.5)
                         for sl, c in STRAT_COLORS.items()]
        
        axes[1].legend(handles=strat_handles[::-1], title='Strategy', title_fontsize=13,
                       fontsize=11, frameon=False, loc='upper left',
                       bbox_to_anchor=LEGEND_STRAT_POS)
        axes[1].add_artist(leg1)

        fig.suptitle('Strategy Trade-Off: Absolute Energy vs. Discomfort\n(S0 = 2020 Baseline, error bars = RCP range)',
                     fontsize=18, fontweight='bold', y=1.05)

    fig.tight_layout()
    out = os.path.join(FIG_DIR, 'Fig5_Tradeoff_Scatter_Absolute_Updated.png') 
    
    fig.savefig(out, dpi=OUTPUT_DPI, bbox_inches='tight', transparent=True)
    plt.close(fig)
    print(f"   [OK] 图表已成功生成！路径为: {out}")


if __name__ == '__main__':
    print(f"\n{'='*60}")
    print(f"  执行重构修正版 Step 5: 核心权衡散点图生成")
    print(f"  纯净图形模式 (无文字): {REMOVE_ALL_TEXT}")
    print(f"{'='*60}")
    plot_tradeoff()
    print(">> 运行完毕！")