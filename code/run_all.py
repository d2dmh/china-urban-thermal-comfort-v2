"""
Main pipeline — One-click run: Step 1 -> Step 2 -> Step 3 -> Step 4.

6 cities x 6 strategies x 7 climate scenarios.
Produces SET computations, per-capita discomfort hours, energy capacity, and load curves
consumed by the plotting scripts in figure/.
"""

import os, sys, time, subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

STEPS = [
    ("step1_compute_set.py",        "Step 1: SET computation + per-capita hours"),
    ("step2_pivot_tables.py",       "Step 2: Pivot tables"),
    ("step3_energy_capacity.py",    "Step 3: Energy + capacity + peak load"),
    ("step4_citywide_load_curves.py","Step 4: Compute citywide GW load curves"),
]


def run_step(script, desc):
    print(f"\n{'#'*60}\n#  {desc}\n{'#'*60}")
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, script)],
                       cwd=PROJECT_ROOT)
    if r.returncode != 0:
        print(f"\n[ERROR] {desc} failed (code={r.returncode})")
        sys.exit(r.returncode)
    print(f"\n[OK] {desc} completed in {time.time()-t0:.1f}s")


def main():
    print("=" * 60)
    print("  Pipeline: 6 cities x 6 strategies x 7 scenarios")
    print("=" * 60)
    t0 = time.time()
    for script, desc in STEPS:
        run_step(script, desc)
    print(f"\n{'='*60}")
    print(f"  [DONE] Total: {time.time()-t0:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
