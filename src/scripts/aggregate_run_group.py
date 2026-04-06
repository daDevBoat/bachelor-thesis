import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main():
    if len(sys.argv) != 2:
        print("Usage: python aggregate_run_group.py /path/to/group_folder")
        sys.exit(1)

    group_dir = Path(sys.argv[1]).expanduser().resolve()
    if not group_dir.exists():
        print(f"Group folder does not exist: {group_dir}")
        sys.exit(1)

    run_dirs = sorted([p for p in group_dir.iterdir() if p.is_dir() and p.name.startswith("run_")])
    if not run_dirs:
        print(f"No run_* folders found in {group_dir}")
        sys.exit(1)

    all_rows = []

    for run_dir in run_dirs:
        run_name = run_dir.name

        metrics_files = list(run_dir.glob("*_metrics_summary.csv"))
        gt_files = list(run_dir.glob("*_groundtruth_estimation_summary.csv"))

        row = {"run_name": run_name}

        if metrics_files:
            df_metrics = pd.read_csv(metrics_files[0])
            for col in df_metrics.columns:
                row[col] = df_metrics.iloc[0][col]

        if gt_files:
            df_gt = pd.read_csv(gt_files[0])
            for col in df_gt.columns:
                row[col] = df_gt.iloc[0][col]

        all_rows.append(row)

    combined = pd.DataFrame(all_rows)

    # Remove duplicate run_name columns if present
    combined = combined.loc[:, ~combined.columns.duplicated()]

    # Numeric columns only for stats
    numeric_cols = combined.select_dtypes(include=[np.number]).columns.tolist()

    stats = []
    for col in numeric_cols:
        stats.append({
            "metric": col,
            "n": combined[col].count(),
            "mean": combined[col].mean(),
            "std": combined[col].std(),
            "min": combined[col].min(),
            "max": combined[col].max(),
        })

    stats_df = pd.DataFrame(stats)

    # Save outputs
    group_name = group_dir.name
    combined_out = group_dir / f"{group_name}_combined_results.csv"
    stats_out = group_dir / f"{group_name}_group_statistics.csv"

    combined.to_csv(combined_out, index=False)
    stats_df.to_csv(stats_out, index=False)

    print(f"Saved combined per-run table to: {combined_out}")
    print(f"Saved group statistics to: {stats_out}")

    print("\nPer-run combined table:")
    print(combined)

    print("\nGroup statistics:")
    print(stats_df)

    # Optional plots for common metrics if present
    plot_metrics = [
        "mean_cte_m",
        "max_cte_m",
        "rms_cte_m",
        "gt_mean_cte_m",
        "gt_max_cte_m",
        "gt_rms_cte_m",
        "est_gt_mean_error_m",
        "est_gt_max_error_m",
        "est_gt_rms_error_m",
    ]

    for metric in plot_metrics:
        if metric in combined.columns:
            plt.figure(figsize=(8, 4))
            plt.bar(combined["run_name"], combined[metric])
            plt.xticks(rotation=45)
            plt.ylabel(metric)
            plt.title(f"{group_name}: {metric} by run")
            plt.tight_layout()
            plt.savefig(group_dir / f"{group_name}_{metric}_by_run.png", dpi=300)
            plt.show()


if __name__ == "__main__":
    main()
