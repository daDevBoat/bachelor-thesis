#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =====================================================
# User settings
# =====================================================

FILE_PATH = "/home/isabella-lopiano/bachelor-project/PX4-Autopilot/gps_spoofing_log.csv"

# If you add a marker row at the start of each run:
# 0.000000,0.000000,0.000000,0,0.000000,0.000000
# leave this True.
USE_MARKER_ROWS = True

# If you do NOT use marker rows, but every run has the same length,
# set RUN_LENGTH to that number. Otherwise leave as None.
RUN_LENGTH = None

# Set this to None for control/no-spoofing data.
# Set to 25.0 for active-spoofing data where spoof starts at 25 m GPS distance.
# SPOOF_START_GPS_DISTANCE = None
SPOOF_START_GPS_DISTANCE = 25.0

CONTROL_MEAN_DIFF = -0.004073260416666667

# Candidate values for replay tuning
K_VALUES = np.linspace(0.005, 0.08, 151)
THRESH_VALUES = np.linspace(0.5, 3.0, 251)


# =====================================================
# Load data
# =====================================================

df = pd.read_csv(
        FILE_PATH,
        names=["of_distance", "gps_distance", "diff", "detected", "s_pos", "s_neg"]
    )

# Recalculate diff to be safe
df["diff"] = df["of_distance"] - df["gps_distance"]
df["sample"] = np.arange(len(df))
df["cusum_max_logged"] = df[["s_pos", "s_neg"]].max(axis=1)


# =====================================================
# Detect run starts
# =====================================================

if USE_MARKER_ROWS:
    # Marker row written by your C++ code:
    # 0.000000,0.000000,0.000000,0,0.000000,0.000000
    is_marker = (
        (df["of_distance"] == 0.0) &
        (df["gps_distance"] == 0.0) &
        (df["diff"] == 0.0) &
        (df["detected"] == 0) &
        (df["s_pos"] == 0.0) &
        (df["s_neg"] == 0.0)
    )

    # If the file does not start with a marker, force the first row to start run 1.
    if len(df) > 0 and not bool(is_marker.iloc[0]):
        is_marker.iloc[0] = True

    df["run"] = is_marker.cumsum()

    # Remove marker rows from actual analysis.
    data = df[~is_marker].copy()

else:
    if RUN_LENGTH is None:
        df["run"] = 1
        data = df.copy()
    else:
        df["run"] = df.index // RUN_LENGTH + 1
        data = df.copy()

# Sample number inside each run
data["sample_in_run"] = data.groupby("run").cumcount()

# Add cumulative distances per run
data["gps_total"] = data.groupby("run")["gps_distance"].cumsum()
data["of_total"] = data.groupby("run")["of_distance"].cumsum()
data["cumulative_diff"] = data["of_total"] - data["gps_total"]


# =====================================================
# Basic statistics
# =====================================================

print("\n==================== BASIC DATA INFO ====================")
print("Total raw rows:", len(df))
print("Analysis samples, excluding marker rows:", len(data))
print("Number of runs:", data["run"].nunique())

if USE_MARKER_ROWS:
    marker_rows = df.index.difference(data.index).tolist()
    print("Detected marker rows:", len(marker_rows))
    print("Run start row numbers:", marker_rows)

print("\nSamples per run:")
print(data.groupby("run").size())

print("\n==================== DIFF STATISTICS ====================")
print("Mean diff:", data["diff"].mean())
print("Median diff:", data["diff"].median())
print("Std diff:", data["diff"].std())
print("Min diff:", data["diff"].min())
print("Max diff:", data["diff"].max())
print("Max abs diff:", data["diff"].abs().max())

print("\nDiff percentiles:")
for q in [0.01, 0.05, 0.50, 0.95, 0.99]:
    print(f"{int(q * 100)}th percentile:", data["diff"].quantile(q))

print("\n==================== LOGGED CUSUM STATISTICS ====================")
print("Max logged s_pos:", data["s_pos"].max())
print("Max logged s_neg:", data["s_neg"].max())
print("Max logged CUSUM:", data["cusum_max_logged"].max())
print("Number of detected samples:", int(data["detected"].sum()))

detected_rows = data[data["detected"] == 1]

if len(detected_rows) > 0:
    first_detection = detected_rows.iloc[0]
    print("First detection global sample:", int(first_detection["sample"]))
    print("First detection run:", int(first_detection["run"]))
    print("First detection sample in run:", int(first_detection["sample_in_run"]))
    print("GPS total at first detection:", first_detection["gps_total"])
else:
    print("No detection in logged data.")


# =====================================================
# Per-run summary
# =====================================================

print("\n==================== PER-RUN SUMMARY ====================")

run_summaries = []

for run_id, run in data.groupby("run"):
    spoof_start_sample = None
    spoof_start_gps = None

    if SPOOF_START_GPS_DISTANCE is not None:
        spoof_rows = run[run["gps_total"] >= SPOOF_START_GPS_DISTANCE]

        if len(spoof_rows) > 0:
            spoof_start_sample = int(spoof_rows.iloc[0]["sample_in_run"])
            spoof_start_gps = float(spoof_rows.iloc[0]["gps_total"])

    detected = run[run["detected"] == 1]

    first_detection_sample = None
    detection_delay_samples = None
    detection_gps_total = None

    if len(detected) > 0:
        first_detection_sample = int(detected.iloc[0]["sample_in_run"])
        detection_gps_total = float(detected.iloc[0]["gps_total"])

        if spoof_start_sample is not None:
            detection_delay_samples = first_detection_sample - spoof_start_sample

    run_summaries.append({
        "run": run_id,
        "samples": len(run),
        "mean_diff": run["diff"].mean(),
        "std_diff": run["diff"].std(),
        "min_diff": run["diff"].min(),
        "max_diff": run["diff"].max(),
        "max_abs_diff": run["diff"].abs().max(),
        "max_s_pos": run["s_pos"].max(),
        "max_s_neg": run["s_neg"].max(),
        "max_logged_cusum": run["cusum_max_logged"].max(),
        "spoof_start_sample": spoof_start_sample,
        "spoof_start_gps_total": spoof_start_gps,
        "first_detection_sample": first_detection_sample,
        "detection_delay_samples": detection_delay_samples,
        "detection_gps_total": detection_gps_total,
    })

run_summary_df = pd.DataFrame(run_summaries)
print(run_summary_df)


# =====================================================
# Replay CUSUM for candidate k and threshold values
# =====================================================

baseline_diff = CONTROL_MEAN_DIFF

print("\n==================== BASELINE FOR REPLAY ====================")
print("Suggested baseline_diff:", baseline_diff)
print("Suggested k from std diff:", data["diff"].std())

def replay_cusum(run, k, threshold, baseline_diff):
    s_pos = 0.0
    s_neg = 0.0

    max_cusum = 0.0
    detection_sample = None
    detection_gps_total = None
    detection_direction = None

    for _, row in run.iterrows():
        diff = row["diff"]

        s_pos = max(0.0, s_pos + diff - baseline_diff - k)
        s_neg = max(0.0, s_neg - diff + baseline_diff - k)

        max_cusum = max(max_cusum, s_pos, s_neg)

        if detection_sample is None:
            if s_pos > threshold:
                detection_sample = int(row["sample_in_run"])
                detection_gps_total = float(row["gps_total"])
                detection_direction = "s_pos"
            elif s_neg > threshold:
                detection_sample = int(row["sample_in_run"])
                detection_gps_total = float(row["gps_total"])
                detection_direction = "s_neg"

    return max_cusum, detection_sample, detection_gps_total, detection_direction


results = []

for k in K_VALUES:
    for threshold in THRESH_VALUES:
        false_alarms = 0
        detections_after_spoof = 0
        missed_detections = 0
        delays = []
        detection_distances_after_spoof = []
        max_cusums = []

        for run_id, run in data.groupby("run"):
            max_cusum, detection_sample, detection_gps_total, direction = replay_cusum(
                run,
                k,
                threshold,
                baseline_diff
            )

            max_cusums.append(max_cusum)

            if SPOOF_START_GPS_DISTANCE is None:
                # Control data: any detection is a false alarm.
                if detection_sample is not None:
                    false_alarms += 1
            else:
                spoof_rows = run[run["gps_total"] >= SPOOF_START_GPS_DISTANCE]

                if len(spoof_rows) == 0:
                    continue

                spoof_start_sample = int(spoof_rows.iloc[0]["sample_in_run"])
                spoof_start_gps_total = float(spoof_rows.iloc[0]["gps_total"])

                if detection_sample is None:
                    missed_detections += 1
                elif detection_sample < spoof_start_sample:
                    false_alarms += 1
                else:
                    detections_after_spoof += 1
                    delays.append(detection_sample - spoof_start_sample)
                    detection_distances_after_spoof.append(
                        detection_gps_total - spoof_start_gps_total
                    )

        total_runs = data["run"].nunique()

        results.append({
            "k": k,
            "threshold": threshold,
            "false_alarms": false_alarms,
            "missed_detections": missed_detections,
            "detections_after_spoof": detections_after_spoof,
            "total_runs": total_runs,
            "avg_delay_samples": np.mean(delays) if len(delays) > 0 else np.nan,
            "max_delay_samples": np.max(delays) if len(delays) > 0 else np.nan,
            "avg_detection_distance_after_spoof": np.mean(detection_distances_after_spoof) if len(detection_distances_after_spoof) > 0 else np.nan,
            "max_detection_distance_after_spoof": np.max(detection_distances_after_spoof) if len(detection_distances_after_spoof) > 0 else np.nan,
            "max_cusum": np.max(max_cusums),
        })

results_df = pd.DataFrame(results)


# =====================================================
# Candidate selection
# =====================================================

print("\n==================== BEST CANDIDATES ====================")

if SPOOF_START_GPS_DISTANCE is None:
    # Control data: best means no false alarms.
    candidates = results_df[results_df["false_alarms"] == 0].copy()

    # Sort by threshold first so you can see the lowest threshold that survives.
    candidates = candidates.sort_values(["threshold", "k"])
else:
    # Active spoofing data:
    # 1. no false alarms before spoof
    # 2. no missed detections
    # 3. fastest detection
    candidates = results_df[
        (results_df["false_alarms"] == 0) &
        (results_df["missed_detections"] == 0)
    ].copy()

    candidates = candidates.sort_values([
        "avg_detection_distance_after_spoof",
        "avg_delay_samples",
        "threshold",
        "k"
    ])

print(candidates.head(20))

if len(candidates) > 0:
    best = candidates.iloc[0]

    print("\n==================== RECOMMENDED VALUES ====================")
    print("baseline_diff =", baseline_diff)
    print("k =", best["k"])
    print("threshold =", best["threshold"])
    print("false_alarms =", int(best["false_alarms"]))
    print("missed_detections =", int(best["missed_detections"]))

    if SPOOF_START_GPS_DISTANCE is not None:
        print("avg_delay_samples =", best["avg_delay_samples"])
        print("max_delay_samples =", best["max_delay_samples"])
        print("avg_detection_distance_after_spoof =", best["avg_detection_distance_after_spoof"])
        print("max_detection_distance_after_spoof =", best["max_detection_distance_after_spoof"])


# =====================================================
# Plots
# =====================================================

plt.figure()
plt.plot(data["sample"], data["of_distance"], label="OF distance")
plt.plot(data["sample"], data["gps_distance"], label="GPS distance")
plt.xlabel("Sample")
plt.ylabel("Distance")
plt.title("OF Distance vs GPS Distance")
plt.legend()
plt.grid()
plt.show()

plt.figure()
plt.plot(data["sample"], data["diff"], label="diff = OF - GPS")
plt.axhline(data["diff"].mean(), linestyle="--", label="mean diff")
plt.axhline(data["diff"].mean() + data["diff"].std(), linestyle="--", label="+1 std")
plt.axhline(data["diff"].mean() - data["diff"].std(), linestyle="--", label="-1 std")
plt.xlabel("Sample")
plt.ylabel("Diff")
plt.title("Diff Across Analysis Samples")
plt.legend()
plt.grid()
plt.show()

plt.figure()
plt.plot(data["sample"], data["s_pos"], label="logged s_pos")
plt.plot(data["sample"], data["s_neg"], label="logged s_neg")
plt.xlabel("Sample")
plt.ylabel("CUSUM value")
plt.title("Logged CUSUM Values")
plt.legend()
plt.grid()
plt.show()

plt.figure()
plt.hist(data["diff"], bins=50)
plt.xlabel("diff = OF - GPS")
plt.ylabel("Count")
plt.title("Distribution of Diff Values")
plt.grid()
plt.show()