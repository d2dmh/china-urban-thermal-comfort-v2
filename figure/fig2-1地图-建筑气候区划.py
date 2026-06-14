import os
import pyproj
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import Counter  # 新增：用于统计附近最多的颜色

# ================= 0. 修复中文显示乱码 =================
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

# ================= 1. 核心调节区 =================

# 🌟 南海诸岛小图位置与大小
INSET_X = 0.89
INSET_Y = 0.25
INSET_WIDTH = 0.07
INSET_HEIGHT = 0.2
INSET_MARGIN = 0.15

# 🌟 基础颜色配置
COLOR_HIGHLIGHT = '#931832'  # 高亮城市的颜色（红色）
COLOR_LINE = '#333333'  # 边界线颜色
LINE_WIDTH_MAIN = 0.3  # 主图普通城市边框粗细（调细了）
LINE_WIDTH_HL = 0.5  # 主图高亮城市边框粗细（调细了）

# 🌟 气候区颜色配置
CLIMATE_CONFIG = {
    "严寒气候区": {"color": "#3850A1", "cities": []},
    "寒冷气候区": {"color": "#7EA8C3", "cities": []},
    "夏热冬冷气候区": {"color": "#EBB97F", "cities": []},
    "夏热冬暖气候区": {"color": "#D56B52", "cities": []},
    "温和气候区": {"color": "#F7F4C3", "cities": []}
}

# ================= 2. 城市列表数据导入 =================
severe_cold_cities = ["哈尔滨市", "齐齐哈尔市", "鸡西市", "鹤岗市", "双鸭山市", "大庆市", "伊春市", "佳木斯市",
                      "七台河市", "牡丹江市", "黑河市", "绥化市", "大兴安岭地区", "长春市", "吉林市", "四平市",
                      "辽源市", "通化市", "白山市", "松原市", "白城市", "延边朝鲜族自治州", "呼和浩特市", "包头市",
                      "乌海市", "赤峰市", "通辽市", "鄂尔多斯市", "呼伦贝尔市", "巴彦淖尔市", "乌兰察布市", "兴安盟",
                      "锡林郭勒盟", "阿拉善盟", "沈阳市", "抚顺市", "本溪市", "阜新市", "辽阳市", "铁岭市", "朝阳市",
                      "张家口市", "承德市", "乌鲁木齐市", "克拉玛依市", "昌吉回族自治州", "博尔塔拉蒙古自治州",
                      "伊犁哈萨克自治州", "塔城地区", "阿勒泰地区", "西宁市", "海东市", "海北藏族自治州",
                      "黄南藏族自治州", "海南藏族自治州", "果洛藏族自治州", "玉树藏族自治州", "海西蒙古族藏族自治州",
                      "那曲市", "阿里地区", "嘉峪关市", "金昌市", "张掖市", "酒泉市"]
cold_cities = ["北京市", "天津市", "石家庄市", "唐山市", "秦皇岛市", "邯郸市", "邢台市", "保定市", "沧州市", "廊坊市",
               "衡水市", "太原市", "大同市", "阳泉市", "长治市", "晋城市", "朔州市", "晋中市", "运城市", "忻州市",
               "临汾市", "吕梁市", "大连市", "鞍山市", "丹东市", "锦州市", "营口市", "盘锦市", "葫芦岛市", "济南市",
               "青岛市", "淄博市", "枣庄市", "东营市", "烟台市", "潍坊市", "济宁市", "泰安市", "威海市", "日照市",
               "临沂市", "德州市", "聊城市", "滨州市", "菏泽市", "郑州市", "开封市", "洛阳市", "平顶山市", "安阳市",
               "鹤壁市", "新乡市", "焦作市", "濮阳市", "许昌市", "漯河市", "三门峡市", "商丘市", "周口市", "驻马店市",
               "西安市", "铜川市", "宝鸡市", "咸阳市", "渭南市", "延安市", "榆林市", "商洛市", "兰州市", "白银市",
               "天水市", "武威市", "平凉市", "庆阳市", "定西市", "陇南市", "临夏回族自治州", "甘南藏族自治州", "银川市",
               "石嘴山市", "吴忠市", "固原市", "中卫市", "巴音郭楞蒙古自治州", "阿克苏地区", "克孜勒苏柯尔克孜自治州",
               "喀什地区", "和田地区", "拉萨市", "日喀则市", "昌都市", "林芝市", "山南市", "甘孜藏族自治州", "吐鲁番市",
               "哈密市", "阿坝藏族羌族自治州"]
hot_summer_cold_winter_cities = ["上海市", "南京市", "无锡市", "徐州市", "常州市", "苏州市", "南通市", "连云港市",
                                 "淮安市", "盐城市", "扬州市", "镇江市", "泰州市", "宿迁市", "杭州市", "宁波市",
                                 "温州市", "嘉兴市", "湖州市", "绍兴市", "金华市", "衢州市", "舟山市", "台州市",
                                 "丽水市", "合肥市", "芜湖市", "蚌埠市", "淮南市", "马鞍山市", "淮北市", "铜陵市",
                                 "安庆市", "黄山市", "滁州市", "阜阳市", "宿州市", "六安市", "亳州市", "池州市",
                                 "宣城市", "南昌市", "景德镇市", "萍乡市", "九江市", "新余市", "鹰潭市", "赣州市",
                                 "吉安市", "宜春市", "抚州市", "上饶市", "南阳市", "信阳市", "武汉市", "黄石市",
                                 "十堰市", "宜昌市", "襄阳市", "鄂州市", "荆门市", "孝感市", "荆州市", "黄冈市",
                                 "咸宁市", "随州市", "恩施土家族苗族自治州", "长沙市", "株洲市", "湘潭市", "衡阳市",
                                 "邵阳市", "岳阳市", "常德市", "张家界市", "益阳市", "郴州市", "永州市", "怀化市",
                                 "娄底市", "湘西土家族苗族自治州", "重庆市", "成都市", "自贡市", "泸州市", "德阳市",
                                 "绵阳市", "广元市", "遂宁市", "内江市", "乐山市", "南充市", "眉山市", "宜宾市",
                                 "广安市", "达州市", "雅安市", "巴中市", "资阳市", "汉中市", "安康市", "三明市",
                                 "南平市", "宁德市", "遵义市", "铜仁市", "黔东南苗族侗族自治州", "桂林市"]
hot_summer_warm_winter_cities = ["福州市", "厦门市", "莆田市", "泉州市", "漳州市", "龙岩市", "广州市", "韶关市",
                                 "深圳市", "珠海市", "汕头市", "佛山市", "江门市", "湛江市", "茂名市", "肇庆市",
                                 "惠州市", "梅州市", "汕尾市", "河源市", "阳江市", "清远市", "东莞市", "中山市",
                                 "潮州市", "揭阳市", "云浮市", "南宁市", "柳州市", "梧州市", "北海市", "防城港市",
                                 "钦州市", "贵港市", "玉林市", "百色市", "贺州市", "河池市", "来宾市", "崇左市",
                                 "海口市", "三亚市", "三沙市", "儋州市", "香港特别行政区", "澳门特别行政区"]
temperate_cities = ["昆明市", "曲靖市", "玉溪市", "保山市", "昭通市", "丽江市", "普洱市", "临沧市", "楚雄彝族自治州",
                    "红河哈尼族彝族自治州", "文山壮族苗族自治州", "西双版纳傣族自治州", "大理白族自治州",
                    "德宏傣族景颇族自治州", "怒江傈僳族自治州", "迪庆藏族自治州", "贵阳市", "六盘水市", "安顺市",
                    "毕节市", "黔西南布依族苗族自治州", "黔南布依族苗族自治州", "攀枝花市", "凉山彝族自治州"]

CLIMATE_CONFIG["严寒气候区"]["cities"] = severe_cold_cities
CLIMATE_CONFIG["寒冷气候区"]["cities"] = cold_cities
CLIMATE_CONFIG["夏热冬冷气候区"]["cities"] = hot_summer_cold_winter_cities
CLIMATE_CONFIG["夏热冬暖气候区"]["cities"] = hot_summer_warm_winter_cities
CLIMATE_CONFIG["温和气候区"]["cities"] = temperate_cities

# ================= 3. 环境变量与路径 =================
proj_path = r"E:\anacondaa\envs\myproj\Library\share\proj"
os.environ['PROJ_LIB'] = proj_path
os.environ['PROJ_DATA'] = proj_path
pyproj.datadir.set_data_dir(proj_path)

shp_path_city = r"E:\中国标准地图-审图号GS(2024)0650号-shp格式\面格式\中国_市_Albers.shp"
shp_path_ninedash = r"E:\中国标准地图-审图号GS(2024)0650号-shp格式\线格式\九段线_Albers.shp"

# ================= 4. 数据处理与空间智能补全 =================
gdf = gpd.read_file(shp_path_city)
gdf_ninedash = gpd.read_file(shp_path_ninedash)


# 4.1 基础匹配：【核心修复区】修复“鞍山”误配“马鞍山”的Bug
def assign_climate_color(city_name):
    if not city_name: return None

    # 1. 优先完全精确匹配（最安全）
    for zone, info in CLIMATE_CONFIG.items():
        if city_name in info["cities"]:
            return info["color"]

    # 2. 如果因为数据源缺失“市/州”后缀没匹配上，则去除后缀再比对
    def clean_name(name):
        for suffix in ["市", "地区", "盟", "自治州", "特别行政区"]:
            name = name.replace(suffix, "")
        return name

    city_core = clean_name(city_name)
    for zone, info in CLIMATE_CONFIG.items():
        for c in info["cities"]:
            if clean_name(c) == city_core:
                return info["color"]

    return None


gdf['climate_color'] = gdf['name'].apply(assign_climate_color)

# 4.2 提取六个需要标红的高亮城市
target_keywords = '北京|上海|广州|深圳|厦门|武汉'
highlight_cities = gdf[gdf['name'].str.contains(target_keywords, na=False, regex=True)]

# 4.3 智能空间插值：用周边邻居的最常见颜色，填补缺失城市
print("正在进行空间智能运算，自动以附近城市的颜色补全缺失区域...")
sindex = gdf.sindex
while True:
    missing_idx = gdf[gdf['climate_color'].isna()].index
    if len(missing_idx) == 0:
        break

    changed = False
    for idx in missing_idx:
        geom = gdf.loc[idx, 'geometry']
        possible_matches_index = list(sindex.intersection(geom.bounds))
        possible_matches = gdf.iloc[possible_matches_index]
        precise_matches = possible_matches[possible_matches.intersects(geom)]

        neighbor_colors = precise_matches['climate_color'].dropna().tolist()

        if neighbor_colors:
            most_common_color = Counter(neighbor_colors).most_common(1)[0][0]
            gdf.loc[idx, 'climate_color'] = most_common_color
            changed = True

    if not changed: break

# 4.4 兜底处理
remaining_idx = gdf[gdf['climate_color'].isna()].index
if len(remaining_idx) > 0:
    known_gdf = gdf[~gdf['climate_color'].isna()]
    for idx in remaining_idx:
        geom = gdf.loc[idx, 'geometry']
        nearest_idx = known_gdf.distance(geom).idxmin()
        gdf.loc[idx, 'climate_color'] = known_gdf.loc[nearest_idx, 'climate_color']
print("补全完成！开始绘图...")

# ================= 5. 开始绘制主图 =================
fig, ax = plt.subplots(figsize=(15, 15))

for color in gdf['climate_color'].unique():
    subset = gdf[gdf['climate_color'] == color]
    subset.plot(ax=ax, color=color, edgecolor=COLOR_LINE, linewidth=LINE_WIDTH_MAIN)

if not highlight_cities.empty:
    highlight_cities.plot(ax=ax, color=COLOR_HIGHLIGHT, edgecolor=COLOR_LINE, linewidth=LINE_WIDTH_HL)

gdf_ninedash.plot(ax=ax, color=COLOR_LINE, linewidth=1.5)

legend_patches = [mpatches.Patch(color=info["color"], label=zone) for zone, info in CLIMATE_CONFIG.items()]
legend_patches.append(mpatches.Patch(color=COLOR_HIGHLIGHT, label="典型代表城市"))
ax.legend(handles=legend_patches, loc='lower left', title="建筑气候区划", prop={'size': 12}, title_fontsize=14)

# ================= 6. 南海小图同步 =================
ax_inset = ax.inset_axes([INSET_X, INSET_Y, INSET_WIDTH, INSET_HEIGHT])

for color in gdf['climate_color'].unique():
    subset = gdf[gdf['climate_color'] == color]
    subset.plot(ax=ax_inset, color=color, edgecolor=COLOR_LINE, linewidth=0.1)

if not highlight_cities.empty:
    highlight_cities.plot(ax=ax_inset, color=COLOR_HIGHLIGHT, edgecolor=COLOR_LINE, linewidth=0.2)

gdf_ninedash.plot(ax=ax_inset, color=COLOR_LINE, linewidth=0.8)

bounds = gdf_ninedash.total_bounds
margin_x = (bounds[2] - bounds[0]) * INSET_MARGIN
margin_y = (bounds[3] - bounds[1]) * INSET_MARGIN
ax_inset.set_xlim(bounds[0] - margin_x, bounds[2] + margin_x)
ax_inset.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)

ax_inset.set_xticks([])
ax_inset.set_yticks([])
for spine in ax_inset.spines.values():
    spine.set_edgecolor(COLOR_LINE)
    spine.set_linewidth(1.0)

# ================= 7. 设置透明及保存 =================
ax.axis('off')
fig.patch.set_alpha(0.0)
ax.patch.set_alpha(0.0)

output_dir = r"C:\Users\31080\Desktop\figure"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_path = os.path.join(output_dir, "建筑气候区划_标红且自动补全版.png")
plt.savefig(output_path, dpi=600, transparent=True, bbox_inches='tight', pad_inches=0)

print(f"✅ 地图已保存至: {output_path}")