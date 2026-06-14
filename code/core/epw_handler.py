"""
EPW weather file processing: extract atmospheric pressure and align time axes.
"""

import os
import re
import glob
import numpy as np
import pandas as pd


def extract_epw_pressure(epw_file):
    """
    Extract hourly atmospheric pressure (8760 hours per year) from an EPW file.

    EPW files have 8 header lines; column 9 (0-indexed) is atmospheric pressure in Pa.

    Args:
        epw_file: path to .epw file

    Returns:
        numpy array of pressure values [Pa], shape (8760,)
    """
    try:
        epw_data = pd.read_csv(epw_file, skiprows=8, header=None,
                               encoding='utf-8', engine='python', usecols=[9])
        return epw_data.iloc[:, 0].values.astype(float)
    except Exception:
        # Fallback to standard atmospheric pressure
        return np.full(8760, 101325.0)


def get_epw_start_offset(date_str):
    """
    Compute the starting hour index (0–8759) of an EnergyPlus date string
    within the full-year 8760-hour EPW sequence.

    Used to align CSV simulation data (which may start mid-year) with EPW
    atmospheric pressure time series.

    Args:
        date_str: date string from EnergyPlus, e.g. ' 05/01  01:00:00'

    Returns:
        integer hour offset from the start of the year
    """
    try:
        match = re.search(r'(\d{2})/(\d{2})', str(date_str))
        if not match:
            return 0
        month, day = int(match.group(1)), int(match.group(2))
        # Non-leap year day counts (EPW uses 365-day year)
        days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        past_days = sum(days_in_month[:month]) + (day - 1)
        return past_days * 24
    except Exception:
        return 0


def find_epw_file(epw_root, scenario_keyword, city_epw_keyword):
    """
    Find an EPW file under the EPW root directory using scenario subfolder
    and city English keyword matching.

    Args:
        epw_root: root directory containing EPW files
        scenario_keyword: scenario keyword (e.g. '2020', '2040-rcp2.6')
        city_epw_keyword: city English keyword (e.g. 'BEIJING', 'SHENZHENSHI')

    Returns:
        path to the matching .epw file, or None
    """
    scenario_dir = os.path.join(epw_root, scenario_keyword)
    if not os.path.exists(scenario_dir):
        scenario_dir = epw_root

    # Prefer files matching both city and scenario keywords
    patterns = [
        os.path.join(scenario_dir, f"*{city_epw_keyword}*{scenario_keyword}*.epw"),
        os.path.join(scenario_dir, f"*{city_epw_keyword}*.epw"),
    ]

    for pattern in patterns:
        matched = glob.glob(pattern)
        if matched:
            return matched[0]

    return None
