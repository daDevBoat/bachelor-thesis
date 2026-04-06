import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def point_to_segment_distance(px, py, ax, ay, bx, by):
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay

    ab_len_sq = abx * abx + aby * aby
    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = (apx * abx + apy * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    cx = ax + t * abx
    cy = ay + t * aby
    return math.hypot(px - cx, py - cy)


def path_error(px, py, waypoints):
    return min(
        point_to_segment_distance(
            px, py,
            waypoints[i][0], waypoints[i][1],
            waypoints[i + 1][0], waypoints[i + 1][1]
        )
        for i in range(len(waypoints) - 1)
    )


def compute_path_metrics(df, waypoints):
    df = df.copy()
    df["cte_m"] = df.apply(lambda r: path_error(r["x_shift"], r["y_shift"], waypoints), axis=1)

    mean_cte = df["cte_m"].mean()
    max_cte = df["cte_m"].max()
    rms_cte = np.sqrt(np.mean(df["cte_m"] ** 2))

    return df, mean_cte, max_cte, rms_cte


def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_estimated_vs_planned.py /path/to/run_folder")
        sys.exit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.exists():
        print(f"Run folder does not exist: {run_dir}")
        sys.exit(1)

    est_files = list(run_dir.glob("*vehicle_local_position_0.csv"))
    if not est_files:
        print("Could not find '*vehicle_local_position_0.csv' in the run folder.")
        sys.exit(1)

    est_file = est_files[0]
    run_name = run_dir.name

    df = pd.read_csv(est_file)
    df = df[["timestamp", "x", "y", "z"]].dropna().copy()

    df["time_s"] = (df["timestamp"] - df["timestamp"].iloc[0]) / 1e6

    x0 = df["x"].iloc[0]
    y0 = df["y"].iloc[0]

    df["x_shift"] = df["x"] - x0
    df["y_shift"] = df["y"] - y0

    waypoints = [
        (0.0, 0.0),
        (20.0, 0.0),
        (20.0, 20.0),
        (0.0, 20.0),
        (0.0, 0.0),
    ]

    df, mean_cte, max_cte, rms_cte = compute_path_metrics(df, waypoints)

    print("Estimated trajectory vs planned mission")
    print("---------------------------------------")
    print(f"Run folder: {run_dir}")
    print(f"Samples: {len(df)}")
    print(f"Mean cross-track error: {mean_cte:.3f} m")
    print(f"Max  cross-track error: {max_cte:.3f} m")
    print(f"RMS  cross-track error: {rms_cte:.3f} m")

    summary = pd.DataFrame([{
        "run_name": run_name,
        "mean_cte_m": mean_cte,
        "max_cte_m": max_cte,
        "rms_cte_m": rms_cte,
    }])
    summary.to_csv(run_dir / f"{run_name}_metrics_summary.csv", index=False)

    df[["time_s", "x_shift", "y_shift", "cte_m"]].to_csv(
        run_dir / f"{run_name}_cte_timeseries.csv", index=False
    )

    wp = np.array(waypoints)

    plt.figure(figsize=(8, 8))
    plt.plot(df["x_shift"], df["y_shift"], label="Estimated path")
    plt.plot(wp[:, 0], wp[:, 1], "o--", label="Planned path")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.title(f"Estimated path vs planned rectangle ({run_name})")
    plt.axis("equal")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(run_dir / f"{run_name}_estimated_vs_planned.png", dpi=300)
    plt.show()

    plt.figure(figsize=(10, 4))
    plt.plot(df["time_s"], df["cte_m"])
    plt.xlabel("Time [s]")
    plt.ylabel("Cross-track error [m]")
    plt.title(f"Cross-track error over time ({run_name})")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(run_dir / f"{run_name}_cte_over_time.png", dpi=300)
    plt.show()


if __name__ == "__main__":
    main()
