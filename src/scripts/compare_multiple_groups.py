import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def main():
    if len(sys.argv) != 2:
        print("Usage: python compare_multiple_groups.py /path/to/missions_parent_folder")
        sys.exit(1)

    parent_dir = Path(sys.argv[1]).expanduser().resolve()
    if not parent_dir.exists():
        print(f"Parent folder does not exist: {parent_dir}")
        sys.exit(1)

    group_dirs = [p for p in parent_dir.iterdir() if p.is_dir() and p.name != "scripts"]
    if not group_dirs:
        print(f"No group folders found in {parent_dir}")
        sys.exit(1)

    combined_tables = []

    for group_dir in sorted(group_dirs):
        group_name = group_dir.name
        combined_file = group_dir / f"{group_name}_combined_results.csv"

        if not combined_file.exists():
            print(f"Skipping {group_name}: missing {combined_file.name}")
            continue

        df = pd.read_csv(combined_file)
        df["group"] = group_name
        combined_tables.append(df)

    if not combined_tables:
        print("No group combined-results files were found.")
        sys.exit(1)

    all_results = pd.concat(combined_tables, ignore_index=True)

    # Keep only one run_name column if duplicates exist
    all_results = all_results.loc[:, ~all_results.columns.duplicated()]

    # Save combined all-group table
    all_out = parent_dir / "all_groups_combined_results.csv"
    all_results.to_csv(all_out, index=False)

    print(f"Saved all-group combined table to: {all_out}")

    # Compute by-group summary statistics
    numeric_cols = all_results.select_dtypes(include=[np.number]).columns.tolist()
    stats_rows = []

    for metric in numeric_cols:
        grouped = all_results.groupby("group")[metric]
        for group_name, values in grouped:
            stats_rows.append({
                "group": group_name,
                "metric": metric,
                "n": values.count(),
                "mean": values.mean(),
                "std": values.std(),
                "min": values.min(),
                "max": values.max(),
            })

    stats_df = pd.DataFrame(stats_rows)
    stats_out = parent_dir / "all_groups_statistics.csv"
    stats_df.to_csv(stats_out, index=False)

    print(f"Saved all-group statistics to: {stats_out}")

    # Print a concise summary
    print("\nGroup comparison summary:")
    print(stats_df)

    # Plot selected metrics across groups
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
        if metric not in all_results.columns:
            continue

        # Boxplot
        grouped_data = []
        labels = []
        for group_name, gdf in all_results.groupby("group"):
            vals = gdf[metric].dropna().values
            if len(vals) > 0:
                grouped_data.append(vals)
                labels.append(group_name)

        if grouped_data:
            plt.figure(figsize=(8, 5))
            plt.boxplot(grouped_data, tick_labels=labels)
            plt.ylabel(metric)
            plt.title(f"{metric} across groups")
            plt.tight_layout()
            plt.savefig(parent_dir / f"{metric}_boxplot.png", dpi=300)
            plt.show()

        # Mean ± std bar chart
        stats_metric = (
            all_results.groupby("group")[metric]
            .agg(["mean", "std"])
            .reset_index()
            .sort_values("group")
        )

        plt.figure(figsize=(8, 5))
        plt.bar(stats_metric["group"], stats_metric["mean"], yerr=stats_metric["std"], capsize=5)
        plt.ylabel(metric)
        plt.title(f"{metric}: mean ± std by group")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(parent_dir / f"{metric}_mean_std.png", dpi=300)
        plt.show()


if __name__ == "__main__":
    main()
