#!/usr/bin/env python3

import sys
import numpy as np
import pandas as pd
from pandas import DataFrame

# =====================================================
# SETTINGS
# =====================================================

COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]

DEFAULT_CONTROL_FILE = "/Users/isabellalopiano/thesis/PX4-Autopilot/turn_control_log.csv"
DEFAULT_SPOOFED_FILE = "/Users/isabellalopiano/thesis/PX4-Autopilot/turn_spoofing100_log.csv"

SPOOF_START_DISTANCE = 100.0

# If True, reject k/threshold pairs that detect during control flights.
USE_CONTROL_SAFETY = True

# Marker rows are:
# 0,0,0,0
SKIP_FIRST_SAMPLE_AFTER_MARKER = True

# Tune search space.
K_VALUES = np.linspace(0.1, 2.0, 191)
THRESH_VALUES = np.linspace(1.0, 30.0, 291)

# Optional: exclude bad runs.
EXCLUDED_CONTROL_RUNS = set()
EXCLUDED_SPOOFED_RUNS = set()

# Example:
EXCLUDED_CONTROL_RUNS = {2, 26, 49, 29, 35}


# =====================================================
# DATA LOADING
# =====================================================

def read_data(filename: str) -> DataFrame:
    df = pd.read_csv(filename, names=COLUMNS)

    for col in COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna().reset_index(drop=True)
    return df


def is_marker_row(row) -> bool:
    return (
        row["of_distance"] == 0
        and row["gps_distance"] == 0
        and row["gyro_magnitude"] == 0
        and row["prev_gyro_magnitude"] == 0
    )


def split_into_runs(df: DataFrame, excluded_runs: set[int]) -> list[DataFrame]:
    runs = []
    current_rows = []
    run_id = 0
    skip_next = False

    for _, row in df.iterrows():
        if is_marker_row(row):
            if current_rows and run_id not in excluded_runs:
                runs.append(pd.DataFrame(current_rows).reset_index(drop=True))

            current_rows = []
            run_id += 1
            skip_next = SKIP_FIRST_SAMPLE_AFTER_MARKER
            continue

        if skip_next:
            skip_next = False
            continue

        current_rows.append(row)

    if current_rows and run_id not in excluded_runs:
        runs.append(pd.DataFrame(current_rows).reset_index(drop=True))

    return runs


# =====================================================
# SIGNAL AND NORMALIZATION
# =====================================================

def compute_control_stats(control_runs: list[DataFrame]) -> tuple[float, float]:
    values = []

    for run in control_runs:
        diff = run["of_distance"] - run["gps_distance"]
        values.extend(diff.to_numpy(dtype=float))

    if len(values) == 0:
        raise ValueError("No control data found.")

    mean = float(np.mean(values))
    sd = float(np.std(values))

    if sd == 0:
        raise ValueError("Control standard deviation is zero.")

    return mean, sd


def make_run_arrays(runs: list[DataFrame], mean: float, sd: float):
    run_arrays = []

    for index, run in enumerate(runs, start=1):
        gps_distance = run["gps_distance"].to_numpy(dtype=float)
        of_distance = run["of_distance"].to_numpy(dtype=float)

        raw_signal = of_distance - gps_distance
        z_signal = (raw_signal - mean) / sd

        gps_total = np.cumsum(gps_distance)
        of_total = np.cumsum(of_distance)

        run_arrays.append({
            "run": index,
            "z_signal": z_signal,
            "gps_total": gps_total,
            "of_total": of_total,
        })

    return run_arrays


# =====================================================
# CUSUM
# =====================================================

def replay_cusum(z_signal: np.ndarray, k: float) -> np.ndarray:
    s_pos = 0.0
    s_neg = 0.0
    cmax = np.zeros(len(z_signal))

    for i, z in enumerate(z_signal):
        s_pos = max(0.0, s_pos + z - k)
        s_neg = max(0.0, s_neg - z - k)
        cmax[i] = max(s_pos, s_neg)

    return cmax


def first_detection_index(cmax: np.ndarray, threshold: float):
    detected = np.flatnonzero(cmax > threshold)

    if len(detected) == 0:
        return None

    return int(detected[0])


def evaluate_pair(control_arrays, spoof_arrays, k: float, threshold: float) -> dict:
    control_false_positives = 0

    if USE_CONTROL_SAFETY:
        for run in control_arrays:
            cmax = replay_cusum(run["z_signal"], k)
            idx = first_detection_index(cmax, threshold)

            if idx is not None:
                control_false_positives += 1

    spoof_false_positives = 0
    true_positives = 0
    missed_detections = 0

    detection_distances_after_spoof = []
    detection_gps_distances = []

    for run in spoof_arrays:
        cmax = replay_cusum(run["z_signal"], k)
        idx = first_detection_index(cmax, threshold)

        if idx is None:
            missed_detections += 1
            continue

        detection_gps_distance = float(run["gps_total"][idx])
        detection_gps_distances.append(detection_gps_distance)

        if detection_gps_distance < SPOOF_START_DISTANCE:
            spoof_false_positives += 1
        else:
            true_positives += 1
            detection_distances_after_spoof.append(
                detection_gps_distance - SPOOF_START_DISTANCE
            )

    total_spoof_runs = len(spoof_arrays)

    return {
        "k": float(k),
        "threshold": float(threshold),
        "control_false_positives": int(control_false_positives),
        "spoof_false_positives": int(spoof_false_positives),
        "true_positives": int(true_positives),
        "missed_detections": int(missed_detections),
        "total_spoof_runs": int(total_spoof_runs),
        "avg_detection_distance_after_spoof": (
            float(np.mean(detection_distances_after_spoof))
            if detection_distances_after_spoof else np.nan
        ),
        "min_detection_distance_after_spoof": (
            float(np.min(detection_distances_after_spoof))
            if detection_distances_after_spoof else np.nan
        ),
        "max_detection_distance_after_spoof": (
            float(np.max(detection_distances_after_spoof))
            if detection_distances_after_spoof else np.nan
        ),
        "std_detection_distance_after_spoof": (
            float(np.std(detection_distances_after_spoof))
            if detection_distances_after_spoof else np.nan
        ),
        "avg_detection_gps_distance": (
            float(np.mean(detection_gps_distances))
            if detection_gps_distances else np.nan
        ),
    }


# =====================================================
# TUNING
# =====================================================

def find_best_pair(control_arrays, spoof_arrays) -> DataFrame:
    rows = []

    total_tests = len(K_VALUES) * len(THRESH_VALUES)
    count = 0

    print(f"Testing {total_tests} k/threshold pairs...")

    for k in K_VALUES:
        for threshold in THRESH_VALUES:
            count += 1

            if count % 1000 == 0:
                print(f"Progress: {count}/{total_tests}")

            result = evaluate_pair(control_arrays, spoof_arrays, k, threshold)
            rows.append(result)

    results = pd.DataFrame(rows)
    results.to_csv("cusum_k_threshold_results.csv", index=False)

    return results


def print_best_results(results: DataFrame, mean: float, sd: float) -> None:
    valid = results.copy()

    if USE_CONTROL_SAFETY:
        valid = valid[valid["control_false_positives"] == 0]

    valid = valid[
        (valid["spoof_false_positives"] == 0)
        & (valid["missed_detections"] == 0)
    ].copy()

    valid.to_csv("cusum_valid_k_threshold_pairs.csv", index=False)

    print("\n============================================================")
    print("BEST VALID RESULTS")
    print("============================================================")

    if len(valid) == 0:
        print("No perfect k/threshold pair found.")
        print("Showing closest candidates instead:\n")

        closest = results.sort_values([
            "control_false_positives",
            "spoof_false_positives",
            "missed_detections",
            "avg_detection_distance_after_spoof",
            "threshold",
            "k",
        ])

        print(closest.head(20).to_string(index=False))
        return

    valid = valid.sort_values([
        "avg_detection_distance_after_spoof",
        "std_detection_distance_after_spoof",
        "threshold",
        "k",
    ])

    best = valid.iloc[0]

    print(valid.head(20).to_string(index=False))

    print("\n============================================================")
    print("RECOMMENDED VALUES")
    print("============================================================")
    print(f"control mean = {mean}")
    print(f"control standard deviation = {sd}")
    print(f"k = {best['k']}")
    print(f"threshold = {best['threshold']}")

    print("\nPerformance:")
    print(f"control false positives = {int(best['control_false_positives'])}")
    print(f"spoof false positives = {int(best['spoof_false_positives'])}")
    print(f"true positives = {int(best['true_positives'])} / {int(best['total_spoof_runs'])}")
    print(f"missed detections = {int(best['missed_detections'])}")
    print(f"avg detection distance after spoof = {best['avg_detection_distance_after_spoof']:.2f} m")
    print(f"min detection distance after spoof = {best['min_detection_distance_after_spoof']:.2f} m")
    print(f"max detection distance after spoof = {best['max_detection_distance_after_spoof']:.2f} m")
    print(f"std detection distance after spoof = {best['std_detection_distance_after_spoof']:.2f} m")

    print("\nC++ values:")
    print(f"double dist_mean = {mean:.6f};")
    print(f"double dist_sd = {sd:.6f};")
    print(f"double k = {best['k']:.6f};")
    print(f"double thresh = {best['threshold']:.6f};")


# =====================================================
# MAIN
# =====================================================

def main(control_file: str, spoofed_file: str) -> None:
    control_df = read_data(control_file)
    spoofed_df = read_data(spoofed_file)

    control_runs = split_into_runs(control_df, EXCLUDED_CONTROL_RUNS)
    spoofed_runs = split_into_runs(spoofed_df, EXCLUDED_SPOOFED_RUNS)

    print("\nLoaded data:")
    print(f"Control runs: {len(control_runs)}")
    print(f"Spoofed runs: {len(spoofed_runs)}")

    mean, sd = compute_control_stats(control_runs)

    print("\nControl statistics:")
    print(f"Mean OF-GPS diff: {mean}")
    print(f"Std OF-GPS diff: {sd}")
    print(f"Spoof start distance: {SPOOF_START_DISTANCE} m")

    control_arrays = make_run_arrays(control_runs, mean, sd)
    spoof_arrays = make_run_arrays(spoofed_runs, mean, sd)

    results = find_best_pair(control_arrays, spoof_arrays)

    print_best_results(results, mean, sd)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        main(DEFAULT_CONTROL_FILE, DEFAULT_SPOOFED_FILE)