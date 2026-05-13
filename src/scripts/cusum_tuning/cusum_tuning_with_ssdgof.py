#!/usr/bin/env python3

import sys
import pandas as pd
from pandas import DataFrame

# =====================================================
# SETTINGS
# =====================================================

COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]

# Print run summaries and immediate detections.
TEST_PRINTING = True

# If True, pauses after every sample. Usually keep this False.
MANUAL_STEPS = False

# Normalize CUSUM inputs using mean and standard deviation from control data.
NORMALIZE = True

# Spoofing starts when cumulative GPS distance passes this value.
SPOOF_START_DISTANCE = 25.0

# SSDGOF threshold, matching your C++ _sensitivity_threshold.
SSDGOF_THRESHOLD = 10.0

# CUSUM threshold used on spoofed flights.
CUSUM_THRESHOLD = 11.0 * 1.1

# CUSUM k values.
# If NORMALIZE is True, these are in standard-deviation units.
DIST_K_NORMALIZED = 0.5
GYRO_K_NORMALIZED = 0.8

# If NORMALIZE is False, these are in raw units.
DIST_K_RAW = 0.0132
GYRO_K_RAW = DIST_K_RAW

# Your current default files. These can also be overridden from the command line.
DEFAULT_CONTROL_FILE = "/Users/isabellalopiano/Downloads/straight_control_log_cleaned.csv"
DEFAULT_SPOOFED_FILE = "/Users/isabellalopiano/thesis/PX4-Autopilot/straight_spoofing25_log.csv"

# Your marker row is all zeros. The original script skipped the marker row and the
# row immediately after it. Keeping this True preserves that behavior.
SKIP_FIRST_SAMPLE_AFTER_MARKER = True


# =====================================================
# DATA LOADING AND RUN SPLITTING
# =====================================================

def read_data(filename: str) -> DataFrame:
    csv_df = pd.read_csv(filename, names=COLUMNS)

    for col in COLUMNS:
        csv_df[col] = pd.to_numeric(csv_df[col], errors="coerce")

    csv_df = csv_df.dropna().reset_index(drop=True)
    return csv_df


def is_marker_row(row) -> bool:
    return (
        row["of_distance"] == 0
        and row["gps_distance"] == 0
        and row["gyro_magnitude"] == 0
        and row["prev_gyro_magnitude"] == 0
    )


def split_into_runs(df: DataFrame) -> list[DataFrame]:
    runs = []
    current_rows = []
    skip_next = False

    for _, row in df.iterrows():
        if is_marker_row(row):
            if current_rows:
                runs.append(pd.DataFrame(current_rows).reset_index(drop=True))
                current_rows = []

            skip_next = SKIP_FIRST_SAMPLE_AFTER_MARKER
            continue

        if skip_next:
            skip_next = False
            continue

        current_rows.append(row)

    if current_rows:
        runs.append(pd.DataFrame(current_rows).reset_index(drop=True))

    return runs


# =====================================================
# CONTROL STATISTICS
# =====================================================

def compute_means(df: DataFrame) -> tuple[float, float]:
    runs = split_into_runs(df)

    dist_diffs = []
    gyro_diffs = []

    for run in runs:
        dist_diffs.extend((run["of_distance"] - run["gps_distance"]).tolist())
        gyro_diffs.extend((run["gyro_magnitude"] - run["prev_gyro_magnitude"]).tolist())

    if len(dist_diffs) == 0 or len(gyro_diffs) == 0:
        raise ValueError("No usable rows found while computing means.")

    return float(pd.Series(dist_diffs).mean()), float(pd.Series(gyro_diffs).mean())


def compute_deviation(df: DataFrame, dist_mean: float, gyro_mean: float) -> tuple[float, float]:
    runs = split_into_runs(df)

    dist_squared = []
    gyro_squared = []

    for run in runs:
        dist_diff = run["of_distance"] - run["gps_distance"]
        gyro_diff = run["gyro_magnitude"] - run["prev_gyro_magnitude"]

        dist_squared.extend(((dist_diff - dist_mean) ** 2).tolist())
        gyro_squared.extend(((gyro_diff - gyro_mean) ** 2).tolist())

    if len(dist_squared) == 0 or len(gyro_squared) == 0:
        raise ValueError("No usable rows found while computing standard deviation.")

    # This matches the original script: sqrt(sum / N), not sample std with N - 1.
    dist_sd = float((sum(dist_squared) / len(dist_squared)) ** 0.5)
    gyro_sd = float((sum(gyro_squared) / len(gyro_squared)) ** 0.5)

    if dist_sd == 0 or gyro_sd == 0:
        raise ValueError("Standard deviation is zero. CUSUM normalization would divide by zero.")

    return dist_sd, gyro_sd


# =====================================================
# CUSUM HELPERS
# =====================================================

def cusum(diff: float, mean: float, sd: float, s_pos: float, s_neg: float, k: float) -> tuple[float, float]:
    if NORMALIZE:
        z = (diff - mean) / sd
    else:
        z = diff

    s_pos = max(0.0, s_pos + z - k)
    s_neg = max(0.0, s_neg - z - k)
    return s_pos, s_neg


def cusum_abs(diff: float, mean: float, sd: float, s: float, k: float) -> float:
    if NORMALIZE:
        z = abs(diff - mean) / sd
    else:
        z = abs(diff)

    s = max(0.0, s + z - k)
    return s


# =====================================================
# CUSUM TEST
# =====================================================

def test_cusum(
    df: DataFrame,
    mean1: float,
    sd1: float,
    k1: float,
    threshold: float,
    mean2: float,
    sd2: float,
    k2: float,
    label: str = "",
) -> tuple[float, float, float]:
    runs = split_into_runs(df)

    max_dist_s_pos = 0.0
    max_dist_s_neg = 0.0
    max_gyro_s = 0.0

    if TEST_PRINTING:
        print(f"\n\nCUSUM ANALYSIS: {label}")
        print("-------------------------------------------")
        print(f"Runs found: {len(runs)}")
        print(f"Threshold: {threshold}\n")

    for run_index, run_df in enumerate(runs, start=1):
        dist_s_pos = 0.0
        dist_s_neg = 0.0
        gyro_s = 0.0

        run_max_dist_s_pos = 0.0
        run_max_dist_s_neg = 0.0
        run_max_gyro_s = 0.0

        total_gps_distance = 0.0
        total_of_distance = 0.0

        cusum_detected = False
        detection_gps_distance = None
        detection_of_distance = None
        detection_delay_distance = None
        detection_delay_seconds = None
        updates_after_spoof_start = 0

        for row_index, row in run_df.iterrows():
            dist_diff = row["of_distance"] - row["gps_distance"]
            dist_s_pos, dist_s_neg = cusum(dist_diff, mean1, sd1, dist_s_pos, dist_s_neg, k1)

            total_gps_distance += row["gps_distance"]
            total_of_distance += row["of_distance"]

            gyro_diff = row["gyro_magnitude"] - row["prev_gyro_magnitude"]
            gyro_s = cusum_abs(gyro_diff, mean2, sd2, gyro_s, k2)

            run_max_dist_s_pos = max(run_max_dist_s_pos, dist_s_pos)
            run_max_dist_s_neg = max(run_max_dist_s_neg, dist_s_neg)
            run_max_gyro_s = max(run_max_gyro_s, gyro_s)

            if total_gps_distance > SPOOF_START_DISTANCE and not cusum_detected:
                updates_after_spoof_start += 1

            if threshold > 0 and not cusum_detected and (dist_s_pos > threshold or dist_s_neg > threshold):
                cusum_detected = True
                detection_gps_distance = total_gps_distance
                detection_of_distance = total_of_distance
                detection_delay_distance = total_gps_distance - SPOOF_START_DISTANCE
                detection_delay_seconds = updates_after_spoof_start * 0.2

                if TEST_PRINTING:
                    print(
                        f"CUSUM DETECTED in run {run_index}: "
                        f"GPS distance={detection_gps_distance:.2f} m, "
                        f"OF distance={detection_of_distance:.2f} m, "
                        f"delay={detection_delay_distance:.2f} m, "
                        f"s_pos={dist_s_pos:.3f}, s_neg={dist_s_neg:.3f}"
                    )

            if TEST_PRINTING and MANUAL_STEPS:
                print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
                print(f"dist_s_pos: {dist_s_pos}, dist_s_neg: {dist_s_neg}, gyro_s: {gyro_s}")
                input("")

        max_dist_s_pos = max(max_dist_s_pos, run_max_dist_s_pos)
        max_dist_s_neg = max(max_dist_s_neg, run_max_dist_s_neg)
        max_gyro_s = max(max_gyro_s, run_max_gyro_s)

        if TEST_PRINTING:
            print(f"\nCUSUM results run: {run_index}")
            print("--------------------------------------")
            print(f"Dist run max s_pos: {run_max_dist_s_pos}")
            print(f"Dist run max s_neg: {run_max_dist_s_neg}")
            print(f"Gyro run max s: {run_max_gyro_s}")

            if threshold > 0:
                if cusum_detected:
                    print(
                        f"CUSUM spoofing detected during this run, "
                        f"{detection_delay_seconds:.1f}s after spoofing started."
                    )
                    print(
                        f"Detection GPS distance: {detection_gps_distance:.2f} m, "
                        f"OF distance: {detection_of_distance:.2f} m, "
                        f"distance after spoof start: {detection_delay_distance:.2f} m\n"
                    )
                else:
                    print("CUSUM did not detect during this run.\n")

    if TEST_PRINTING:
        print("\nCUSUM overall max values")
        print("--------------------------------------")
        print(f"Max s_pos: {max_dist_s_pos}")
        print(f"Max s_neg: {max_dist_s_neg}")
        print(f"Max gyro_s: {max_gyro_s}\n")

    return max_dist_s_pos, max_dist_s_neg, max_gyro_s


# =====================================================
# SSDGOF TEST
# =====================================================

def test_ssdgof(df: DataFrame, threshold: float, label: str = "") -> float:
    runs = split_into_runs(df)

    max_ssdgof_error = 0.0

    if TEST_PRINTING:
        print(f"\n\nSSDGOF ANALYSIS: {label}")
        print("-------------------------------------------")
        print(f"Runs found: {len(runs)}")
        print(f"Threshold: {threshold}\n")

    for run_index, run_df in enumerate(runs, start=1):
        total_gps_distance = 0.0
        total_of_distance = 0.0

        run_max_ssdgof_error = 0.0

        ssdgof_detected = False
        detection_gps_distance = None
        detection_of_distance = None
        detection_error = None
        detection_delay_distance = None
        detection_delay_seconds = None
        updates_after_spoof_start = 0

        for row_index, row in run_df.iterrows():
            total_gps_distance += row["gps_distance"]
            total_of_distance += row["of_distance"]

            ssdgof_error = abs(total_gps_distance - total_of_distance)
            run_max_ssdgof_error = max(run_max_ssdgof_error, ssdgof_error)

            if total_gps_distance > SPOOF_START_DISTANCE and not ssdgof_detected:
                updates_after_spoof_start += 1

            if not ssdgof_detected and ssdgof_error > threshold:
                ssdgof_detected = True
                detection_gps_distance = total_gps_distance
                detection_of_distance = total_of_distance
                detection_error = ssdgof_error
                detection_delay_distance = total_gps_distance - SPOOF_START_DISTANCE
                detection_delay_seconds = updates_after_spoof_start * 0.2

                if TEST_PRINTING:
                    print(
                        f"SSDGOF DETECTED in run {run_index}: "
                        f"GPS distance={detection_gps_distance:.2f} m, "
                        f"OF distance={detection_of_distance:.2f} m, "
                        f"error={detection_error:.2f} m, "
                        f"distance after spoof start={detection_delay_distance:.2f} m"
                    )

            if TEST_PRINTING and MANUAL_STEPS:
                print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
                print(f"ssdgof_error: {ssdgof_error}")
                input("")

        max_ssdgof_error = max(max_ssdgof_error, run_max_ssdgof_error)

        if TEST_PRINTING:
            print(f"\nSSDGOF results run: {run_index}")
            print("--------------------------------------")
            print(f"SSDGOF run max error: {run_max_ssdgof_error}")
            print(f"SSDGOF current overall max error: {max_ssdgof_error}")

            if ssdgof_detected:
                print(
                    f"SSDGOF spoofing detected during this run, "
                    f"{detection_delay_seconds:.1f}s after spoofing started."
                )
                print(
                    f"Detection GPS distance: {detection_gps_distance:.2f} m, "
                    f"OF distance: {detection_of_distance:.2f} m, "
                    f"SSDGOF error: {detection_error:.2f} m, "
                    f"distance after spoof start: {detection_delay_distance:.2f} m\n"
                )
            else:
                print("SSDGOF did not detect during this run.\n")

    if TEST_PRINTING:
        print("\nSSDGOF overall max value")
        print("--------------------------------------")
        print(f"Max SSDGOF error: {max_ssdgof_error}\n")

    return max_ssdgof_error


# =====================================================
# MAIN
# =====================================================

def main(filename_control: str, filename_spoofed: str) -> None:
    data_normal = read_data(filename_control)
    data_spoofed = read_data(filename_spoofed)

    dist_mean, gyro_mean = compute_means(data_normal)
    dist_deviation, gyro_deviation = compute_deviation(data_normal, dist_mean, gyro_mean)

    if NORMALIZE:
        k1 = DIST_K_NORMALIZED
        k2 = GYRO_K_NORMALIZED
    else:
        k1 = DIST_K_RAW
        k2 = GYRO_K_RAW

    print("\n============================================================")
    print("CONTROL DATA STATISTICS")
    print("============================================================")
    print(f"Distance mean: {dist_mean}")
    print(f"Distance standard deviation: {dist_deviation}")
    print(f"Gyro mean: {gyro_mean}")
    print(f"Gyro standard deviation: {gyro_deviation}")
    print(f"Distance k: {k1}")
    print(f"Gyro k: {k2}")
    print(f"CUSUM threshold: {CUSUM_THRESHOLD}")
    print(f"SSDGOF threshold: {SSDGOF_THRESHOLD}")

    # Control analysis. CUSUM threshold -1 means no CUSUM spoof detection is reported;
    # it is used to find maximum CUSUM values during normal flight.
    max_dist_s_pos, max_dist_s_neg, max_gyro_s = test_cusum(
        data_normal,
        dist_mean,
        dist_deviation,
        k1,
        -1,
        gyro_mean,
        gyro_deviation,
        k2,
        label="CONTROL",
    )

    max_ssdgof_control = test_ssdgof(data_normal, SSDGOF_THRESHOLD, label="CONTROL")

    # Spoofed analysis.
    test_cusum(
        data_spoofed,
        dist_mean,
        dist_deviation,
        k1,
        CUSUM_THRESHOLD,
        gyro_mean,
        gyro_deviation,
        k2,
        label="SPOOFED",
    )

    max_ssdgof_spoofed = test_ssdgof(data_spoofed, SSDGOF_THRESHOLD, label="SPOOFED")

    print("\n============================================================")
    print("FINAL SUMMARY")
    print("============================================================")
    print("Distance CUSUM:")
    print(f"Mean: {dist_mean}")
    print(f"Standard deviation: {dist_deviation}")
    print(f"Max control s_pos: {max_dist_s_pos}")
    print(f"Max control s_neg: {max_dist_s_neg}\n")

    print("Gyro CUSUM:")
    print(f"Mean: {gyro_mean}")
    print(f"Standard deviation: {gyro_deviation}")
    print(f"Max control gyro_s: {max_gyro_s}\n")

    print("SSDGOF:")
    print(f"Threshold: {SSDGOF_THRESHOLD}")
    print(f"Max SSDGOF error on control data: {max_ssdgof_control}")
    print(f"Max SSDGOF error on spoofed data: {max_ssdgof_spoofed}\n")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        control_file = sys.argv[1]
        spoofed_file = sys.argv[2]
    else:
        control_file = DEFAULT_CONTROL_FILE
        spoofed_file = DEFAULT_SPOOFED_FILE

    main(control_file, spoofed_file)
