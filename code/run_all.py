"""
One-click run: Step 1 (SET + per-capita) → Step 2 (pivot tables).

Execution order:
  step1_compute_set.py → step2_pivot_tables.py
"""

import os
import sys
import multiprocessing

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    print("\n" + "=" * 70)
    print("  Step 1: SET computation + nighttime overheating + per-capita hours")
    print("=" * 70)
    from Code.pipeline.step1_compute_set import main as step1_main
    step1_main()

    print("\n" + "=" * 70)
    print("  Step 2: Pivot tables")
    print("=" * 70)
    from Code.pipeline.step2_pivot_tables import main as step2_main
    step2_main()

    print("\n>> All steps complete.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
