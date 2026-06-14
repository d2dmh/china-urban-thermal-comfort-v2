import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# ==============================================================================
# 🎯 核心配置区 (请在此处统一修改您的所有参数)
# ==============================================================================
class CONFIG:
    # ---------------- 1. 数据配置 ----------------
    # scenarios: X轴的标签名称。第一个是现状年份，后面是不同的未来气候情景。
    scenarios = ['2020', 'RCP 2.6', 'RCP 4.5', 'RCP 8.5']
    
    # --- 城市A (左侧柱子) 的数据 ---
    city_a_name = 'Guangzhou'        # 城市A的名称，会在图例中显示
    city_a_2040 = [17.9, 26.2, 41.7, 43.6]
    city_a_2060 = [17.9, 62.1, 65.4, 85.9]
    
    # --- 城市B (右侧柱子) 的数据 ---
    city_b_name = 'Shenzhen'         # 城市B的名称，会在图例中显示
    city_b_2040 = [42.8, 70.0, 80.4, 101.6]
    city_b_2060 = [42.8, 113.0, 122.9, 186.2]

    # ---------------- 2. 颜色与透明度配置 (SCI 高级风格) ----------------
    city_a_color = '#72AACE'         # 广州的颜色 (浅蓝色)
    city_b_color = '#A70327'         # 深圳的颜色 (深红色)
    bar_alpha = 0.7                 # 悬浮柱体的透明度 (0为完全透明，1为完全不透明)
    
    mean_line_color = '#222222'      # 年代均值黑线的颜色 (深灰色/纯黑色)

    # ---------------- 3. 画板与排版尺寸参数 ----------------
    fig_size = (4.5, 5)              # 整个画板的大小 (宽度稍微增加一点以便容纳图例)
    dpi = 600                        # 输出图片的清晰度 (600为典型的SCI出版标准)
    
    bar_width = 0.13                 # 柱体的绝对宽度 (数值越小，柱子越纤细)
    bar_offset = 0.12                # 同一组情景下，左右两个柱子偏离中心的距离 (控制两者的拥挤程度)
    
    mean_line_width = 2.4            # 代表均值的黑色横线的粗细
    mean_line_scale = 1.35           # 黑色横线的宽度比例 (1.35表示线比其底下的柱子本身宽35%)

    # ---------------- 4. 字体、线条与标签配置 ----------------
    font_family = 'Arial'            # 全局使用的无衬线英文字体 (符合多数期刊要求)
    axes_linewidth = 1.2             # 坐标轴边框线的粗细
    
    y_label = 'Hours / Resident'     # Y轴的标题文本
    y_label_size = 14                # Y轴标题的字体大小
    x_tick_size = 14                 # X轴刻度(RCP情景文本)的字体大小
    legend_size = 12                 # 图例内部说明文字的字体大小

    # ---------------- 5. 坐标轴范围与刻度配置 (极大影响画面整洁度) ----------------
    y_min = 0                        # Y轴的起始最小值 (柱状图的基准线必须从0开始，避免视觉失真)
    y_max = 200                      # Y轴的最大值 (设为200，刚好包容最大的数据 186.2，留有呼吸感)
    y_tick_step = 40                 # Y轴刻度步长 (设为40，非常清爽)

# ==============================================================================
# (以下为绘图渲染核心逻辑，日常修改数据无需改动这里)
# ==============================================================================

# 1. 初始化设置
plt.rcParams['font.sans-serif'] = [CONFIG.font_family]
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.linewidth'] = CONFIG.axes_linewidth

# 将数据转换为 numpy 数组以便进行向量化运算，同时计算均值
arr_a_2040 = np.array(CONFIG.city_a_2040)
arr_a_2060 = np.array(CONFIG.city_a_2060)
arr_a_means = (arr_a_2040 + arr_a_2060) / 2

arr_b_2040 = np.array(CONFIG.city_b_2040)
arr_b_2060 = np.array(CONFIG.city_b_2060)
arr_b_means = (arr_b_2040 + arr_b_2060) / 2

# 创建画板对象
fig, ax = plt.subplots(figsize=CONFIG.fig_size, dpi=CONFIG.dpi)
x = np.arange(len(CONFIG.scenarios))

# 2. 循环绘制每一组数据
for i in range(len(CONFIG.scenarios)):
    # 绘制 左侧城市 (City A) 的悬浮波动范围柱，统一使用 city_a_color
    ax.bar(x[i] - CONFIG.bar_offset, arr_a_2060[i] - arr_a_2040[i], 
           CONFIG.bar_width, bottom=arr_a_2040[i], 
           color=CONFIG.city_a_color, edgecolor='none', alpha=CONFIG.bar_alpha, zorder=2)
    
    # 绘制 右侧城市 (City B) 的悬浮波动范围柱，统一使用 city_b_color
    ax.bar(x[i] + CONFIG.bar_offset, arr_b_2060[i] - arr_b_2040[i], 
           CONFIG.bar_width, bottom=arr_b_2040[i], 
           color=CONFIG.city_b_color, edgecolor='none', alpha=CONFIG.bar_alpha, zorder=2)

    # 计算均值线的实际渲染宽度
    marker_w = CONFIG.bar_width * CONFIG.mean_line_scale 
    
    # 绘制 左右两个城市的年代际均值横线
    ax.hlines(arr_a_means[i], x[i] - CONFIG.bar_offset - marker_w/2, x[i] - CONFIG.bar_offset + marker_w/2, 
               colors=CONFIG.mean_line_color, linewidth=CONFIG.mean_line_width, zorder=3)
    
    ax.hlines(arr_b_means[i], x[i] + CONFIG.bar_offset - marker_w/2, x[i] + CONFIG.bar_offset + marker_w/2, 
               colors=CONFIG.mean_line_color, linewidth=CONFIG.mean_line_width, zorder=3)



# 设置标题与刻度文本
ax.set_ylabel(CONFIG.y_label, fontsize=CONFIG.y_label_size, fontweight='bold', labelpad=10)
ax.set_xticks(x)
ax.set_xticklabels(CONFIG.scenarios, fontsize=CONFIG.x_tick_size, fontweight='bold')

# 应用Y轴的范围与自定义刻度步长
ax.set_ylim(CONFIG.y_min, CONFIG.y_max)
ax.set_yticks(np.arange(CONFIG.y_min, CONFIG.y_max + 1, CONFIG.y_tick_step))

# 隐藏顶部和右侧的边框线 (经典去冗余操作)
ax.spines['right'].set_visible(False)
ax.spines['top'].set_visible(False)

# 设置底部和左侧保留的刻度线样式 (direction='out' 使刻度线朝外，不侵入作图区)
ax.tick_params(axis='x', direction='out', length=5, width=CONFIG.axes_linewidth, pad=8, bottom=True) 
ax.tick_params(axis='y', direction='out', length=5, width=CONFIG.axes_linewidth, left=True)

# 自动调整排版使其紧凑
plt.tight_layout()

# plt.savefig("IPCC_Style_Plot_with_Baseline.pdf", format='pdf', transparent=True)
plt.show()