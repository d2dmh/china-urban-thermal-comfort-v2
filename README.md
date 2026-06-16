# Urban Residential Nighttime Thermal Comfort under Climate Change

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20691709.svg)](https://doi.org/10.5281/zenodo.20691709)

The code and data in this repository support the **peer review** of the manuscript:

**"Climate warming not only amplifies cooling demand but also undermines sleep comfort"**

## Purpose

This repository provides all code and external data needed to reproduce the figures and computational workflow described in the paper. Researchers can verify the SET (Standard Effective Temperature) computation pipeline, inspect per-capita discomfort hour calculations for 6 Chinese cities under 7 climate scenarios, and regenerate all figures (2–6).

## Online resources

- **Zenodo data package**: Full external inputs — EPW weather files, building energy data, shape coefficients, standard China maps, anonymised Weibo check-ins, cluster mappings, population CSVs, pipeline outputs, and EnergyPlus indoor environment CSVs (Shenzhen). See [https://doi.org/10.5281/zenodo.20691709](https://doi.org/10.5281/zenodo.20691709).

## Quick start

```bash
git clone <this-repo>
cd thermal_comfort_analysis
pip install -r requirements.txt
```

Download **Zenodo data** and extract into `input/`. Then generate all figures:

```bash
python figure/fig2-1地图-建筑气候区划.py
python figure/figure2-b-去除文字.py
python figure/figure2-c_public.py
python figure/figure2-d_public.py
python figure/figure3-a.py
python figure/figure3-b.py
python figure/figure3-c.py
python figure/figure4-l.py
python figure/figure4-r.py
python figure/figure5_public.py
python figure/figure6-a.py
python figure/figure6-b.py
python figure/figure6-c.py
```

Output figures go to `output/figure{2,3,4,5,6}/`.

## Repository layout

```
thermal_comfort_analysis/
├── code/                    # Main pipeline (15 .py files)
│   ├── config/              # Global parameters + path config
│   ├── core/                # SET, EPW, RH core computation
│   ├── step1_compute_set.py
│   ├── step2_pivot_tables.py
│   ├── step3_energy_capacity.py
│   ├── step4_citywide_load_curves.py
│   └── run_all.py           # One-click: Step 1→2→3→4
├── figure/                   # 16 plotting scripts (Figures 2–6)
├── input/                    # External data (download from Zenodo)
├── output/                   # Generated figures (at runtime)
├── CLAUDE.md                 # Project developer guide
└── README.md
```

## Pipeline

```bash
python code/run_all.py
```

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `step1_compute_set.py` | Compute per-building per-storey hourly SET, aggregate per-capita discomfort hours |
| 2 | `step2_pivot_tables.py` | Cross-comparison pivot tables |
| 3 | `step3_energy_capacity.py` | Building energy, cooling capacity, peak load |
| 4 | `step4_citywide_load_curves.py` | City-wide GW-scale cooling load curves |

## Figure scripts

### Figure 2 — Baseline context

| Script | Output | Public |
|--------|--------|--------|
| `fig2-1地图-建筑气候区划.py` | China building climate zone map | ✓ |
| `figure2-b-去除文字.py` | 6-city per-capita discomfort grouped bar | ✓ |
| `figure2-c.py` / `figure2-c_public.py` | Beijing Weibo heat-complaint overlay | `_public.py` |
| `figure2-d.py` / `figure2-d_public.py` | 6-city 3D discomfort heat maps | `_public.py` |

### Figure 3 — Climate context

| Script | Output |
|--------|--------|
| `figure3-a.py` | GZ vs SZ annual mean temperature (7 scenarios) |
| `figure3-b.py` | GZ vs SZ floating-bar per-capita discomfort hours |
| `figure3-c.py` | Building shape coefficient KDE comparison |

### Figure 4 — Building-scale validation

| Script | Output |
|--------|--------|
| `figure4-l.py` | Vertical thermal disparity — 3 Shenzhen archetypes |
| `figure4-r.py` | 24h top-floor vs non-top-floor discomfort profiles |

### Figure 5 — City-scale mapping

| Script | Output | Public |
|--------|--------|--------|
| `figure5.py` / `figure5_public.py` | 6-city 2×2 bivariate heat + vulnerability maps | `_public.py` |

### Figure 6 — Strategy trade-off

| Script | Output |
|--------|--------|
| `figure6-a.py` | Strategy trade-off scatter: energy (TWh) vs discomfort (h) |
| `figure6-b.py` | Cooling capacity density raincloud plots (RCP 8.5) |
| `figure6-c.py` | Typical midsummer city-wide cooling load curves |

## Input data (`input/`)

| Directory | Size | Contents |
|-----------|------|----------|
| `epw/` | 65 MB | 42 EPW weather files (6 cities × 7 scenarios) |
| `figure6/` | 127 MB | Building energy Excel ×6, energy capacity CSV, per-capita hours CSV, GW load curve CSVs ×6, grid load shape |
| `shape_coefficient/` | 32 MB | GZ + SZ building shape coefficient Excel |
| `cluster_maps/` | 67 MB | Building prototype cluster assignment CSV ×6 |
| `population_csv/` | 122 MB | Anonymised building population CSV ×12 (full + residential; 8 columns: BuildingID, Area, landUseTyp, Height, Age, popNum_2, age0_2, age65abv_2) |
| `pipeline_outputs/` | 506 MB | Pipeline outputs — SET hourly Excel (79 files), zhibiao CSV ×6, pop_lookup CSV ×6, per-capita summary CSV |
| `GeiMingHao_27Degree/` | 446 MB | Shenzhen EnergyPlus indoor environment CSV (figure4-r only) |
| `beijing_building_data/` | 97 MB | Beijing building SHP + anonymised attributes CSV |
| `beijing_weibo/` | 328 KB | Anonymised Sina Weibo summer check-in data (Beijing) |
| `china_county_shp/` | 7.2 MB | China county boundaries (审图号 GS(2024)0650) |
| `china_city_shp/` | 3.0 MB | China city boundaries |
| `china_city_boundary_shp/` | 31 MB | City-level administrative boundaries |
| `china_ninedash_shp/` | 16 KB | Nine-dash line (九段线) |

## Reproducibility notes

- All paths are **repo-relative** (`os.path.join(PROJECT_ROOT, "input", ...)`). Works on any OS.
- `figureX_public.py` scripts use pre-computed **GeoJSON grid data** under `figure/*_grid_data/` — no private SHP needed.
- `figureX.py` originals require private SHP layers (author use only).
- Weibo data is anonymised: all fields except longitude, latitude, venue type replaced with `***`.

## Dependencies

| Package | Minimum | Purpose |
|---------|---------|---------|
| `pythermalcomfort` | 2.8 | SET computation |
| `numpy` | 1.24 | Array computation |
| `pandas` | 1.5 | CSV / Excel I/O |
| `matplotlib` | 3.6 | Plotting |
| `seaborn` | 0.12 | Statistical plots |
| `geopandas` | 0.12 | GIS (figure 2-c/2-d/5) |
| `shapely` | 2.0 | Geometry operations |
| `scikit-learn` | 1.2 | K-means (figure 6-c) |
| `scipy` | 1.10 | KDE / stats (figure 6-b) |
| `openpyxl` | 3.0 | Excel I/O |

## Citing

> *[Paper citation — TBD after publication]*

## License

*[TBD]*
