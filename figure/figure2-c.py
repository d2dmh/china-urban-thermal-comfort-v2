import os
import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.gridspec import GridSpec
from shapely.geometry import Polygon, Point
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
import matplotlib.patches as mpatches

warnings.filterwarnings("ignore")

# ==============================================================================
# 🎯 核心配置区
# ==============================================================================
class CONFIG:
    # ---------------- 1. 路径与环境设置 ----------------
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figure2c_output")
    
    weibo_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "other data", "beijing_weibo", "data.csv")
    sim_shp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "other data", "population", "110000Beijing_shp", "T110000_Beijing_building_pop.shp")
    sim_csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "input", "pipeline_outputs", "zhibiao", "北京市_zhibiao_result_all.csv")
    shp_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "other data", "china_county_shp", "中国_县_Albers.shp")
    
    # ---------------- 2. 版面与排版比例 ----------------
    fig_size = (15, 15)         # 画板整体大小
    dpi = 600                   # 输出图片清晰度
    main_to_margin_ratio = 9    # 主图与边缘图的比例

    # ---------------- 3. 主图: 底图与坐标点参数 ----------------
    map_bg_color = '#F7F7F7'    
    map_edge_color = '#D0D0D0'  
    map_edge_width = 0.8        

    # --- 自定义仿真热度图 Colormap ---
    sim_custom_colors = ["#F7F4C3", "#931832"]
    sim_custom_cmap = LinearSegmentedColormap.from_list("sim_custom", sim_custom_colors)
    sim_alpha = 0.85            

    # --- 微博散点配色 ---
    weibo_color = '#475894'     
    weibo_size = 18             
    weibo_alpha =0.9          
    weibo_edge_color = 'white'  
    weibo_edge_width = 0.2      

    star_color = '#FF0000'      
    star_size = 1200             
    lon_bj, lat_bj = 116.397, 39.907 

    # ---------------- 4. 边缘分布图 (KDE) 参数与配色 ----------------
    kde_sim_color = '#931832'   
    kde_sim_alpha = 0.2         

    kde_weibo_color = '#475894' 
    kde_weibo_alpha = 0.2       

# ==============================================================================

# Initialize output path
if not os.path.exists(CONFIG.output_dir):
    os.makedirs(CONFIG.output_dir)

# ==========================================
# 1. 数据读取、清洗与网格化
# ==========================================
print("正在读取并清洗北京微博点数据...")
df_weibo = pd.read_csv(CONFIG.weibo_csv, encoding='utf-8')
df_weibo = df_weibo.dropna(subset=['经度', '纬度', '地点类型', '用户昵称'])
df_weibo = df_weibo[df_weibo['地点类型'].str.contains('住宅', na=False)]
df_weibo = df_weibo.drop_duplicates(subset=['用户昵称'], keep='first')
df_weibo['经度'] = df_weibo['经度'].astype(float)
df_weibo['纬度'] = df_weibo['纬度'].astype(float)

pt_counts = df_weibo.groupby(['经度', '纬度']).size().reset_index(name='pt_count')
pt_threshold = pt_counts['pt_count'].quantile(0.997)
valid_pts = pt_counts[pt_counts['pt_count'] <= pt_threshold]
df_weibo = df_weibo.merge(valid_pts[['经度', '纬度']], on=['经度', '纬度'], how='inner')

gdf_weibo = gpd.GeoDataFrame(
    df_weibo, geometry=[Point(xy) for xy in zip(df_weibo['经度'], df_weibo['纬度'])], crs="EPSG:4326"
).to_crs("EPSG:3857")

print("正在读取全国底图并裁剪出北京城区...")
gdf_china = gpd.read_file(CONFIG.shp_base).to_crs("EPSG:3857")
pt_bounds = gdf_weibo.total_bounds
crop_margin = 15000 
beijing_base = gdf_china.cx[pt_bounds[0]-crop_margin:pt_bounds[2]+crop_margin, 
                            pt_bounds[1]-crop_margin:pt_bounds[3]+crop_margin]

print("正在读取并清洗北京仿真指标数据 (使用 3-Sigma 剔除异常值)...")
buildings = gpd.read_file(CONFIG.sim_shp_path)
heat_df = pd.read_csv(CONFIG.sim_csv_path, encoding='utf-8') 

target_col = '人均受灾小时数_2020'

# 计算均值和标准差
mean_val = heat_df[target_col].mean()
std_val = heat_df[target_col].std()

# 定义 3-Sigma 的上限和下限
lower_bound = mean_val - 3 * std_val
upper_bound = mean_val + 3 * std_val

print(f"  -> 数据均值: {mean_val:.2f}, 标准差: {std_val:.2f}")
print(f"  -> 3-Sigma 有效范围: [{lower_bound:.2f}, {upper_bound:.2f}]")

# 剔除异常值 (仅保留在 3-Sigma 范围内的数据)
heat_df = heat_df[(heat_df[target_col] >= lower_bound) & (heat_df[target_col] <= upper_bound)]

buildings['BuildingID'] = buildings['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
heat_df['BuildingID'] = heat_df['BuildingID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
gdf_sim = buildings.merge(heat_df, on='BuildingID', how='inner').to_crs("EPSG:3857")

gdf_sim_pts = gdf_sim.copy()
gdf_sim_pts['geometry'] = gdf_sim_pts.centroid

print("正在生成统一 750m 网格并进行双向聚合...")
bounds = gdf_weibo.total_bounds 
margin = 3000
xmin, ymin, xmax, ymax = bounds[0]-margin, bounds[1]-margin, bounds[2]+margin, bounds[3]+margin
grid_size = 750 
x_coords = np.arange(xmin, xmax, grid_size)
y_coords = np.arange(ymin, ymax, grid_size)
polygons = [Polygon([(x, y), (x + grid_size, y), (x + grid_size, y + grid_size), (x, y + grid_size)]) 
            for x in x_coords for y in y_coords]
grid_gdf = gpd.GeoDataFrame({'grid_id': range(len(polygons))}, geometry=polygons, crs="EPSG:3857")
grid_gdf = gpd.sjoin(grid_gdf, beijing_base[['geometry']], how='inner').drop_duplicates(subset=['grid_id'])[['grid_id', 'geometry']]

weibo_join = gpd.sjoin(gdf_weibo, grid_gdf, how='inner')
weibo_counts = weibo_join.groupby('grid_id').size().reset_index(name='weibo_count')

sim_join = gpd.sjoin(gdf_sim_pts, grid_gdf, how='inner')
sim_means = sim_join.groupby('grid_id')[target_col].mean().reset_index(name='sim_risk')

grid_merged = grid_gdf.merge(weibo_counts, on='grid_id', how='left').merge(sim_means, on='grid_id', how='left')
grid_merged['weibo_count'] = grid_merged['weibo_count'].fillna(0)
grid_merged['sim_risk'] = grid_merged['sim_risk'].fillna(0)

# ==========================================
# 2. 准备绘图数据 
# ==========================================
sim_grids = grid_merged[grid_merged['sim_risk'] > 0]
data_bounds = sim_grids.total_bounds
v_margin = 2000 
xlims = (data_bounds[0] - v_margin, data_bounds[2] + v_margin)
ylims = (data_bounds[1] - v_margin, data_bounds[3] + v_margin)

weibo_x = gdf_weibo.geometry.x
weibo_y = gdf_weibo.geometry.y

sim_centroids = sim_grids.geometry.centroid
sim_x = sim_centroids.x
sim_y = sim_centroids.y
sim_weights = sim_grids['sim_risk']

# ==========================================
# 3. 渲染主画板
# ==========================================
print("渲染最终版画板...")
fig = plt.figure(figsize=CONFIG.fig_size, dpi=CONFIG.dpi, facecolor='none') 

gs = GridSpec(2, 2, 
              width_ratios=[CONFIG.main_to_margin_ratio, 1], 
              height_ratios=[1, CONFIG.main_to_margin_ratio], 
              wspace=0.03, hspace=0.03)

# ---- 3.1 顶部边缘图 ----
ax_top = fig.add_subplot(gs[0, 0])
ax_top.patch.set_facecolor('none')
sns.kdeplot(x=sim_x, weights=sim_weights, ax=ax_top, fill=True, color=CONFIG.kde_sim_color, alpha=CONFIG.kde_sim_alpha, linewidth=0, cut=0)
sns.kdeplot(x=weibo_x, ax=ax_top, fill=True, color=CONFIG.kde_weibo_color, alpha=CONFIG.kde_weibo_alpha, linewidth=0, cut=0)
ax_top.set_xlim(xlims)
ax_top.axis('off')

# ---- 3.2 右侧边缘图 ----
ax_right = fig.add_subplot(gs[1, 1])
ax_right.patch.set_facecolor('none')
sns.kdeplot(y=sim_y, weights=sim_weights, ax=ax_right, fill=True, color=CONFIG.kde_sim_color, alpha=CONFIG.kde_sim_alpha, linewidth=0, cut=0)
sns.kdeplot(y=weibo_y, ax=ax_right, fill=True, color=CONFIG.kde_weibo_color, alpha=CONFIG.kde_weibo_alpha, linewidth=0, cut=0)
ax_right.set_ylim(ylims)
ax_right.axis('off')

# ---- 3.3 主地图 ----
ax_main = fig.add_subplot(gs[1, 0])
ax_main.patch.set_facecolor('none') 

# 隐藏上方和右方的边框线
ax_main.spines['top'].set_visible(False)
ax_main.spines['right'].set_visible(False)

# 添加虚线网格 (经纬度线)
ax_main.grid(True, linestyle='--', color='gray', alpha=0.5, zorder=0)

# 绘制底图
beijing_base.plot(ax=ax_main, facecolor=CONFIG.map_bg_color, edgecolor=CONFIG.map_edge_color, linewidth=CONFIG.map_edge_width, zorder=1)
# 绘制仿真网格
sim_grids.plot(ax=ax_main, column='sim_risk', cmap=CONFIG.sim_custom_cmap, edgecolor='none', alpha=CONFIG.sim_alpha, zorder=2)
# 绘制微博散点
ax_main.scatter(weibo_x, weibo_y, s=CONFIG.weibo_size, c=CONFIG.weibo_color, alpha=CONFIG.weibo_alpha, edgecolor=CONFIG.weibo_edge_color, linewidth=CONFIG.weibo_edge_width, zorder=3)
# 标记中心五角星 
star = gpd.GeoSeries([Point(CONFIG.lon_bj, CONFIG.lat_bj)], crs="EPSG:4326").to_crs("EPSG:3857")[0]
ax_main.scatter(star.x, star.y, marker='*', color=CONFIG.star_color, edgecolor='white', s=CONFIG.star_size, zorder=10)

ax_main.set_xlim(xlims)
ax_main.set_ylim(ylims)

# 保存主图
save_path = os.path.join(CONFIG.output_dir, "Beijing_Overlay_Final_Grid.svg")
plt.savefig(save_path, format='svg', dpi=CONFIG.dpi, bbox_inches='tight', transparent=True)
print(f"[OK] Main figure saved: {save_path}")

# ==========================================
# 4. 生成独立的图例文件 (SVG) - 包含 Colorbar
# ==========================================
print("正在生成包含 Colorbar 的独立图例...")
# 稍微加宽画板以同时容纳文字图例和 Colorbar
fig_leg = plt.figure(figsize=(6.5, 3), dpi=CONFIG.dpi, facecolor='none')

# 使用 GridSpec 划分左右两个子区域
gs_leg = GridSpec(1, 2, width_ratios=[1.5, 1], wspace=0.1)

# --- 左半部分：离散图例 (微博、KDE、市中心) ---
ax_leg_discrete = fig_leg.add_subplot(gs_leg[0])
ax_leg_discrete.axis('off')

legend_elements = [
    # 微博散点图例
    Line2D([0], [0], marker='o', color='none', label='Weibo Check-ins',
           markerfacecolor=CONFIG.weibo_color, markersize=8, markeredgewidth=CONFIG.weibo_edge_width, markeredgecolor='white'),
    # 仿真 KDE 图例
    mpatches.Patch(color=CONFIG.kde_sim_color, alpha=CONFIG.kde_sim_alpha, label='Simulation Density (KDE)'),
    # 微博 KDE 图例
    mpatches.Patch(color=CONFIG.kde_weibo_color, alpha=CONFIG.kde_weibo_alpha, label='Weibo Density (KDE)'),
    # 市中心图例
    Line2D([0], [0], marker='*', color='none', label='City Center',
           markerfacecolor=CONFIG.star_color, markersize=15)
]

ax_leg_discrete.legend(handles=legend_elements, loc='center', frameon=False, 
              prop={'family': 'sans-serif', 'size': 12}) # 满足 SCI 无衬线字体要求

# --- 右半部分：连续图例 (仿真热不适的 Colorbar) ---
ax_leg_cbar = fig_leg.add_subplot(gs_leg[1])

# 获取真实数据的最大最小值，确保 Colorbar 刻度准确
vmin, vmax = sim_weights.min(), sim_weights.max()
norm = Normalize(vmin=vmin, vmax=vmax)

# 创建标量映射对象 (ScalarMappable)
sm = ScalarMappable(cmap=CONFIG.sim_custom_cmap, norm=norm)
sm.set_array([]) 

# 绘制 Colorbar
cbar = fig_leg.colorbar(sm, cax=ax_leg_cbar, orientation='vertical', alpha=CONFIG.sim_alpha)
# 标签增加换行符，防止截断
cbar.set_label('Simulated Thermal\nDiscomfort (Hours)', fontname='sans-serif', fontsize=12, labelpad=10)

# 美化 Colorbar (去掉边框，设置刻度字体)
cbar.outline.set_edgecolor('none')
cbar.ax.tick_params(labelsize=10, length=4, color='gray')
for l in cbar.ax.yaxis.get_ticklabels():
    l.set_family('sans-serif')

# 保存最终图例
leg_save_path = os.path.join(CONFIG.output_dir, "Legend_Standalone_WithCbar.svg")
fig_leg.savefig(leg_save_path, format='svg', transparent=True, bbox_inches='tight')
print(f"[OK] Legend (with colorbar) saved: {leg_save_path}")