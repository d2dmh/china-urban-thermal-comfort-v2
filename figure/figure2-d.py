# ==========================================
# 6城市 × 3情形 3D叠层批处理
# 纯热不适数据 + 3D市中心红星 + 自定义离散分段图例，figure2
# ==========================================

import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import os
import pandas as pd
import shapely.affinity
from shapely.geometry import Polygon, Point
import matplotlib.colors as mcolors
import matplotlib.font_manager as fm
import warnings

warnings.filterwarnings("ignore")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figure2d_output")

# ==================== 0. 基础配置 ====================
_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COUNTY_SHP_PATH = os.path.join(_PROJ, "data", "other data", "china_county_shp", "中国_县_Albers.shp")
CITY_BOUNDS_SHP = os.path.join(_PROJ, "data", "other data", "china_city_boundary_shp", "city.shp")

cities_info = {
    "北京市": {
        "shp": r"E:\cc data\github\thermal_comfort_analysis\data\other data\population\110000Beijing_shp\T110000_Beijing_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\北京市_zhibiao_result_all.csv"
    },
    "上海市": {
        "shp": r"E:\cc data\thermal_comfort_analysis\data\other data\population\310000上海市\T310000_上海市_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\上海市_zhibiao_result_all.csv"
    },
    "广州市": {
        "shp": r"E:\cc data\thermal_comfort_analysis\data\other data\population\440000广东省\T440100_广州市_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\广州市_zhibiao_result_all.csv"
    },
    "深圳市": {
        "shp": r"E:\cc data\thermal_comfort_analysis\data\other data\population\440000广东省\T440300_深圳市_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\深圳市_zhibiao_result_all.csv"
    },
    "武汉市": {
        "shp": r"E:\cc data\thermal_comfort_analysis\data\other data\population\420000湖北省\T420100_武汉市_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\武汉市_zhibiao_result_all.csv"
    },
    "厦门市": {
        "shp": r"E:\cc data\thermal_comfort_analysis\data\other data\population\350000福建省\T350200_厦门市_building_pop.shp",
        "heat": r"E:\GeiMingHao_all\GeiMingHao\zhibiao\厦门市_zhibiao_result_all.csv"
    }
}

HEAT_COLS = ['BuildingID', '人均受灾小时数_2020', '人均受灾小时数_2040-rcp8.5', '人均受灾小时数_2060-rcp8.5']


def load_table(file_path, usecols):
    """Load CSV or Excel with specified columns."""
    if file_path.endswith('.csv'):
        return pd.read_csv(file_path, usecols=usecols)
    elif file_path.endswith('.xls') or file_path.endswith('.xlsx'):
        return pd.read_excel(file_path, usecols=usecols)
    else:
        raise ValueError(f"Unsupported file format: {file_path}")


def create_clipped_grid(boundary_gdf, grid_size):
    """Create a regular grid clipped to a boundary geometry."""
    xmin, ymin, xmax, ymax = boundary_gdf.total_bounds
    cols = list(np.arange(xmin, xmax + grid_size, grid_size))
    rows = list(np.arange(ymin, ymax + grid_size, grid_size))
    polygons = []
    for x in cols[:-1]:
        for y in rows[:-1]:
            polygons.append(Polygon([(x, y), (x + grid_size, y), (x + grid_size, y + grid_size), (x, y + grid_size)]))
    grid = gpd.GeoDataFrame({'geometry': polygons}, crs=boundary_gdf.crs)
    return gpd.clip(grid, boundary_gdf) 

CITY_CENTERS_WGS84 = {
    '北京市': (116.4074, 39.9042),
    '武汉市': (114.3055, 30.5928),
    '上海市': (121.4737, 31.2304),
    '广州市': (113.2644, 23.1291),
    '深圳市': (114.0596, 22.5429),
    '厦门市': (118.0894, 24.4798)
}

CITY_SPECIFIC_PARAMS = {
    "北京市": {"grid_sz": 1000, "min_grids": 150, "density": 0.15},
    "上海市": {"grid_sz": 1000, "min_grids": 150, "density": 0.15},
    "广州市": {"grid_sz": 1000, "min_grids": 100, "density": 0.10},
    "深圳市": {"grid_sz": 500,  "min_grids": 200, "density": 0.15}, 
    "厦门市": {"grid_sz": 500,  "min_grids": 200, "density": 0.15},
    "武汉市": {"grid_sz": 1000, "min_grids": 150, "density": 0.15},
}

# 🌟 新增：从图片提取的自定义离散颜色与标签
CUSTOM_COLORS = ['#3850A1', '#7EA8C3', '#F7F4C3', '#EBB97F', '#D56B52', '#931832']
CUSTOM_LABELS = ['0 - 5', '5 - 15', '15 - 30', '30 - 70', '70 - 140', '>140']

def get_discrete_color(val):
    if pd.isna(val) or val <= 5:
        return CUSTOM_COLORS[0]
    elif val <= 15:
        return CUSTOM_COLORS[1]
    elif val <= 30:
        return CUSTOM_COLORS[2]
    elif val <= 70:
        return CUSTOM_COLORS[3]
    elif val <= 140:
        return CUSTOM_COLORS[4]
    else:
        return CUSTOM_COLORS[5]

# ==================== 1. 严格复刻 3D 变换函数与比例尺 ====================
def transform_to_3d_strict(geom, z_offset=0):
    if geom is None or geom.is_empty: return geom
    tilt_z_deg = 60  
    rot_flat_deg = 0
    rx, rz = np.radians(tilt_z_deg), np.radians(rot_flat_deg)
    
    a, b = np.cos(rz), -np.sin(rz)
    d, e = np.sin(rz) * np.cos(rx), np.cos(rz) * np.cos(rx)
    xoff, yoff = 0, -z_offset 
    
    return shapely.affinity.affine_transform(geom, [a, b, d, e, xoff, yoff])

def apply_3d_strict(gdf, z_offset=0):
    if gdf is None or gdf.empty: return gdf
    gdf_3d = gdf.copy()
    gdf_3d['geometry'] = gdf_3d.geometry.apply(lambda geom: transform_to_3d_strict(geom, z_offset))
    return gdf_3d

# 🌟 新增：针对 EPSG:3857 的自适应比例尺函数
def add_scalebar(ax, lat):
    plt.draw() # 刷新画布以获取真实坐标域
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()

    # 在 EPSG:3857 中，1地图单位 = 1真实米 / cos(纬度)
    # 所以：真实公里数 = 地图单位长度 * cos(纬度) / 1000
    total_map_units = xmax - xmin
    total_true_km = (total_map_units * np.cos(np.radians(lat))) / 1000.0
    
    # 取画面总宽度的 20% 左右作为期望的比例尺长度
    target_km = total_true_km * 0.2
    
    # 归整到好看的刻度值
    if target_km <= 5: length_km = 2
    elif target_km <= 15: length_km = 5
    elif target_km <= 35: length_km = 10
    elif target_km <= 75: length_km = 20
    else: length_km = 50
    
    # 将真实公里数反推回 EPSG:3857 下的地图单位长度
    width_map_units = (length_km * 1000.0) / np.cos(np.radians(lat))
    
    # 放置在图表左下角
    x0 = xmin + (xmax - xmin) * 0.05
    y0 = ymin + (ymax - ymin) * 0.05
    tick_height = (ymax - ymin) * 0.015
    
    line_color = 'black'
    lw = 2
    z_layer = 100
    
    # 绘制基础线与刻度
    ax.plot([x0, x0 + width_map_units], [y0, y0], color=line_color, lw=lw, zorder=z_layer)
    ax.plot([x0, x0], [y0, y0 + tick_height], color=line_color, lw=lw, zorder=z_layer)
    ax.plot([x0 + width_map_units / 2, x0 + width_map_units / 2], [y0, y0 + tick_height], color=line_color, lw=lw, zorder=z_layer)
    ax.plot([x0 + width_map_units, x0 + width_map_units], [y0, y0 + tick_height], color=line_color, lw=lw, zorder=z_layer)
    
    # 添加文字
    font_prop = fm.FontProperties(size=14)
    ax.text(x0, y0 + tick_height * 1.5, '0', ha='center', va='bottom', color=line_color, fontproperties=font_prop, zorder=z_layer)
    ax.text(x0 + width_map_units, y0 + tick_height * 1.5, f'{length_km} km', ha='center', va='bottom', color=line_color, fontproperties=font_prop, zorder=z_layer)

# ==================== 2. 批处理主循环 ====================
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

print("正在加载底图...")
counties_raw = gpd.read_file(COUNTY_SHP_PATH)
counties_raw['area_km2'] = counties_raw.geometry.area / 1e6
counties_all = counties_raw.to_crs('EPSG:3857')

for city_name, params in CITY_SPECIFIC_PARAMS.items():
    if city_name not in cities_info: continue
    paths = cities_info[city_name]
    grid_sz, m_grids, m_dens = params["grid_sz"], params["min_grids"], params["density"]
    
    print(f"\n>> Plotting 3D: {city_name}")
    
    try:
        # --- A. 数据融合与网格化 ---
        buildings = gpd.read_file(paths['shp'])
        heat_df = load_table(paths['heat'], HEAT_COLS)
        
        for df in [buildings, heat_df]:
            df['BuildingID'] = df['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        gdf_merged = buildings.merge(heat_df, on='BuildingID', how='inner').to_crs('EPSG:3857')
        
        china_cities = gpd.read_file(CITY_BOUNDS_SHP)
        city_mask = china_cities[china_cities.astype(str).apply(lambda x: x.str.contains(city_name[:2])).any(axis=1)]
        city_limit = city_mask.iloc[[0]].to_crs('EPSG:3857') if not city_mask.empty else None
        
        grid_base = create_clipped_grid(city_limit if city_limit is not None else gdf_merged, grid_size=grid_sz)
        joined = gpd.sjoin(gdf_merged.copy().set_geometry(gdf_merged.centroid), grid_base, how='left', predicate='within')
        
        grid_stats = joined.groupby('index_right').agg({
            '人均受灾小时数_2020': 'mean', 
            '人均受灾小时数_2040-rcp8.5': 'mean', 
            '人均受灾小时数_2060-rcp8.5': 'mean'
        }).reset_index()
        grid_city = grid_base.merge(grid_stats, left_index=True, right_on='index_right', how='right').dropna()

        # --- B. 核心行政边界筛选 ---
        pts = gpd.GeoDataFrame(geometry=grid_city.centroid, crs=grid_city.crs)
        joined_counties = gpd.sjoin(pts, counties_all, how='inner', predicate='intersects')
        counts = joined_counties['index_right'].value_counts().rename('grid_count')
        curr_counties = counties_all.copy().merge(counts, left_index=True, right_index=True, how='left').fillna(0)
        curr_counties['density_ratio'] = (curr_counties['grid_count'] * ((grid_sz**2)/1e6)) / curr_counties['area_km2']
        core_counties = curr_counties[(curr_counties['grid_count'] >= m_grids) | (curr_counties['density_ratio'] >= m_dens)]
        
        core_hull = gpd.GeoDataFrame(geometry=[core_counties.unary_union], crs=grid_city.crs)
        core_hull['geometry'] = core_hull['geometry'].apply(lambda g: Polygon(g.exterior) if g.geom_type == 'Polygon' else g)
        grid_core = gpd.clip(grid_city, core_hull)

        # --- C. 计算并变换市中心五角星 ---
        lon, lat = CITY_CENTERS_WGS84[city_name]
        star_point_3857 = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs("EPSG:3857")[0]
        star_3d = transform_to_3d_strict(star_point_3857, z_offset=0)

        # --- D. 绘图 (3D 叠层 + 五角星) ---
        fig, axes = plt.subplots(1, 4, figsize=(28, 10), gridspec_kw={'width_ratios': [1, 1, 1, 0.7]}, facecolor='none')
        fig.patch.set_alpha(0.0)
        plt.subplots_adjust(bottom=0.15, wspace=0.05) 
        
        scenarios = [('2020', '2020 现状'), ('2040-rcp8.5', '2040 RCP8.5'), ('2060-rcp8.5', '2060 RCP8.5')]
        minx, miny, maxx, maxy = core_hull.total_bounds
        dynamic_thickness = (maxy - miny) * 0.03

        for i, (yr, ttl) in enumerate(scenarios):
            ax = axes[i]
            ax.set_facecolor('none')
            ax.set_axis_off()

            # 1. 底座阴影
            for z in np.linspace(dynamic_thickness, 0, 15):
                apply_3d_strict(core_hull, z_offset=z).plot(ax=ax, facecolor='#cccccc', edgecolor='none', zorder=1)

            # 2. 顶层底盘
            hull_top = apply_3d_strict(core_hull, z_offset=0)
            hull_top.plot(ax=ax, facecolor='#F7F7F7', edgecolor='none', zorder=2)

            # 3. 应用离散色彩分类
            col_name = f'人均受灾小时数_{yr}'
            grid_core[f'color_{yr}'] = grid_core[col_name].apply(get_discrete_color)
            grid_3d = apply_3d_strict(grid_core, z_offset=0)
            grid_3d.plot(ax=ax, color=grid_3d[f'color_{yr}'], edgecolor='none', zorder=3)
            
            # 4. 行政边界线
            apply_3d_strict(core_counties, z_offset=0).boundary.plot(ax=ax, color='#888888', linewidth=0.6, zorder=4)
            hull_top.boundary.plot(ax=ax, color='#666666', linewidth=1.2, zorder=5)

            # 5. 绘制红星 
            ax.scatter(star_3d.x, star_3d.y, marker='*', color='red', edgecolor='white', s=700, zorder=15, label="市中心")

            ax.set_title(f"【{city_name}】 {ttl}", fontsize=20, pad=20, fontweight='bold')
            viz_bounds = hull_top.total_bounds
            ax.set_xlim(viz_bounds[0] - 5000, viz_bounds[2] + 5000)
            ax.set_ylim(viz_bounds[1] - 10000, viz_bounds[3] + 5000)

            # 🌟 新增：由于 X 轴、Y 轴被固定了限制，调用我们的真实物理比例尺函数
            add_scalebar(ax, lat)

        # 🌟 核心：构造完美复刻的离散型全局横向图例
        # 使用 0 到 6 的线性映射，确保 6 个颜色块平分空间
        cmap_discrete = mcolors.ListedColormap(CUSTOM_COLORS)
        norm_discrete = mcolors.Normalize(vmin=0, vmax=len(CUSTOM_COLORS))
        sm = plt.cm.ScalarMappable(cmap=cmap_discrete, norm=norm_discrete)
        sm._A = []  
        
        cbar_ax = fig.add_axes([0.25, 0.08, 0.4, 0.03]) 
        cbar = fig.colorbar(sm, cax=cbar_ax, orientation='horizontal')
        
        # 将刻度对齐到每个色块的中心点 (0.5, 1.5, 2.5...)
        ticks_loc = np.arange(len(CUSTOM_COLORS)) + 0.5
        cbar.set_ticks(ticks_loc)
        cbar.set_ticklabels(CUSTOM_LABELS)
        
        # 隐藏小刻度线，让它看起来更像原图的平滑色块
        cbar.ax.tick_params(labelsize=15, length=0) 
        
        # 自定义图例标签
        cbar.set_label('installed capacity [10³m³h⁻¹]', fontsize=16, labelpad=10)

        # 6. 索引图
        ax_idx = axes[3]
        idx_pts = gpd.GeoDataFrame(geometry=counties_all.centroid, crs=counties_all.crs)
        idx_match = gpd.sjoin(idx_pts, city_limit[['geometry']], how='inner', predicate='within')
        all_city_counties = counties_all.loc[idx_match.index]
        all_city_counties.plot(ax=ax_idx, color='#EEEEEE', edgecolor='#B0B0B0', linewidth=0.5)
        core_counties.plot(ax=ax_idx, color='#E67E22', alpha=0.8)
        core_counties.boundary.plot(ax=ax_idx, color='#C0392B', linewidth=0.5)
        core_hull.boundary.plot(ax=ax_idx, color='#D35400', linewidth=1.0)
        ax_idx.set_title("区域索引 (平面)", fontsize=18)
        ax_idx.set_axis_off()

        # 保存并直接在 Jupyter 内显示图像
        save_path = os.path.join(OUTPUT_DIR, f"{city_name}_3D_Heat_Discrete_600dpi.png")
        plt.savefig(save_path, dpi=600, bbox_inches='tight', transparent=True)
        
        plt.show() 
        plt.close(fig) 

    except Exception as e:
        print(f"[ERROR] {city_name}: {e}")

print("\n[OK] All cities processed.")