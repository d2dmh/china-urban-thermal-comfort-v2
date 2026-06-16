# CLAUDE.md — 项目指引

## 项目概要

中国城市住宅夜间热舒适分析。评估不同气候情景（2020/2040/2060 × RCP 2.6/4.5/8.5）和空调策略（S1-S5）下的人均不舒适小时数（SET>30°C），覆盖北京、上海、广州、深圳、武汉、厦门 6 个城市。

## 核心概念

- **SET** = 标准有效温度，用 `pythermalcomfort.set_tmp()` 计算
- **不舒适小时数** = 夜间（22:00-07:00）SET > 30°C 的小时数
- **人均不舒适小时数** = Σ(每层人口 × 该层不舒适小时数) / 总人口
- 人口匹配用 `(LandNum, Cluster, Fnum)` 三元组，从 cluster 映射 + 人口属性文件聚合
- RH 通过 Magnus 公式从含湿量和大气压计算，空调截断 ≤60%
- MET=0.7, CLO=0.8, v=0.1, SET_threshold=30°C

## 管线执行顺序

```
Step 1: code/step1_compute_set.py          → SET计算 + 人均 + 逐时Excel
Step 2: code/step2_pivot_tables.py         → 透视表
Step 3: code/step3_energy_capacity.py      → 能耗 + 容量 + 峰值负荷
Step 4: code/step4_citywide_load_curves.py → 城市级 GW 负荷曲线
```

`code/run_all.py` 一键执行。

## 项目结构

```
thermal_comfort_analysis/
├── code/                # 管线代码
│   ├── config/          # 参数配置 (parameters.py, paths.py)
│   ├── core/            # 核心计算 (SET, EPW, RH)
│   ├── pipeline/        # 旧版 pipeline 模块（保留引用）
│   ├── step1_compute_set.py
│   ├── step2_pivot_tables.py
│   ├── step3_energy_capacity.py
│   ├── step4_citywide_load_curves.py
│   └── run_all.py
├── figure/              # 全部画图脚本 (16个)
├── input/               # 外部输入数据 (Zenodo)
├── output/              # 图表输出
│   ├── figure2/
│   ├── figure3/
│   ├── figure4/
│   ├── figure5/
│   └── figure6/
└── .gitignore
```

## 图示脚本与输入数据

### Figure 2

| 脚本 | 输入数据 | 输出 |
|------|----------|------|
| `fig2-1地图-建筑气候区划.py` | `input/china_city_shp/`, `input/china_ninedash_shp/` | `output/figure2/Fig2-1_China_Building_Climate_Zones.png` |
| `figure2-b-去除文字.py` | `input/cluster_maps/`, `input/population_csv/{code}_{City}_full.csv`, `input/pipeline_outputs/hourly_set/{Baseline,Future}/`, `input/epw/` | `output/figure2/SCI_Custom_Params_Plot_Horizontal_BottomTicks.png/pdf` |
| `figure2-c.py` | `input/beijing_building_data/Beijing_buildings.shp`, `input/beijing_weibo/`, `input/china_county_shp/` | `output/figure2/` |
| `figure2-c_public.py` | `figure/figure2c_grid_data/` (GeoJSON) | `output/figure2/` |
| `figure2-d.py` | `input/beijing_building_data/`, `input/population_csv/`, `input/pipeline_outputs/zhibiao/` | `output/figure2/` |
| `figure2-d_public.py` | `figure/figure2d_grid_data/` (GeoJSON) | `output/figure2/` |

### Figure 3

| 脚本 | 输入数据 | 输出 |
|------|----------|------|
| `figure3-a.py` | `input/epw/` (GZ+SZ, 7 scenarios) | `output/figure3/Fig3-a_Annual_Temperature_Comparison.png` |
| `figure3-b.py` | 硬编码数据 (从 pipeline summary CSV 提取) | `output/figure3/Fig3-b_Discomfort_Hours_Comparison.png` |
| `figure3-c.py` | `input/shape_coefficient/` (GZ+SZ 建筑体型系数) | `output/figure3/` 4张 KDE 图 |

### Figure 4

| 脚本 | 输入数据 | 输出 |
|------|----------|------|
| `figure4-l.py` | `input/pipeline_outputs/hourly_set/summary_uncomfortable_hours.csv` | `output/figure4/Discomfort_{High,Mid,Low}-rise.png` |
| `figure4-r.py` | `input/GeiMingHao_27Degree/` (深圳 EnergyPlus CSV), `input/cluster_maps/cluster_440300_深圳市.csv`, `input/epw/`, `code/core/` | `output/figure4/Discomfort_Hourly_Top_vs_NonTop.png` |

### Figure 5

| 脚本 | 输入数据 | 输出 |
|------|----------|------|
| `figure5.py` | `input/population_csv/`, `input/pipeline_outputs/zhibiao/`, `input/pipeline_outputs/pop_lookup/`, `input/china_county_shp/` | `output/figure5/` |
| `figure5_public.py` | `figure/figure5_grid_data/` (GeoJSON) | `output/figure5/` |

### Figure 6

| 脚本 | 输入数据 | 输出 |
|------|----------|------|
| `figure6-a.py` | `input/figure6/{city}_building_energy.xlsx`, `input/figure6/per_capita_hours_summary.csv` | `output/figure6/Fig5_Tradeoff_Scatter_Absolute_Updated.png` |
| `figure6-b.py` | `input/figure6/energy_capacity_summary.csv`, `input/figure6/{city}_building_energy.xlsx` | `output/figure6/Fig3_CapacityDensity_2x3_Raincloud_RCP8.5.svg` |
| `figure6-c.py` | `input/figure6/{pinyin}_curves.csv`, `input/epw/2060-rcp8.5/`, `input/figure6/省会城市24h电力负荷.xlsx` | `output/figure6/Fig4_MS_{City}_Combined.png` ×6, `Fig4_Midsummer_Summary.png` |

## 输入数据 `input/` 目录

| 目录 | 内容 | 来源 |
|------|------|------|
| `epw/` | 气象文件 (6城市×7情景=42文件) | 外部 |
| `figure6/` | 建筑能耗 Excel、容量汇总 CSV、人均小时 CSV、GW 负荷曲线 CSV、电网负荷 | 预计算 |
| `shape_coefficient/` | 广州/深圳建筑体型系数 | 外部 |
| `cluster_maps/` | 建筑原型聚类映射 (6城市) | 预计算 |
| `population_csv/` | 脱敏人口属性 CSV (8列: BuildingID,Area,landUseTyp,Height,Age,popNum_2,age0_2,age65abv_2) | 从原始 SHP 提取 |
| `pipeline_outputs/` | 管线产出: zhibiao, pop_lookup, hourly_set, summary CSV, pivot_tables | 运行管线生成 |
| `beijing_building_data/` | 北京建筑 SHP + 脱敏 CSV | 外部 |
| `GeiMingHao_27Degree/` | 深圳 EnergyPlus 仿真 CSV (仅 figure4-r 使用, 447MB) | 外部 |
| `china_*_shp/` | 中国标准地图 (审图号 GS(2024)0650) | 外部 |
| `beijing_weibo/` | 匿名微博签到数据 | 收集 |

## 路径约定

所有脚本使用以下模式构建路径：

```python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # figure/ 脚本往上 1 层即项目根
```

- **code/ 根脚本**: `PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))` (1 层上)
- **figure/ 脚本**: `PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)` (1 层上)
- **code/ 子模块** (epw_handler, set_calculator 等) 被 figure4-r 作为 package 导入，需保留 `code/__init__.py` 和 `code/config/__init__.py`

## 编码注意事项

- Windows GBK 终端不支持 emoji，用 `[OK]`/`[ERROR]`/`[DONE]`/`[SKIP]` 代替
- CSV 读写统一用 `encoding='utf-8-sig'` 优先（自动去 BOM），GBK 兜底
- EPW 文件名用拼音（如 `guang3zhou1shi4`），非英文关键词
- matplotlib 中文字体必须在 `sns.set_style()` 之后设置（seaborn 会重置 `font.sans-serif`）

## 重要修复记录

1. **EPW 气压**：`find_epw_file()` 用英文关键词搜索失败 → 新增 `_find_epw()` 用拼音匹配
2. **统计口径**：仅统计 HVAC=1 & COOLING=1 的夜间时段
3. **get_file_content**：先试 utf-8-sig（去 BOM）再试 gbk，避免列名 `﻿BuildingID` 导致 KeyError
4. **code package**：`code/__init__.py` 和 `code/config/__init__.py` 必须存在，否则 `from code.core...` 报 ModuleNotFoundError
5. **S2/S3 命名**：CSV 数据源已修正，S2 = Fix_Day32（全天降温），S3 = Fix_Eve26（调低晚间设定温度）
6. **figure6-c DPI**：统一为 600

## Git 约定

- `input/` 下的大文件目录在 `.gitignore` 中排除，通过 Zenodo 分发
- `output/` 在 `.gitignore` 中排除（运行时生成）
- 只提交代码（`.py`）和文档（`.md`），不提交数据
