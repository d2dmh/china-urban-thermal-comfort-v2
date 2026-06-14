"""
Thermal comfort calculation parameters, city configurations, and scenario definitions.
"""

# ================= Temperature baseline configuration =================

# Temperature baseline: 27°C AC setpoint (energy-saving recommendation)
BASELINES = [27]

# Data subdirectory names for each temperature baseline
TEMP_BASELINE_DIRS = {
    27: "GeiMingHao_27Degree",
}


# ================= SET thermal comfort calculation parameters =================

# Metabolic rate [met] — sleeping state
MET = 0.7

# Clothing insulation [clo] — bedding insulation
CLO = 0.8

# Indoor air velocity [m/s]
AIR_VELOCITY = 0.1

# Relative humidity upper limit under AC [%] (dehumidification effect)
RH_LIMIT = 60.0

# Nighttime discomfort threshold [°C SET]
SET_THRESHOLD = 30.0

# Nighttime hours (hour indices), 24 represents 0:00 (midnight)
NIGHT_HOURS = [22, 23, 24, 1, 2, 3, 4, 5, 6, 7]


# ================= City configurations =================

CITY_CONFIGS = [
    {
        "pinyin": "bei3jing1shi4",
        "chn_name": "Beijing",
        "name_cn": "北京市",
        "code": "110000",
        "prov_folder": "110000北京市",
        "epw_keyword": "BEIJING",
    },
    {
        "pinyin": "shang4hai3shi4",
        "chn_name": "Shanghai",
        "name_cn": "上海市",
        "code": "310000",
        "prov_folder": "310000上海市",
        "epw_keyword": "SHANGHAI",
        "custom_pop_filename": "T310000_上海市_building_pop.csv",
    },
    {
        "pinyin": "guang3zhou1shi4",
        "chn_name": "Guangzhou",
        "name_cn": "广州市",
        "code": "440100",
        "prov_folder": "440000广东省",
        "epw_keyword": "GUANGZHOU",
    },
    {
        "pinyin": "shen1zhen4shi4",
        "chn_name": "Shenzhen",
        "name_cn": "深圳市",
        "code": "440300",
        "prov_folder": "440000广东省",
        "epw_keyword": "SHENZHENSHI",
    },
    {
        "pinyin": "wu3han4shi4",
        "chn_name": "Wuhan",
        "name_cn": "武汉市",
        "code": "420100",
        "prov_folder": "420000湖北省",
        "epw_keyword": "WUHAN",
    },
    {
        "pinyin": "xia4men2shi4",
        "chn_name": "Xiamen",
        "name_cn": "厦门市",
        "code": "350200",
        "prov_folder": "350000福建省",
        "epw_keyword": "XIAMEN",
        "custom_pop_filename": "T350200_厦门市_building_pop.csv",
    },
]


# ================= Scenario configuration =================

# Label → EnergyPlus subfolder / filename keyword
SCENARIOS = {
    "2020 Baseline": "2020",
    "2040 RCP 2.6": "2040-rcp2.6",
    "2040 RCP 4.5": "2040-rcp4.5",
    "2040 RCP 8.5": "2040-rcp8.5",
    "2060 RCP 2.6": "2060-rcp2.6",
    "2060 RCP 4.5": "2060-rcp4.5",
    "2060 RCP 8.5": "2060-rcp8.5",
}

# Scenario display order (used in plots)
SCENARIO_ORDER = list(SCENARIOS.keys())


# ================= Multiprocessing configuration =================

# Number of parallel worker processes (limited by Numba/pythermalcomfort memory, recommended 2-4)
MAX_WORKERS = 4
