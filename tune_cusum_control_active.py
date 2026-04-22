#!/usr/bin/env python3

## Loads the control file.
## Computes baseline_diff from control data only.
## Finds all k/threshold pairs with zero false alarms on control data.
## Loads the spoofing file.
## Tests only the control-safe pairs on spoofing data.
## Picks the pair that detects earliest after GPS cumulative distance reaches 25 m.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =====================================================
# SETTINGS YOU SHOULD EDIT
# =====================================================

CONTROL_FILE = "/home/isabella-lopiano/bachelor-project/PX4-Autopilot/gps_spoofing_log.csv"
SPOOF_FILE = "/home/isabella-lopiano/bachelor-project/PX4-Autopilot/active_gps_spoofing_log.csv"

# Your CSV format:
# of_distance,gps_distance,diff,detected,s_pos,s_neg
HAS_HEADER = False

# If you write a marker row at the start of each run:
# 0.000000,0.000000,0.000000,0,0.000000,0.000000
USE_MARKER_ROWS = True

# Only used if USE_MARKER_ROWS = False.
# If each run has the same number of samples, set these.
# Otherwise leave as None.
CONTROL_RUN_LENGTH = None
SPOOF_RUN_LENGTH = None

# Spoof starts at 25 m according to cumulative GPS distance.
SPOOF_START_GPS_DISTANCE = 25.0

# Grid of CUSUM values to test.
# Wider ranges are okay but take longer.
K_VALUES = np.linspace(0.005, 0.08, 151)         # 0.005, 0.0055, ..., 0.08
THRESH_VALUES = np.linspace(0.5, 3.5, 301)      # 0.5, 0.51, ..., 3.5

# Optional extra safety margin above the worst control CUSUM.
# 0.0 means "zero false alarms on the provided control data."
# Try 0.05 or 0.10 if you want extra safety.
CONTROL_MARGIN = 0.0

# If True, plots are shown at the end.
SHOW_PLOTS = True


# =====================================================
# DATA LOADING
# =====================================================

COLUMNS = ["of_distance", "gps_distance", "diff", "detected", "s_pos", "s_neg"]


def load_log(file_path, has_header=False, use_marker_rows=True, run_length=None):
    if has_header:
        df = pd.read_csv(file_path)
    else:
        df = pd.read_csv(file_path, names=COLUMNS)

    # Recalculate diff to avoid trusting logged diff if formatting changed.
    df["diff"] = df["of_distance"] - df["gps_distance"]
    df["global_sample"] = np.arange(len(df))
    df["logged_cusum_max"] = df[["s_pos", "s_neg"]].max(axis=1)

    if use_marker_rows:
        is_marker = (
            (df["of_distance"] == 0.0) &
            (df["gps_distance"] == 0.0) &
            (df["diff"] == 0.0) &
            (df["detected"] == 0) &
            (df["s_pos"] == 0.0) &
            (df["s_neg"] == 0.0)
        )

        if is_marker.sum() > 0:
            # Each marker starts a new run.
            df["run"] = is_marker.cumsum()

            # If there is data before the first marker, keep it as run 1.
            # Then marker-created runs become 2, 3, ...
            if df.loc[~is_marker, "run"].min() == 0:
                df["run"] = df["run"] + 1

            data = df[~is_marker].copy()
            marker_rows = df.index[is_marker].tolist()
        else:
            # No marker rows found, treat as one run.
            df["run"] = 1
            data = df.copy()
            marker_rows = []
    else:
        if run_length is None:
            df["run"] = 1
        else:
            df["run"] = df.index // run_length + 1

        data = df.copy()
        marker_rows = []

    data["sample_in_run"] = data.groupby("run").cumcount()
    data["gps_total"] = data.groupby("run")["gps_distance"].cumsum()
    data["of_total"] = data.groupby("run")["of_distance"].cumsum()
    data["cumulative_diff"] = data["of_total"] - data["gps_total"]

    return data, marker_rows


def summarize_log(name, data, marker_rows):
    print(f"\n==================== {name} DATA INFO ====================")
    print("Analysis samples:", len(data))
    print("Number of runs:", data["run"].nunique())
    print("Marker rows found:", len(marker_rows))

    if len(marker_rows) > 0:
        print("Marker row numbers:", marker_rows)

    print("\nSamples per run:")
    print(data.groupby("run").size())

    print("\nDiff statistics:")
    print("Mean diff:", data["diff"].mean())
    print("Median diff:", data["diff"].median())
    print("Std diff:", data["diff"].std())
    print("Min diff:", data["diff"].min())
    print("Max diff:", data["diff"].max())
    print("Max abs diff:", data["diff"].abs().max())

    print("\nDiff percentiles:")
    for q in [0.01, 0.05, 0.50, 0.95, 0.99]:
        print(f"{int(q * 100)}th percentile:", data["diff"].quantile(q))

    print("\nLogged CUSUM:")
    print("Max logged s_pos:", data["s_pos"].max())
    print("Max logged s_neg:", data["s_neg"].max())
    print("Max logged CUSUM:", data["logged_cusum_max"].max())
    print("Detected samples:", int(data["detected"].sum()))


# =====================================================
# CUSUM REPLAY
# =====================================================

def make_runs(data, spoof_start_gps_distance=None):
    runs = []

    for run_id, run in data.groupby("run"):
        run = run.copy()

        spoof_start_sample = None
        spoof_start_gps_total = None

        if spoof_start_gps_distance is not None:
            spoof_rows = run[run["gps_total"] >= spoof_start_gps_distance]

            if len(spoof_rows) > 0:
                spoof_start_sample = int(spoof_rows.iloc[0]["sample_in_run"])
                spoof_start_gps_total = float(spoof_rows.iloc[0]["gps_total"])

        runs.append({
            "run_id": int(run_id),
            "diffs": run["diff"].to_numpy(dtype=float),
            "samples": run["sample_in_run"].to_numpy(dtype=int),
            "gps_total": run["gps_total"].to_numpy(dtype=float),
            "spoof_start_sample": spoof_start_sample,
            "spoof_start_gps_total": spoof_start_gps_total,
        })

    return runs


def replay_cusum_for_k(diffs, k, baseline_diff):
    s_pos = np.zeros(len(diffs))
    s_neg = np.zeros(len(diffs))

    pos = 0.0
    neg = 0.0

    for i, diff in enumerate(diffs):
        pos = max(0.0, pos + diff - baseline_diff - k)
        neg = max(0.0, neg - diff + baseline_diff - k)

        s_pos[i] = pos
        s_neg[i] = neg

    cmax = np.maximum(s_pos, s_neg)
    return s_pos, s_neg, cmax


def first_crossing(cmax, threshold):
    crossing = np.flatnonzero(cmax > threshold)

    if len(crossing) == 0:
        return None

    return int(crossing[0])


# =====================================================
# TUNING LOGIC
# =====================================================

def find_control_safe_pairs(control_runs, baseline_diff, k_values, thresh_values, margin=0.0):
    rows = []

    print("\n==================== STEP 1: CONTROL FALSE-ALARM TEST ====================")

    for i, k in enumerate(k_values):
        if i % 25 == 0:
            print(f"Control progress: k {i + 1}/{len(k_values)}")

        max_control_cusum = 0.0
        per_run_max = []

        for run in control_runs:
            _, _, cmax = replay_cusum_for_k(run["diffs"], k, baseline_diff)
            run_max = float(np.max(cmax)) if len(cmax) > 0 else 0.0
            per_run_max.append(run_max)
            max_control_cusum = max(max_control_cusum, run_max)

        for threshold in thresh_values:
            false_alarm = max_control_cusum > threshold
            safe = max_control_cusum <= (threshold - margin)

            rows.append({
                "k": float(k),
                "threshold": float(threshold),
                "control_safe": bool(safe),
                "control_false_alarm": bool(false_alarm),
                "control_max_cusum": float(max_control_cusum),
                "control_margin": float(threshold - max_control_cusum),
            })

    control_results = pd.DataFrame(rows)
    safe_pairs = control_results[control_results["control_safe"]].copy()

    print("\nControl-safe pairs:", len(safe_pairs), "/", len(control_results))

    if len(safe_pairs) == 0:
        print("No safe pairs found. Try increasing THRESH_VALUES max or K_VALUES max.")
    else:
        print("\nLowest-threshold safe pairs:")
        print(safe_pairs.sort_values(["threshold", "k"]).head(20))

    return control_results, safe_pairs


def test_safe_pairs_on_spoof(spoof_runs, safe_pairs, baseline_diff):
    rows = []

    print("\n==================== STEP 2: SPOOF DETECTION TEST ====================")

    if len(safe_pairs) == 0:
        return pd.DataFrame()

    # Group by k so we replay each spoof run only once per k.
    grouped = safe_pairs.groupby("k")

    for k_index, (k, group) in enumerate(grouped):
        if k_index % 25 == 0:
            print(f"Spoof progress: k group {k_index + 1}/{len(grouped)}")

        replayed = []

        for run in spoof_runs:
            _, _, cmax = replay_cusum_for_k(run["diffs"], k, baseline_diff)

            replayed.append({
                **run,
                "cmax": cmax,
                "max_cusum": float(np.max(cmax)) if len(cmax) > 0 else 0.0,
            })

        for _, pair in group.iterrows():
            threshold = float(pair["threshold"])

            false_alarms_before_spoof = 0
            missed_detections = 0
            detections_after_spoof = 0
            delays_samples = []
            delays_distance = []
            detection_samples = []
            detection_gps_totals = []

            for rr in replayed:
                idx = first_crossing(rr["cmax"], threshold)

                if idx is None:
                    detection_sample = None
                    detection_gps_total = None
                else:
                    detection_sample = int(rr["samples"][idx])
                    detection_gps_total = float(rr["gps_total"][idx])

                spoof_start_sample = rr["spoof_start_sample"]
                spoof_start_gps_total = rr["spoof_start_gps_total"]

                if spoof_start_sample is None:
                    # This run never reached the spoof start distance.
                    missed_detections += 1
                    continue

                if detection_sample is None:
                    missed_detections += 1
                elif detection_sample < spoof_start_sample:
                    false_alarms_before_spoof += 1
                else:
                    detections_after_spoof += 1
                    delays_samples.append(detection_sample - spoof_start_sample)
                    delays_distance.append(detection_gps_total - spoof_start_gps_total)
                    detection_samples.append(detection_sample)
                    detection_gps_totals.append(detection_gps_total)

            rows.append({
                "k": float(k),
                "threshold": threshold,
                "control_max_cusum": float(pair["control_max_cusum"]),
                "control_margin": float(pair["control_margin"]),
                "false_alarms_before_spoof": int(false_alarms_before_spoof),
                "missed_detections": int(missed_detections),
                "detections_after_spoof": int(detections_after_spoof),
                "total_spoof_runs": int(len(spoof_runs)),
                "avg_delay_samples": float(np.mean(delays_samples)) if len(delays_samples) > 0 else np.nan,
                "max_delay_samples": float(np.max(delays_samples)) if len(delays_samples) > 0 else np.nan,
                "avg_detection_distance_after_spoof": float(np.mean(delays_distance)) if len(delays_distance) > 0 else np.nan,
                "max_detection_distance_after_spoof": float(np.max(delays_distance)) if len(delays_distance) > 0 else np.nan,
                "avg_detection_gps_total": float(np.mean(detection_gps_totals)) if len(detection_gps_totals) > 0 else np.nan,
            })

    return pd.DataFrame(rows)


# =====================================================
# MAIN
# =====================================================

def main():
    control_data, control_markers = load_log(
        CONTROL_FILE,
        has_header=HAS_HEADER,
        use_marker_rows=USE_MARKER_ROWS,
        run_length=CONTROL_RUN_LENGTH
    )

    spoof_data, spoof_markers = load_log(
        SPOOF_FILE,
        has_header=HAS_HEADER,
        use_marker_rows=USE_MARKER_ROWS,
        run_length=SPOOF_RUN_LENGTH
    )

    summarize_log("CONTROL", control_data, control_markers)
    summarize_log("SPOOF", spoof_data, spoof_markers)

    # IMPORTANT: baseline comes from control data only.
    baseline_diff = control_data["diff"].mean()
    control_std_diff = control_data["diff"].std()

    print("\n==================== BASELINE FROM CONTROL DATA ====================")
    print("baseline_diff:", baseline_diff)
    print("control std diff:", control_std_diff)

    control_runs = make_runs(control_data, spoof_start_gps_distance=None)
    spoof_runs = make_runs(spoof_data, spoof_start_gps_distance=SPOOF_START_GPS_DISTANCE)

    control_results, safe_pairs = find_control_safe_pairs(
        control_runs,
        baseline_diff,
        K_VALUES,
        THRESH_VALUES,
        margin=CONTROL_MARGIN
    )

    spoof_results = test_safe_pairs_on_spoof(
        spoof_runs,
        safe_pairs,
        baseline_diff
    )

    control_results.to_csv("control_grid_results.csv", index=False)
    safe_pairs.to_csv("control_safe_pairs.csv", index=False)

    if len(spoof_results) > 0:
        spoof_results.to_csv("combined_spoof_results.csv", index=False)

    print("\n==================== STEP 3: FINAL CANDIDATE SELECTION ====================")

    if len(spoof_results) == 0:
        print("No spoof results available.")
        return

    # Final valid settings:
    # 1. safe on control
    # 2. no false alarm before 25 m on spoof runs
    # 3. no missed detections
    final = spoof_results[
        (spoof_results["false_alarms_before_spoof"] == 0) &
        (spoof_results["missed_detections"] == 0)
    ].copy()

    if len(final) == 0:
        print("No k/threshold pair was both control-safe and detected every spoof run.")
        print("Try increasing detection sensitivity, extending the spoof runs, or adding more control/spoof data.")
        print("\nClosest spoof results:")
        print(spoof_results.sort_values([
            "missed_detections",
            "false_alarms_before_spoof",
            "avg_detection_distance_after_spoof"
        ]).head(20))
        return

    final = final.sort_values([
        "avg_detection_distance_after_spoof",
        "avg_delay_samples",
        "control_margin",
        "threshold",
        "k"
    ])

    print("\nTop final candidates:")
    print(final.head(20))

    best = final.iloc[0]

    print("\n==================== RECOMMENDED VALUES ====================")
    print("Use baseline_diff from CONTROL data:")
    print("baseline_diff =", baseline_diff)
    print("k =", best["k"])
    print("threshold =", best["threshold"])
    print()
    print("Performance summary:")
    print("control_max_cusum =", best["control_max_cusum"])
    print("control_margin =", best["control_margin"])
    print("false_alarms_before_spoof =", int(best["false_alarms_before_spoof"]))
    print("missed_detections =", int(best["missed_detections"]))
    print("detections_after_spoof =", int(best["detections_after_spoof"]), "/", int(best["total_spoof_runs"]))
    print("avg_delay_samples =", best["avg_delay_samples"])
    print("max_delay_samples =", best["max_delay_samples"])
    print("avg_detection_distance_after_spoof =", best["avg_detection_distance_after_spoof"])
    print("max_detection_distance_after_spoof =", best["max_detection_distance_after_spoof"])
    print()
    print("C++ values:")
    print(f"double baseline_diff = {baseline_diff:.6f};")
    print(f"double k = {best['k']:.6f};")
    print(f"double thresh = {best['threshold']:.6f};")

    if SHOW_PLOTS:
        # Plot control max CUSUM vs k for threshold-independent view.
        best_control_by_k = control_results.groupby("k")["control_max_cusum"].max().reset_index()

        plt.figure()
        plt.plot(best_control_by_k["k"], best_control_by_k["control_max_cusum"], label="Max CUSUM on control")
        plt.axhline(best["threshold"], linestyle="--", label=f"chosen threshold = {best['threshold']:.3f}")
        plt.xlabel("k")
        plt.ylabel("Max CUSUM on control data")
        plt.title("Control False-Alarm Margin")
        plt.legend()
        plt.grid()
        plt.show()

        # Plot final candidates as k vs threshold, colored by detection distance.
        plt.figure()
        scatter = plt.scatter(
            final["k"],
            final["threshold"],
            c=final["avg_detection_distance_after_spoof"]
        )
        plt.colorbar(scatter, label="Avg detection distance after spoof [m]")
        plt.scatter([best["k"]], [best["threshold"]], marker="x", s=150, label="chosen")
        plt.xlabel("k")
        plt.ylabel("threshold")
        plt.title("Final Valid Candidates")
        plt.legend()
        plt.grid()
        plt.show()

        # Plot raw diff data for both files.
        plt.figure()
        plt.plot(control_data["global_sample"], control_data["diff"], label="control diff")
        plt.axhline(baseline_diff, linestyle="--", label="control baseline")
        plt.xlabel("Sample")
        plt.ylabel("diff = OF - GPS")
        plt.title("Control Diff")
        plt.legend()
        plt.grid()
        plt.show()

        plt.figure()
        plt.plot(spoof_data["global_sample"], spoof_data["diff"], label="spoof diff")
        plt.axhline(baseline_diff, linestyle="--", label="control baseline")
        plt.xlabel("Sample")
        plt.ylabel("diff = OF - GPS")
        plt.title("Spoof Diff")
        plt.legend()
        plt.grid()
        plt.show()


if __name__ == "__main__":
    main()