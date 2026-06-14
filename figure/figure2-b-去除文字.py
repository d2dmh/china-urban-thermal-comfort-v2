import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import re
import os
import sys

# ================= 1. 路径全局配置 =================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

ROOT_MAP_DIR = os.path.join(DATA_DIR, "other data", "cluster_maps")
ROOT_POP_DIR = os.path.join(DATA_DIR, "other data", "population")
ROOT_OUTPUT_DIR = os.path.join(DATA_DIR, "output")  # Not used in this script
# HourlyStats xlsx files are pipeline output — run Code/run_all.py first
ROOT_SCENARIO_BASE = os.path.join(PROJECT_ROOT, "results", "27Degree", "set_calculations")

# EPW weather files
EPW_ROOT_DIR = os.path.join(DATA_DIR, "input data", "epw_files")
TARGET_FIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "figure2b_output")

# ================= 1.5 ⭐ 图表核心参数调整区 ⭐ =================

# 【柱状图长度控制】
BAR_X_MIN_MULTIPLIER = 0.90  # 柱状图下限比例
BAR_X_MAX_MULTIPLIER = 1.05  # 柱状图上限比例

# 【底部刻度字号】
SIZE_TICK = 20  # 底部X轴数值的字号

CITY_CONFIGS = [
    {"pinyin": "bei3jing1shi4", "chn_name": "北京市", "en_name": "Beijing", "code": "110000",
     "pop_subdir": "110000北京市"},
    {"pinyin": "shang4hai3shi4", "chn_name": "上海市", "en_name": "Shanghai", "code": "310000",
     "pop_subdir": "310000上海市", "custom_filename": "T310000_上海市_building_pop.csv"},
    {"pinyin": "guang3zhou1shi4", "chn_name": "广州市", "en_name": "Guangzhou", "code": "440100",
     "pop_subdir": "440000广东省"},
    {"pinyin": "shen1zhen4shi4", "chn_name": "深圳市", "en_name": "Shenzhen", "code": "440300",
     "pop_subdir": "440000广东省"},
    {"pinyin": "wu3han4shi4", "chn_name": "武汉市", "en_name": "Wuhan", "code": "420100",
     "pop_subdir": "420000湖北省"},
    {"pinyin": "xia4men2shi4", "chn_name": "厦门市", "en_name": "Xiamen", "code": "350200",
     "pop_subdir": "350000福建省", "custom_filename": "T350200_厦门市_building_pop.csv"}
]


# ================= 2. 核心处理逻辑 =================

def get_file_content(path):
    try:
        return pd.read_csv(path, encoding='gbk', low_memory=False)
    except:
        return pd.read_csv(path, encoding='utf-8-sig', low_memory=False)


def get_epw_annual_temp(code, pinyin, scenario_label, year):
    folder_map = {
        'Baseline_2020': '2020',
        'RCP 2.6_2040': '2040-rcp2.6',
        'RCP 4.5_2040': '2040-rcp4.5',
        'RCP 8.5_2040': '2040-rcp8.5',
        'RCP 2.6_2060': '2060-rcp2.6',
        'RCP 4.5_2060': '2060-rcp4.5',
        'RCP 8.5_2060': '2060-rcp8.5',
    }
    key = f"{scenario_label}_{year}"
    folder_name = folder_map.get(key)
    if not folder_name: return None

    epw_filename = f"{code}_{pinyin}_{folder_name}.epw"
    epw_path = os.path.join(EPW_ROOT_DIR, folder_name, epw_filename)
    if not os.path.exists(epw_path): return None

    try:
        df_epw = pd.read_csv(epw_path, skiprows=8, header=None, usecols=[6])
        return df_epw[6].mean()
    except Exception:
        return None


def process_city_data(city_conf):
    pinyin = city_conf['pinyin']
    chn_name = city_conf['chn_name']
    en_name = city_conf['en_name']
    code = city_conf['code']
    pop_subdir = city_conf['pop_subdir']

    print(f"\n{'=' * 20} 正在处理: {chn_name} ({en_name}) {'=' * 20}")

    file_map = os.path.join(ROOT_MAP_DIR, f"cluster_{code}_{chn_name}.csv")
    pop_filename = city_conf.get('custom_filename', f"T{code}_{chn_name}_building_pop_attributes.csv")
    file_pop = os.path.join(ROOT_POP_DIR, pop_subdir, pop_filename)

    if not os.path.exists(file_map) or not os.path.exists(file_pop):
        alt_pop = os.path.join(ROOT_POP_DIR, pop_subdir, f"{code}_{chn_name}_building_pop_attributes.csv")
        if os.path.exists(file_map) and os.path.exists(alt_pop):
            file_pop = alt_pop
        else:
            print(f"❌ [跳过] 基础文件缺失")
            return None

    try:
        df_cluster = get_file_content(file_map)
        df_pop = get_file_content(file_pop)
        df_cluster.columns = df_cluster.columns.str.strip()
        df_pop.columns = df_pop.columns.str.strip()

        if 'landUseTyp' in df_cluster.columns:
            df_cluster['landUseTyp'] = df_cluster['landUseTyp'].astype(str).str.strip()
            df_cluster = df_cluster[df_cluster['landUseTyp'].str.startswith('Residential', na=False)].copy()

        df_cluster['BuildingID'] = df_cluster['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True)
        df_pop['BuildingID'] = df_pop['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True)

        df_merged = pd.merge(df_cluster, df_pop, on='BuildingID', how='inner')
        col_fnum = 'Fnum' if 'Fnum' in df_merged.columns else ('Fnum_x' if 'Fnum_x' in df_merged.columns else None)

        if not col_fnum: return None

        df_merged['Cluster'] = pd.to_numeric(df_merged['Cluster'], errors='coerce').fillna(0).astype(int)
        df_merged[col_fnum] = pd.to_numeric(df_merged[col_fnum], errors='coerce').fillna(0).astype(int)
        df_merged['popNum_2'] = pd.to_numeric(df_merged['popNum_2'], errors='coerce').fillna(0)

        pop_lookup = df_merged.groupby(['Cluster', col_fnum])['popNum_2'].sum().reset_index()
        pop_lookup.rename(columns={col_fnum: 'Fnum'}, inplace=True)

    except Exception as e:
        print(f"❌ 数据预处理失败: {e}")
        return None

    scenarios = [
        {'label': 'Baseline', 'year': '2020',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Baseline', pinyin, f"{pinyin}_2020_HourlyStats.xlsx")},
        {'label': 'RCP 2.6', 'year': '2040',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2040-rcp2.6_HourlyStats.xlsx")},
        {'label': 'RCP 4.5', 'year': '2040',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2040-rcp4.5_HourlyStats.xlsx")},
        {'label': 'RCP 8.5', 'year': '2040',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2040-rcp8.5_HourlyStats.xlsx")},
        {'label': 'RCP 2.6', 'year': '2060',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2060-rcp2.6_HourlyStats.xlsx")},
        {'label': 'RCP 4.5', 'year': '2060',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2060-rcp4.5_HourlyStats.xlsx")},
        {'label': 'RCP 8.5', 'year': '2060',
         'path': os.path.join(ROOT_SCENARIO_BASE, 'Future', pinyin, f"{pinyin}_2060-rcp8.5_HourlyStats.xlsx")}
    ]

    city_summary_list = []

    for scen in scenarios:
        scenario_label = scen['label']
        target_year = scen['year']
        excel_path = scen['path']

        annual_temp = get_epw_annual_temp(code, pinyin, scenario_label, target_year)
        if not os.path.exists(excel_path): continue

        try:
            xls = pd.ExcelFile(excel_path)
            sum_person_hours = 0
            sum_total_pop = 0
            processed_sheets = set()

            for sheet_name in xls.sheet_names:
                match = re.search(r'_(\d+)_(\d+)_', sheet_name)
                if not match: continue
                try:
                    cluster_id = int(match.group(2))
                except:
                    continue

                base_sheet_name = re.sub(r'_\d+$', '', sheet_name)
                if base_sheet_name in processed_sheets: continue
                processed_sheets.add(base_sheet_name)

                df_sheet = pd.read_excel(xls, sheet_name=sheet_name)
                storey_cols = [c for c in df_sheet.columns if str(c).startswith('STOREY_')]
                fnum = len(storey_cols)
                if fnum == 0: continue

                pop_row = pop_lookup[(pop_lookup['Cluster'] == cluster_id) & (pop_lookup['Fnum'] == fnum)]
                current_pop_total = pop_row['popNum_2'].values[0] if not pop_row.empty else 0
                if current_pop_total == 0: continue

                avg_pop_per_floor = current_pop_total / fnum
                sum_total_pop += current_pop_total

                for col in storey_cols:
                    floor_discomfort_hours = df_sheet[col].sum()
                    if floor_discomfort_hours > 0:
                        sum_person_hours += (avg_pop_per_floor * floor_discomfort_hours)

            city_summary_list.append({
                'City': chn_name,
                'City_Label': en_name,
                'Year': target_year,
                'Scenario': scenario_label,
                'Total_Person_Hours': sum_person_hours,
                'Pop_Building_Total': sum_total_pop,
                'Annual_Temp': annual_temp
            })
            print(f"   -> {target_year} {scenario_label} 完成")
        except Exception as e:
            pass

    return pd.DataFrame(city_summary_list) if city_summary_list else None


# ================= 3. 绘图逻辑 =================
def plot_grouped_bar_sci(df_raw):
    if not os.path.exists(TARGET_FIG_DIR):
        os.makedirs(TARGET_FIG_DIR)

    df_plot_base = df_raw[df_raw['Pop_Building_Total'] > 0].copy()
    df_plot_base['Year_Scenario'] = df_plot_base.apply(
        lambda x: "2020 Baseline" if x['Scenario'] == 'Baseline' else f"{x['Year']} {x['Scenario']}",
        axis=1
    )

    grand_total = df_plot_base.groupby(['Year', 'Scenario', 'Year_Scenario']).agg(
        Total_Person_Hours=('Total_Person_Hours', 'sum'),
        Pop_Building_Total=('Pop_Building_Total', 'sum'),
        Annual_Temp=('Annual_Temp', 'mean')
    ).reset_index()
    grand_total['City'] = '总计'
    grand_total['City_Label'] = 'Grand Total'

    df_plot_final = pd.concat([df_plot_base, grand_total], ignore_index=True)
    df_plot_final['Y_Value'] = df_plot_final['Total_Person_Hours'] / df_plot_final['Pop_Building_Total']

    # ====== 确保导出矢量图时文字可编辑 ======
    plt.rcParams['font.family'] = 'Times New Roman'
    plt.rcParams['pdf.fonttype'] = 42
    plt.rcParams['ps.fonttype'] = 42

    unique_cities = list(df_plot_final['City_Label'].unique())
    scenario_order = ['2020 Baseline', '2040 RCP 2.6', '2040 RCP 4.5', '2040 RCP 8.5', '2060 RCP 2.6', '2060 RCP 4.5',
                      '2060 RCP 8.5']

    palette = {
        '2020 Baseline': '#3A51A1',
        '2040 RCP 2.6': '#72AACE',
        '2040 RCP 4.5': '#CAE8F2',
        '2040 RCP 8.5': '#FFFBBB',
        '2060 RCP 2.6': '#FDBA6D',
        '2060 RCP 4.5': '#EB5D3C',
        '2060 RCP 8.5': '#A70327'
    }

    print(f"\n{'=' * 20} 开始生成 SCI 水平分组柱状图 (带底部刻度) {'=' * 20}")

    fig, ax = plt.subplots(figsize=(12, 20))
    sns.set_style("white")

    # 1. 绘制水平柱状图
    bar_plot = sns.barplot(
        data=df_plot_final, x='Y_Value', y='City_Label', hue='Year_Scenario',
        order=unique_cities, hue_order=scenario_order, palette=palette,
        ax=ax, edgecolor='black', linewidth=1.2, zorder=2, orient='h'
    )

    # 动态调整 X 轴范围限制
    min_bar_val = df_plot_final['Y_Value'].min()
    max_bar_val = df_plot_final['Y_Value'].max()
    ax.set_xlim(int(min_bar_val * BAR_X_MIN_MULTIPLIER), int(max_bar_val * BAR_X_MAX_MULTIPLIER))

    # ================= 文字控制逻辑 =================
    # 清除坐标轴标题
    ax.set_xlabel('')
    ax.set_ylabel('')

    # 【修改点】：仅清除左侧(Y轴)的分类文字，保留底部(X轴)的数值和刻度线
    ax.set_yticks([])  # 清除左侧文字
    ax.tick_params(axis='x', labelsize=SIZE_TICK, width=2.0)  # 保留底部刻度并设置字号和线宽

    # 移除 seaborn 自动生成的图例
    if ax.get_legend() is not None:
        ax.get_legend().remove()

    # ================= 边框设置保留 =================
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_linewidth(2.0)
    ax.spines['bottom'].set_color('black')
    ax.spines['left'].set_linewidth(2.0)
    ax.spines['left'].set_color('black')

    # 为了方便后期在 AI 软件里处理，建议同时保存一份 PDF
    save_path_png = os.path.join(TARGET_FIG_DIR, 'SCI_Custom_Params_Plot_Horizontal_BottomTicks.png')
    save_path_pdf = os.path.join(TARGET_FIG_DIR, 'SCI_Custom_Params_Plot_Horizontal_BottomTicks.pdf')

    plt.savefig(save_path_png, dpi=600, bbox_inches='tight', format='png')
    plt.savefig(save_path_pdf, bbox_inches='tight', format='pdf')  # 额外生成一份 PDF
    plt.close()

    print(f"✅ 生成完毕 (PNG和PDF已同时保存): \n{save_path_png}\n{save_path_pdf}")


# ================= 4. 主程序 =================
if __name__ == "__main__":
    all_summaries = []
    for city in CITY_CONFIGS:
        df_city_res = process_city_data(city)
        if df_city_res is not None:
            all_summaries.append(df_city_res)

    if all_summaries:
        final_df = pd.concat(all_summaries, ignore_index=True)
        plot_grouped_bar_sci(final_df)

    print("\n🎉🎉 完美运行！除底部数值刻度外，其他文字已隐去。同时为您输出了方便矢量编辑的 PDF 格式文件。")