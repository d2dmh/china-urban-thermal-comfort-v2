"""
Figure 6 — One-click run: Step 1 → Step 2 → Step 3 → Step 4.

6 cities × 6 strategies × 7 climate scenarios.
Data source: GeiMingHao-6citys (see README for Zenodo download link).

Steps 1–4 compute the data needed by the plotting scripts in Figure/daima/
(figure6-a.py, figure6-b.py, figure6-c.py).
"""

import os, sys, time, subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURE6_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(script, desc):
    print(f"\n{'#'*60}\n#  {desc}\n{'#'*60}")
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(FIGURE6_DIR, script)],
                       cwd=PROJECT_ROOT)
    if r.returncode != 0:
        print(f"\n[ERROR] {desc} failed (code={r.returncode})")
        sys.exit(r.returncode)
    print(f"\n[OK] {desc} completed in {time.time()-t0:.1f}s")


def main():
    print("=" * 60)
    print("  Figure 6: 6 cities × 6 strategies × 7 scenarios")
    print("=" * 60)
    t0 = time.time()

    run_step("step1_compute_set.py", "Step 1: SET computation + per-capita hours")
    run_step("step2_pivot_tables.py", "Step 2: Pivot tables")
    run_step("step3_energy_capacity.py", "Step 3: Energy + capacity + peak load")
    run_step("step4_citywide_load_curves.py", "Step 4: Compute citywide GW load curves")

    print(f"\n{'='*60}")
    print(f"  [DONE] Total elapsed: {time.time()-t0:.1f}s")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
