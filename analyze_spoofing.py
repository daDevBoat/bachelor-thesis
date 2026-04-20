import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =========================
# Settings
# =========================

file_path = "/home/isabella-lopiano/bachelor-project/PX4-Autopilot/gps_spoofing_log.csv"

HAS_HEADER = False

TOP_DISTANCE_CUTOFF = 0.75

THRESHOLD = 1.5
TARGET_FALSE_ALARM_RATE = 0.01   # 1%

K_MIN = 0.01
K_MAX = 0.50
K_STEPS = 300

WINDOW_SIZE = 50
# This means each false-alarm test uses 50 samples.
# If your detector runs continuously, this is a reasonable "test chunk."
# You can try 25, 50, 100 and compare.


# =========================
# Load data
# =========================

if HAS_HEADER:
    df = pd.read_csv(file_path)
else:
    df = pd.read_csv(file_path, names=["of_distance", "gps_distance", "diff"])

df["diff"] = df["of_distance"] - df["gps_distance"]
df["sample"] = np.arange(len(df))


# =========================
# Keep only top / steady sections
# =========================

top = df[
    (df["of_distance"] > TOP_DISTANCE_CUTOFF) &
    (df["gps_distance"] > TOP_DISTANCE_CUTOFF)
].copy()

baseline_diff = top["diff"].mean()
std_diff = top["diff"].std()

print("Total samples:", len(df))
print("Top samples used:", len(top))
print("baseline_diff:", baseline_diff)
print("std_diff:", std_diff)


# =========================
# Split into continuous top segments
# =========================

top["segment"] = (top["sample"].diff() > 1).cumsum()

segments = []

for _, seg in top.groupby("segment"):
    if len(seg) >= WINDOW_SIZE:
        segments.append(seg["diff"].values)

print("Number of top segments:", len(segments))


# =========================
# Make windows from normal data
# =========================

windows = []

for diffs in segments:
    for start in range(0, len(diffs) - WINDOW_SIZE + 1, WINDOW_SIZE):
        window = diffs[start:start + WINDOW_SIZE]
        windows.append(window)

print("Number of control windows:", len(windows))

if len(windows) < 100:
    print("WARNING: You have fewer than 100 windows.")
    print("A 1% false alarm rate is hard to estimate accurately with this little data.")


# =========================
# CUSUM test
# =========================

def window_triggers_alarm(diffs, k, threshold, baseline_diff):
    s_pos = 0.0
    s_neg = 0.0

    for diff in diffs:
        s_pos = max(0.0, s_pos + diff - baseline_diff - k)
        s_neg = max(0.0, s_neg - diff + baseline_diff - k)

        if s_pos > threshold or s_neg > threshold:
            return True

    return False


# =========================
# Sweep k values
# =========================

k_values = np.linspace(K_MIN, K_MAX, K_STEPS)
results = []

for k in k_values:
    alarms = 0

    for window in windows:
        if window_triggers_alarm(window, k, THRESHOLD, baseline_diff):
            alarms += 1

    false_alarm_rate = alarms / len(windows)

    results.append({
        "k": k,
        "alarms": alarms,
        "total_windows": len(windows),
        "false_alarm_rate": false_alarm_rate
    })

results_df = pd.DataFrame(results)


# =========================
# Pick recommended k
# =========================

safe = results_df[
    results_df["false_alarm_rate"] <= TARGET_FALSE_ALARM_RATE
]

if len(safe) > 0:
    best_k = safe.iloc[0]["k"]

    print()
    print("Recommended k:", best_k)
    print("False alarm rate:", safe.iloc[0]["false_alarm_rate"])
    print("Alarms:", int(safe.iloc[0]["alarms"]), "/", int(safe.iloc[0]["total_windows"]))

else:
    best_k = None

    print()
    print("No k in this range achieved 1% false alarm rate.")
    print("Try increasing K_MAX or increasing THRESHOLD.")


# =========================
# Show nearby results
# =========================

print()
print("Best candidates:")
print(results_df[results_df["false_alarm_rate"] <= 0.05].head(20))


# =========================
# Plot false alarm rate vs k
# =========================

plt.figure()
plt.plot(results_df["k"], results_df["false_alarm_rate"], label="False alarm rate")
plt.axhline(TARGET_FALSE_ALARM_RATE, linestyle="--", label="1% target")

if best_k is not None:
    plt.axvline(best_k, linestyle="--", label=f"recommended k = {best_k:.4f}")

plt.xlabel("k")
plt.ylabel("False alarm rate")
plt.title("False alarm rate vs k using control data")
plt.legend()
plt.grid()
plt.show()