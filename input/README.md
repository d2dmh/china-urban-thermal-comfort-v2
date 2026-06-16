# Input Data

All external data required to run the pipelines and figures. Download from **[Zenodo](https://doi.org/10.5281/zenodo.20691709)** (10.5281/zenodo.20691709) and extract to `input/`.

## Directory structure

```
input/
├── epw/                              EPW weather files (6 cities × 7 scenarios = 42 files)
│   ├── 2020/                         2020 baseline
│   ├── 2040-rcp2.6/                  2040 SSP1-2.6
│   ├── 2040-rcp4.5/                  2040 SSP2-4.5
│   ├── 2040-rcp8.5/                  2040 SSP5-8.5
│   ├── 2060-rcp2.6/                  2060 SSP1-2.6
│   ├── 2060-rcp4.5/                  2060 SSP2-4.5
│   └── 2060-rcp8.5/                  2060 SSP5-8.5
│
├── figure6/                          Figure 6 input data (127 MB)
│   ├── {city}_building_energy.xlsx    Building annual cooling energy (6 cities)
│   ├── energy_capacity_summary.csv    Energy + capacity summary
│   ├── per_capita_hours_summary.csv   Per-capita discomfort hours summary
│   ├── {pinyin}_curves.csv            GW load curve caches (6 cities)
│   └── 省会城市24h电力负荷.xlsx        Provincial 24h grid load data
│
├── shape_coefficient/                Building shape coefficient (32 MB)
│   ├── 广州市建筑体型系数_详细版.xlsx
│   └── 深圳市建筑体型系数_详细版.xlsx
│
├── cluster_maps/                     Building prototype cluster assignments (6 cities)
│   ├── cluster_110000_北京市.csv
│   ├── cluster_310000_上海市.csv
│   ├── cluster_420100_武汉市.csv
│   ├── cluster_440100_广州市.csv
│   ├── cluster_440300_深圳市.csv
│   └── cluster_350200_厦门市.csv
│
├── population_csv/                   Anonymised building population CSV (12 files)
│   ├── 110000_Beijing_full.csv       8 columns: BuildingID, Area, landUseTyp, Height, Age, popNum_2, age0_2, age65abv_2
│   ├── 110000_Beijing_residential.csv
│   ├── 310000_Shanghai_full.csv
│   ├── 310000_Shanghai_residential.csv
│   ├── 420000_Wuhan_full.csv
│   ├── 420000_Wuhan_residential.csv
│   ├── 440100_Guangzhou_full.csv
│   ├── 440100_Guangzhou_residential.csv
│   ├── 440300_Shenzhen_full.csv
│   ├── 440300_Shenzhen_residential.csv
│   ├── 350200_Xiamen_full.csv
│   └── 350200_Xiamen_residential.csv
│
├── pipeline_outputs/                 Pipeline outputs (506 MB)
│   ├── zhibiao/                      Per-building per-capita discomfort hours (6 cities)
│   ├── pop_lookup/                   Population lookup tables (6 cities)
│   ├── hourly_set/                   Per-city per-scenario hourly SET Excel (79 files)
│   │   ├── Baseline/                 {pinyin}_2020_HourlyStats.xlsx
│   │   └── Future/                   {pinyin}_20{40,60}-rcp{2.6,4.5,8.5}_HourlyStats.xlsx
│   ├── per_capita_hours/             Summary CSV
│   └── pivot_tables/                 Cross-comparison Excel
│
├── GeiMingHao_27Degree/              EnergyPlus indoor environment CSV — Shenzhen only (446 MB)
│   └── GeiMingHao_IndoorEnv/
│       ├── Baseline_2020/shen1zhen4shi4/2020/     149 MB
│       └── Fixed_capacity/shen1zhen4shi4/
│           ├── 2040-rcp8.5/                       149 MB
│           └── 2060-rcp8.5/                       149 MB
│
├── beijing_building_data/            Beijing building SHP + attributes CSV (97 MB)
│   ├── Beijing_buildings.{shp,shx,dbf,prj,cpg}
│   ├── Beijing_building_attributes_full.csv
│   └── Beijing_building_attributes_residential.csv
│
├── beijing_weibo/                    Anonymised Weibo check-in data
│   └── data.csv                       Data dictionary in file header
│
├── china_county_shp/                 Standard map — county boundaries (审图号 GS(2024)0650)
│   └── 中国_县_Albers.{shp,shx,dbf,prj,cpg}
│
├── china_city_boundary_shp/          City-level administrative boundaries
│   └── city.{shp,shx,dbf,prj,cpg}
│
├── china_city_shp/                   Standard map — city boundaries (市)
│   └── 中国_市_Albers.{shp,shx,dbf,prj,cpg}
│
└── china_ninedash_shp/               Standard map — nine-dash line (九段线)
    └── 九段线_Albers.{shp,shx,dbf,prj,cpg}
```

## File descriptions

### EPW weather files (`epw/`)

Standard EnergyPlus Weather format (.epw). Naming convention: `{city_code}_{pinyin}_{scenario}.epw`. Example: `110000_bei3jing1shi4_2020.epw`.

| Field | Description |
|-------|-------------|
| Column 7 (Dry-bulb temperature, °C) | Used for SET computation |
| Column 9 (Atmospheric pressure, Pa) | Used for Magnus-formula RH calculation |

### Figure 6 data (`figure6/`)

**Building energy Excel files** (`{city}_building_energy.xlsx`): One file per city. Columns include `LandNum`, `Cluster`, `Fnum_x`, `Total_Area_m2`, and energy columns (`S{n}_{year}_{scenario}_kWh`). Used by `figure6-a.py` and `figure6-b.py`.

**Energy capacity summary** (`energy_capacity_summary.csv`): Aggregated per-building energy and capacity from EnergyPlus simulations. Used by `figure6-b.py`.

**Load curve CSVs** (`{pinyin}_curves.csv`): City-wide GW-scale cooling load curves by date and strategy. Columns: `Date`, `Strategy` (S1–S5), `H0`–`H23` (hourly GW values). Used by `figure6-c.py`.

**Grid load data** (`省会城市24h电力负荷.xlsx`): Provincial 24-hour electricity load profiles used as grey reference lines in Figure 6-c.

### Shape coefficient (`shape_coefficient/`)

Building shape coefficient (体型系数) data for Guangzhou and Shenzhen. Columns: building usage type (`建筑用途(usage)`), footprint area, total height, shape coefficient, building age. Used by `figure3-c.py` — filters `Residential_1/2/3` only.

### Cluster maps (`cluster_maps/`)

CSV files mapping each building (`BuildingID`) to its prototype cluster attributes: `Cluster` (building type cluster), `LandNum` (0=low-rise, 1=mid-rise, 2=high-rise), `Fnum` (number of storeys), `landUseTyp` (land use type). Used for per-capita population weighting and building type counting.

### Population CSV (`population_csv/`)

Anonymised building-level population data extracted from original SHP attributes. **8 columns**: `BuildingID`, `Area`, `landUseTyp`, `Height`, `Age`, `popNum_2` (total population), `age0_2` (age 0–14), `age65abv_2` (age 65+). Two variants per city: `_full.csv` (all buildings) and `_residential.csv` (residential only). Used by `figure2-b.py` for weighted per-capita discomfort hour calculation.

### Pipeline outputs (`pipeline_outputs/`)

Intermediate products generated by `code/run_all.py`:

- **`hourly_set/`**: Per-building per-storey hourly discomfort hour Excel files, organised by Baseline (6 files) and Future (37 files). Also contains `summary_uncomfortable_hours.csv` (figure4-l input).
- **`zhibiao/`**: Per-building per-capita discomfort hours aggregated by year (figure5 / figure2-d input).
- **`pop_lookup/`**: Building-level population lookup tables (figure5 input).

### EnergyPlus CSVs (`GeiMingHao_27Degree/`)

Raw EnergyPlus indoor environment simulation output for Shenzhen only (3 scenarios). Each CSV contains hourly Zone Air Temperature, Mean Radiant Temperature, and Humidity Ratio for every storey of a prototype building. Used exclusively by `figure4-r.py` for online SET re-computation with day/night-specific MET/CLO.

### Standard map shapefiles

Four layers of China standard map boundary shapefiles in Albers projection (审图号 GS(2024)0650):

| Directory | Layer | Used by |
|-----------|-------|---------|
| `china_county_shp/` | County-level boundaries | Figures 2-c, 2-d, 5 |
| `china_city_boundary_shp/` | City-level administrative boundaries | Figures 2-d, 5 |
| `china_city_shp/` | City-level boundaries (市) | fig2-1 |
| `china_ninedash_shp/` | Nine-dash line (九段线) | fig2-1 |

### Weibo data (`beijing_weibo/`)

**Privacy notice**: All user identifiers, screen names, addresses, and post content (except one reference row) have been replaced with `***`. Only the following fields are preserved: `经度` (Longitude), `纬度` (Latitude), `地点类型` (Place Type). Used in Figure 2-c for spatial validation.
