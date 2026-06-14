"""
典型盛夏日负荷曲线 — 独立绘图脚本 (SCI Style - 强制 4-5 根刻度线 + 无右侧Y轴纯背景虚线叠加)
"""

import os, sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from matplotlib.ticker import FormatStrFormatter

import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# 🔴 全局配置区
# ==============================================================================

REMOVE_ALL_TEXT = False  # 【开关】设为 False 时显示文字和计算标注

FONT_FAMILY = 'Arial'        
OUTPUT_DPI = 600             
FIG_SIZE_COMBINED = (14, 6)
FIG_SIZE_SUMMARY = (22, 13)

LINE_WIDTH_SINGLE = 2.5
LINE_WIDTH_SUMMARY = 2.2
NIGHT_SHADE_COLOR = '#475894'
NIGHT_SHADE_ALPHA_SINGLE = 0.08
NIGHT_SHADE_ALPHA_SUMMARY = 0.06

XTICK_STEP = 6               
SHARE_Y_AXIS = False  # 关闭共享 Y 轴，各自独立寻找最优刻度

# -------------------------- [新增：2020 实际电网负荷路径] --------------------------
REAL_LOAD_PATH = os.path.join(PROJECT_ROOT, "data", "input data", "figure6", "省会城市24h电力负荷.xlsx")

STRAT_COLORS = {
    'S5 (AutoSize)':  '#931832',
    'S4 (Fix_Day26)': '#D56B52',
    'S3 (Fix_Day32)': '#EBB97F',
    'S2 (Fix_Eve26)': '#7B9FBC',
    'S1 (Baseline)':  '#475894'
}

F4 = [
    ('S5 (AutoSize)',  'S5_Future_AutoSize_AllDay_32_26',  STRAT_COLORS['S5 (AutoSize)']),
    ('S4 (Fix_Day26)', 'S4_Future_FixedCap_AllDay_32_26',  STRAT_COLORS['S4 (Fix_Day26)']),
    ('S3 (Fix_Day32)', 'S3_Future_FixedCap_AllDay_32_27',  STRAT_COLORS['S3 (Fix_Day32)']),
    ('S2 (Fix_Eve26)', 'S2_Future_FixedCap_Evening26',     STRAT_COLORS['S2 (Fix_Eve26)']),
    ('S1 (Baseline)',  'S1b_Future_FixedCap_Evening27',    STRAT_COLORS['S1 (Baseline)']),
]

# ============================================================
# 🔵 路径与常数配置区
# ============================================================
try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.getcwd()

PROJECT_ROOT = _HERE
for _ in range(10):
    if os.path.exists(os.path.join(PROJECT_ROOT, 'config', 'paths.py')):
        break
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SCRIPT_DIR = _HERE
EPW_DIR = os.path.join(PROJECT_ROOT, "data", "input data", "epw_files", "2060-rcp8.5")

OUTPUT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "figure6c_output")
CACHE_DIR = os.path.join(PROJECT_ROOT, "data", "input data", "figure6")

CITIES = [
    ('北京市', 'Beijing',   'bei3jing1shi4',  '110000'),
    ('上海市', 'Shanghai',  'shang4hai3shi4', '310000'),
    ('广州市', 'Guangzhou', 'guang3zhou1shi4', '440100'),
    ('深圳市', 'Shenzhen',  'shen1zhen4shi4', '440300'),
    ('武汉市', 'Wuhan',     'wu3han4shi4',    '420100'),
    ('厦门市', 'Xiamen',    'xia4men2shi4',   '350200'),
]

# ============================================================
# 辅助函数
# ============================================================
def setup_style():
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': [FONT_FAMILY],
        'axes.unicode_minus': False,
        'axes.linewidth': 1.5,
        'xtick.major.width': 1.5,
        'ytick.major.width': 1.5,
        'xtick.direction': 'out', 
        'ytick.direction': 'out',
        'axes.spines.top': False, 
        'axes.spines.right': False,
        'figure.dpi': OUTPUT_DPI,
    })

def _get_strict_ticks(max_val):
    if max_val <= 0:
        return np.array([0.0, 0.1, 0.2, 0.3])
        
    target_max = max_val * 1.02  
    possible_steps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0]
    
    best_step = None
    best_n = None
    min_empty = float('inf')
    
    for n_intervals in [3, 4]:
        for step in possible_steps:
            if step * n_intervals >= target_max:
                empty = step * n_intervals - max_val
                if empty < min_empty:
                    min_empty = empty
                    best_step = step
                    best_n = n_intervals
                    
    if best_step is None:
        best_step, best_n = 0.2, 3
        
    return np.arange(0, best_n + 1) * best_step

def _style_ax(ax, title, ylabel=True, is_summary=False, y_max=None):
    alpha = NIGHT_SHADE_ALPHA_SUMMARY if is_summary else NIGHT_SHADE_ALPHA_SINGLE
    ax.axvspan(22, 23.99, alpha=alpha, color=NIGHT_SHADE_COLOR)
    ax.axvspan(0, 7, alpha=alpha, color=NIGHT_SHADE_COLOR)
    ax.set_xlim(0, 24)
    
    if y_max is not None:
        yticks = _get_strict_ticks(y_max)
        ax.set_yticks(yticks)
        ax.set_ylim(0, yticks[-1])  
    
    ticks = np.arange(0, 25, XTICK_STEP)
    ax.set_xticks(ticks)
    
    if REMOVE_ALL_TEXT:
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.set_xlabel('')
        ax.set_ylabel('')
        ax.set_title('')
    else:
        title_fz = 14
        label_fz = 10 if is_summary else 12
        tick_fz = 9 if is_summary else 10
        
        ax.set_title(title, fontsize=title_fz, fontweight='bold')
        ax.set_xlabel('Hour of the Day' if not is_summary else 'Hour', fontsize=label_fz, fontweight='bold')
        if ylabel:
            ax.set_ylabel('Citywide Cooling Load (GW)' if not is_summary else 'Load (GW)', fontsize=label_fz, fontweight='bold')
            
        ax.set_xticklabels([f'{h:02d}:00' for h in ticks], fontsize=tick_fz)
        ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        ax.tick_params(axis='y', labelsize=tick_fz)

def _add_elevation_text(ax, mean_curves, is_summary=False):
    if REMOVE_ALL_TEXT: return  
    
    s5_label = 'S5 (AutoSize)'
    if s5_label not in mean_curves or mean_curves[s5_label].max() <= 0:
        return
        
    s5_peak = mean_curves[s5_label].max()
    text_lines = [r"$\bf{S5\ Peak\ Elevation:}$"] 
    
    for label, _, _ in F4:
        if label == s5_label: continue
        if mean_curves[label].max() > 0:
            other_peak = mean_curves[label].max()
            elevation = ((s5_peak - other_peak) / other_peak) * 100
            short_name = label.split(' ')[0]
            text_lines.append(f"vs {short_name}: +{elevation:.1f}%")
            
    if len(text_lines) > 1:
        final_text = "\n".join(text_lines)
        fz = 9 if is_summary else 10
        props = dict(boxstyle='round', facecolor='white', alpha=0.85, edgecolor='lightgray')
        ax.text(0.03, 0.58, final_text, transform=ax.transAxes, fontsize=fz,
                verticalalignment='top', bbox=props)

# -------------------------- [数据处理与绘制无轴背景虚线] --------------------------
def _load_real_grid_data():
    if not os.path.exists(REAL_LOAD_PATH):
        print(f"   [WARNING] 找不到实际电网负荷文件: {REAL_LOAD_PATH}")
        return None
    try:
        df = pd.read_excel(REAL_LOAD_PATH)
        df.iloc[:, 0] = df.iloc[:, 0].fillna(method='ffill')
        time_cols = df.columns[2:]
        df_norm = df.copy()
        df_norm[time_cols] = df_norm[time_cols].apply(lambda row: row / row.max(), axis=1)
        return df_norm
    except Exception as e:
        print(f"   [ERROR] 加载实际电网负荷文件失败: {e}")
        return None

def _plot_real_curve(ax, chn, day_type_str, real_df):
    """
    🟡 核心修改：仅在底层数学映射归一化曲线，视觉上完全抹除右侧 Y 轴
    """
    if real_df is None: return
    
    match = real_df[(real_df.iloc[:, 0].astype(str).str.contains(chn[:2])) & 
                    (real_df.iloc[:, 1].astype(str).str.contains(day_type_str))]
                    
    if not match.empty:
        real_curve = match.iloc[0, 2:26].values.astype(float) 
        
        ax2 = ax.twinx()  # 仅作比例映射，借用独立坐标系
        ax2.plot(range(24), real_curve, color='gray', linestyle='--', lw=2.2, alpha=0.6, zorder=1)
        ax2.set_ylim(0, 1.05)
        
        # 🟢 完全隐藏右侧的坐标刻度、数字、标签和边框轴线
        ax2.set_yticks([])
        ax2.set_ylabel('')
        ax2.spines['top'].set_visible(False)
        ax2.spines['bottom'].set_visible(False)
        ax2.spines['left'].set_visible(False)
        ax2.spines['right'].set_visible(False) # 隐藏右侧纵向黑线

def _epw_daily_features(pinyin):
    code = None
    for _, _, py, cd in CITIES:
        if py == pinyin: code = cd; break
    epw_file = None
    for f in os.listdir(EPW_DIR):
        if f.startswith(code) and f.endswith('.epw'):
            epw_file = os.path.join(EPW_DIR, f); break

    cols = list(range(34))
    df = pd.read_csv(epw_file, skiprows=8, header=None, names=cols, engine='python', on_bad_lines='skip')
    df = df[[1, 2, 3, 6, 13, 15]]
    df.columns = ['month', 'day', 'hour', 'T_db', 'GHI', 'DHI']
    for c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df[(df['month'] >= 5) & (df['month'] <= 10)]
    df['date_key'] = df['month'].astype(int).apply(lambda m: f'{m:02d}') + '/' + df['day'].astype(int).apply(lambda d: f'{d:02d}')

    daily = df.groupby('date_key').agg(
        T_max=('T_db', 'max'), T_min=('T_db', 'min'), T_mean=('T_db', 'mean'), GHI_sum=('GHI', 'sum')
    ).reset_index()
    daily['month'] = daily['date_key'].str[:2].astype(int)
    daily['day'] = daily['date_key'].str[3:5].astype(int)
    daily['datetime'] = pd.to_datetime('2060-' + daily['month'].astype(str) + '-' + daily['day'].astype(str), errors='coerce')
    
    daily['is_weekend'] = daily['datetime'].dt.dayofweek >= 5
    return daily

def _load_city_curves_cached(pinyin):
    cache_file = os.path.join(CACHE_DIR, f'{pinyin}_curves.pkl')
    if not os.path.exists(cache_file):
        raise FileNotFoundError(f"Cache not found: {cache_file}.")
    return pd.read_pickle(cache_file)

# ============================================================
# 主执行流程
# ============================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_style()
    print(f"\n{'='*60}")
    print(f"  Typical Midsummer Cooling Load Curves (Seamless Real Load Background)")
    print(f"{'='*60}")

    real_grid_df = _load_real_grid_data()
    real_line_legend = mlines.Line2D([], [], color='gray', linestyle='--', lw=2.2, alpha=0.6, label='2020 Grid Load Shape')

    city_data = {}
    for chn, en, pinyin, _ in CITIES:
        daily = _epw_daily_features(pinyin)
        features = daily[['T_max', 'T_min', 'T_mean', 'GHI_sum']].values
        X = StandardScaler().fit_transform(features)
        km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(X)
        daily['cluster'] = km.labels_
        ms_cl = daily.groupby('cluster')['T_mean'].mean().idxmax()
        ms = daily[daily['cluster'] == ms_cl]
        
        wd_dates = ms[~ms['is_weekend']]['date_key'].tolist()  
        we_dates = ms[ms['is_weekend']]['date_key'].tolist()   
        
        try:
            all_curves = _load_city_curves_cached(pinyin)
        except FileNotFoundError as e:
            print(f"   [SKIP] {e}")
            continue
            
        city_data[pinyin] = {
            'wd': wd_dates, 'we': we_dates, 'n_ms': len(ms), 'curves': all_curves,
        }
        print(f"   [INFO] {en}: loaded (Weekday={len(wd_dates)}, Weekend={len(we_dates)}).")

    global_y_max = 0
    compiled_summary_curves = {}

    for chn, en, pinyin, _ in CITIES:
        if pinyin not in city_data: continue
        cd = city_data[pinyin]
        
        for day_type in ['wd', 'we']:
            dates = cd[day_type]
            if len(dates) == 0: continue
            
            mean_curves = {l: np.zeros(24) for l, _, _ in F4}
            for dd in dates:
                dc = cd['curves'].get(dd, {})
                for l in mean_curves:
                    mean_curves[l] += dc.get(l, np.zeros(24))
            for l in mean_curves:
                mean_curves[l] /= len(dates)
                if mean_curves[l].max() > global_y_max:
                    global_y_max = mean_curves[l].max()
            
            if day_type == 'wd':
                compiled_summary_curves[pinyin] = {'curves': mean_curves, 'days': len(dates)}

    if not SHARE_Y_AXIS:
        global_y_max = None 

    z_order_map = {'S4': 5, 'S3': 6, 'S2': 7, 'S5': 9, 'S1': 10}

    # 绘制单独的城市图
    for chn, en, pinyin, _ in CITIES:
        if pinyin not in city_data: continue
        cd = city_data[pinyin]

        fig, axes = plt.subplots(1, 2, figsize=FIG_SIZE_COMBINED, sharey=True)
        local_y_max = 0
        plot_data = [] 
        
        for ax, (day_type, ttl) in zip(axes, [('wd', 'Weekday'), ('we', 'Weekend')]):
            dates = cd[day_type]
            mean_curves = {l: np.zeros(24) for l, _, _ in F4}
            
            if len(dates) > 0:
                for dd in dates:
                    dc = cd['curves'].get(dd, {})
                    for l in mean_curves:
                        mean_curves[l] += dc.get(l, np.zeros(24))
                for l in mean_curves:
                    mean_curves[l] /= len(dates)
                    if mean_curves[l].max() > local_y_max:
                        local_y_max = mean_curves[l].max()
            
            plot_data.append((ax, ttl, day_type, dates, mean_curves))

        for i, (ax, ttl, day_type, dates, mean_curves) in enumerate(plot_data):
            if len(dates) == 0:
                _style_ax(ax, f'{ttl} (0 days)', ylabel=(i==0), is_summary=False, y_max=local_y_max)
                continue
            
            for label, _, color in F4:
                if mean_curves[label].max() > 0:
                    strat_prefix = label[:2] 
                    current_z = z_order_map.get(strat_prefix, 5)
                    ax.plot(range(24), mean_curves[label], color=color, 
                            lw=LINE_WIDTH_SINGLE, alpha=1.0, zorder=current_z, label=label)
            
            _style_ax(ax, f'{ttl} ({len(dates)} days)', ylabel=(i==0), is_summary=False, y_max=local_y_max)
            _add_elevation_text(ax, mean_curves, is_summary=False)
            
            dt_str = 'workday' if day_type == 'wd' else 'off-workday'
            _plot_real_curve(ax, chn, dt_str, real_grid_df)

        if not REMOVE_ALL_TEXT:
            handles = [plt.Line2D([0], [0], color=c, lw=2.5) for _, _, c in F4] + [real_line_legend]
            labels = [l for l, _, _ in F4] + [real_line_legend.get_label()]
            axes[0].legend(handles, labels, title='Strategy / Grid Context', title_fontsize=12, fontsize=11, frameon=False, loc='upper left')
            fig.suptitle(f'{en}: Citywide Midsummer Cooling Load vs 2020 Grid Load', fontsize=18, fontweight='bold', y=1.05)

        fig.tight_layout()
        fn = f'Fig4_MS_{en}_Combined.png'
        fig.savefig(os.path.join(OUTPUT_DIR, fn), dpi=OUTPUT_DPI, bbox_inches='tight', transparent=True)
        plt.close(fig)
        print(f"   [OK] Combined 1x2 Fig generated: {en}")

    # 绘制矩阵汇总图
    fig, axes = plt.subplots(2, 3, figsize=FIG_SIZE_SUMMARY, sharey=SHARE_Y_AXIS)
    axes = axes.flatten()
    
    for i, (ax, (chn, en, pinyin, _)) in enumerate(zip(axes, CITIES)):
        if pinyin not in compiled_summary_curves: continue
        
        data = compiled_summary_curves[pinyin]
        mean_curves = data['curves']
        days = data['days']

        local_y_max_summary = max([mean_curves[l].max() for l in mean_curves if mean_curves[l].max() > 0] + [0])

        for label, _, color in F4:
            if mean_curves[label].max() > 0:
                strat_prefix = label[:2] 
                current_z = z_order_map.get(strat_prefix, 5)
                ax.plot(range(24), mean_curves[label], color=color, 
                        lw=LINE_WIDTH_SUMMARY, alpha=1.0, zorder=current_z, label=label)
        
        _style_ax(ax, f'{en} ({days} days)', is_summary=True, y_max=global_y_max if SHARE_Y_AXIS else local_y_max_summary)
        _add_elevation_text(ax, mean_curves, is_summary=True)
        _plot_real_curve(ax, chn, 'workday', real_grid_df)

    if not REMOVE_ALL_TEXT:
        handles = [plt.Line2D([0], [0], color=c, lw=2.5) for _, _, c in F4] + [real_line_legend]
        labels = [l for l, _, _ in F4] + [real_line_legend.get_label()]
        fig.legend(handles, labels, title='Strategy & Grid Context', title_fontsize=12,
                   fontsize=10, frameon=False, loc='upper center', ncol=6, bbox_to_anchor=(0.5, 0.005))
        fig.suptitle('Typical Midsummer Weekday Cooling Load vs 2020 Grid Load Shape',
                     fontsize=18, fontweight='bold', y=1.03)

    fig.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'Fig4_Midsummer_Summary.png'), dpi=OUTPUT_DPI, bbox_inches='tight', transparent=True)
    plt.close(fig)
    print(f"   [OK] Summary Matrix generated.")

if __name__ == '__main__':
    main()
    print(">> Done.")