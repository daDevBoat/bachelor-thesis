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


def prepare_xy(df):
    df = df[["timestamp", "x", "y", "z"]].dropna().copy()
    df["time_s"] = (df["timestamp"] - df["timestamp"].iloc[0]) / 1e6
    x0 = df["x"].iloc[0]
    y0 = df["y"].iloc[0]
    df["x_shift"] = df["x"] - x0
    df["y_shift"] = df["y"] - y0
    return df


def compute_path_metrics(df, waypoints):
    df = df.copy()
    df["cte_m"] = df.apply(lambda r: path_error(r["x_shift"], r["y_shift"], waypoints), axis=1)

    mean_cte = df["cte_m"].mean()
    max_cte = df["cte_m"].max()
    rms_cte = np.sqrt(np.mean(df["cte_m"] ** 2))

    return df, mean_cte, max_cte, rms_cte


def main():
    if len(sys.argv) != 2:
        print("Usage: python analyze_groundtruth_and_estimation.py /path/to/run_folder")
        sys.exit(1)

    run_dir = Path(sys.argv[1]).expanduser().resolve()
    if not run_dir.exists():
        print(f"Run folder does not exist: {run_dir}")
        sys.exit(1)

    est_files = list(run_dir.glob("*vehicle_local_position_0.csv"))
    gt_files = list(run_dir.glob("*vehicle_local_position_groundtruth_0.csv"))

    if not est_files:
        print("Could not find '*vehicle_local_position_0.csv' in the run folder.")
        sys.exit(1)

    if not gt_files:
        print("Could not find '*vehicle_local_position_groundtruth_0.csv' in the run folder.")
        sys.exit(1)

    est_file = est_files[0]
    gt_file = gt_files[0]
    run_name = run_dir.name

    df_est = pd.read_csv(est_file)
    df_gt = pd.read_csv(gt_file)

    df_est = prepare_xy(df_est)
    df_gt = prepare_xy(df_gt)

    waypoints = [
        (0.0, 0.0),
        (20.0, 0.0),
        (20.0, 20.0),
        (0.0, 20.0),
        (0.0, 0.0),
    ]
    wp = np.array(waypoints)

    df_gt, gt_mean, gt_max, gt_rms = compute_path_metrics(df_gt, waypoints)

    est_small = df_est[["time_s", "x_shift", "y_shift"]].sort_values("time_s").copy()
    gt_small = df_gt[["time_s", "x_shift", "y_shift"]].sort_values("time_s").copy()

    merged = pd.merge_asof(
        est_small,
        gt_small,
        on="time_s",
        suffixes=("_est", "_gt"),
        direction="nearest"
    )

    merged["estimation_error_m"] = np.sqrt(
        (merged["x_shift_est"] - merged["x_shift_gt"]) ** 2 +
        (merged["y_shift_est"] - merged["y_shift_gt"]) ** 2
    )

    est_gt_mean = merged["estimation_error_m"].mean()
    est_gt_max = merged["estimation_error_m"].max()
    est_gt_rms = np.sqrt(np.mean(merged["estimation_error_m"] ** 2))

    print("Ground-truth trajectory vs planned mission")
    print("-----------------------------------------")
    print(f"Run folder: {run_dir}")
    print(f"Samples: {len(df_gt)}")
    print(f"Mean cross-track error: {gt_mean:.3f} m")
    print(f"Max  cross-track error: {gt_max:.3f} m")
    print(f"RMS  cross-track error: {gt_rms:.3f} m")

    print("\\nEstimated trajectory vs ground-truth trajectory")
    print("----------------------------------------------")
    print(f"Samples: {len(merged)}")
    print(f"Mean estimation error: {est_gt_mean:.3f} m")
    print(f"Max  estimation error: {est_gt_max:.3f} m")
    print(f"RMS  estimation error: {est_gt_rms:.3f} m")

    summary = pd.DataFrame([{
        "run_name": run_name,
        "gt_mean_cte_m": gt_mean,
        "gt_max_cte_m": gt_max,
        "gt_rms_cte_m": gt_rms,
        "est_gt_mean_error_m": est_gt_mean,
        "est_gt_max_error_m": est_gt_max,
        "est_gt_rms_error_m": est_gt_rms,
    }])
    summary.to_csv(run_dir / f"{run_name}_groundtruth_estimation_summary.csv", index=False)

    merged[[
        "time_s",
        "x_shift_est",
        "y_shift_est",
        "x_shift_gt",
        "y_shift_gt",
        "estimation_error_m"
    ]].to_csv(
        run_dir / f"{run_name}_estimation_error_timeseries.csv",
        index=False
    )

    plt.figure(figsize=(8, 8))
    plt.plot(df_est["x_shift"], df_est["y_shift"], label="Estimated path")
    plt.plot(df_gt["x_shift"], df_gt["y_shift"], label="Ground-truth path")
    plt.plot(wp[:, 0], wp[:, 1], "o--", label="Planned mission")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.title(f"Estimated vs ground-truth vs planned path ({run_name})")
    plt.axis("equal")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(run_dir / f"{run_name}_estimated_vs_groundtruth_vs_planned.png", dpi=300)
    plt.show()

    plt.figure(figsize=(10, 4))
    plt.plot(df_gt["time_s"], df_gt["cte_m"])
    plt.xlabel("Time [s]")
    plt.ylabel("Ground-truth CTE [m]")
    plt.title(f"Ground-truth cross-track error over time ({run_name})")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(run_dir / f"{run_name}_groundtruth_cte_over_time.png", dpi=300)
    plt.show()

    plt.figure(figsize=(10, 4))
    plt.plot(merged["time_s"], merged["estimation_error_m"])
    plt.xlabel("Time [s]")
    plt.ylabel("Estimated vs ground-truth error [m]")
    plt.title(f"Estimation error over time ({run_name})")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(run_dir / f"{run_name}_estimation_error_over_time.png", dpi=300)
    plt.show()


if __name__ == "__main__":
    main()
