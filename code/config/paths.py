"""
Path configuration: all external data and output paths managed centrally.
Project modules import paths from this file to avoid hardcoding.

All paths are relative to the project root. Users should place Zenodo data
under the `data/` directory following the structure described in README.md.
"""

import os


# ================= Project root =================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ================= Data paths (relative to project root) =================

DATA_ROOT = os.path.join(PROJECT_ROOT, "data")
INPUT_DATA_ROOT = os.path.join(DATA_ROOT, "input data")
OTHER_DATA_ROOT = os.path.join(DATA_ROOT, "other data")

# EPW weather files directory
EPW_ROOT = os.path.join(INPUT_DATA_ROOT, "epw_files")

# Building population attribute data directory
POPULATION_ROOT = os.path.join(OTHER_DATA_ROOT, "population")

# Cluster mapping files directory
CLUSTER_MAP_ROOT = os.path.join(OTHER_DATA_ROOT, "cluster_maps")


# ================= Dynamic path builders (temperature baseline–aware) =================

def get_simulation_root(temp_baseline):
    """
    Get the simulation data root directory for a given temperature baseline.

    Args:
        temp_baseline: Temperature baseline (27)

    Returns:
        Path to simulation data root directory
    """
    from Code.config.parameters import TEMP_BASELINE_DIRS
    baseline_dir = TEMP_BASELINE_DIRS.get(temp_baseline, "GeiMingHao_27Degree")
    return os.path.join(INPUT_DATA_ROOT, baseline_dir, "GeiMingHao_IndoorEnv")


def get_strategy_dirs(temp_baseline):
    """
    Get the three strategy subdirectories for a given temperature baseline.

    Args:
        temp_baseline: Temperature baseline (27)

    Returns:
        dict: strategy name (Chinese) → directory path
    """
    sim_root = get_simulation_root(temp_baseline)
    return {
        "Baseline": os.path.join(sim_root, "Baseline_2020"),
        "Expansion": os.path.join(sim_root, "Capacity_expansion"),
        "Fixed": os.path.join(sim_root, "Fixed_capacity"),
    }


# ================= Output paths (per temperature baseline) =================

RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")


def get_set_output_dir(baseline):
    """Step 1 output: SET calculation results (hourly Excel files + summary CSV)."""
    return os.path.join(RESULTS_ROOT, f"{baseline}Degree", "set_calculations")


def get_per_capita_output_dir(baseline):
    """Step 1 output: per-capita discomfort hours summary table."""
    return os.path.join(RESULTS_ROOT, f"{baseline}Degree", "per_capita_hours")


def get_pivot_output_dir(baseline):
    """Step 2 output: pivot tables."""
    return os.path.join(RESULTS_ROOT, f"{baseline}Degree", "pivot_tables")


def get_figures_dir(baseline=None):
    """Figure output directory."""
    if baseline:
        return os.path.join(RESULTS_ROOT, "figures", f"{baseline}Degree")
    return os.path.join(RESULTS_ROOT, "figures")


def ensure_output_dirs(baseline=None):
    """Ensure all output directories exist."""
    baselines = [baseline] if baseline else [27]
    for b in baselines:
        for d in [get_set_output_dir(b), get_per_capita_output_dir(b),
                  get_pivot_output_dir(b)]:
            os.makedirs(d, exist_ok=True)
    os.makedirs(get_figures_dir(), exist_ok=True)
