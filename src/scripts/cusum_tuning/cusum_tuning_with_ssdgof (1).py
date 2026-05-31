#!/usr/bin/env python3

import pandas as pd
from pandas import DataFrame


COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]
TEST_PRINTING = False
MANUAL_STEPS = False
NORMALIZE = True
SPOOF_START_DISTANCE = 100
SSDGOF_THRESHOLD = 10.0
CUSUM_THRESHOLD = 21.7 * 1.1
EXCLUDED_CONTROL_RUNS = {2, 13, 16, 26, 29, 35, 49, 50}
EXCLUDED_SPOOFED_RUNS = set()


def read_data(filename: str) -> DataFrame:
    csv_df = pd.read_csv(filename, names=COLUMNS)
    return csv_df

def remove_runs(df: DataFrame, excluded_runs: set[int]) -> DataFrame:
    if not excluded_runs:
        return df

    rows_to_keep = []
    current_run = 0
    inside_excluded_run = False

    i = 0

    while i < len(df):
        is_marker = (
            df.loc[i]["of_distance"] == 0 and
            df.loc[i]["gps_distance"] == 0 and
            df.loc[i]["gyro_magnitude"] == 0 and
            df.loc[i]["prev_gyro_magnitude"] == 0
        )

        if is_marker:
            current_run += 1
            inside_excluded_run = current_run in excluded_runs

            if not inside_excluded_run:
                rows_to_keep.append(df.loc[i])

            i += 1
            continue

        if not inside_excluded_run:
            rows_to_keep.append(df.loc[i])

        i += 1

    return pd.DataFrame(rows_to_keep).reset_index(drop=True)

def compute_means(df: DataFrame) -> tuple[float, float]:
    sum_dist_diff = 0
    sum_gyro_diff = 0
    used_rows = 0
    i = 0

    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            i += 2
            continue

        sum_dist_diff += df.loc[i]["of_distance"] - df.loc[i]["gps_distance"]
        sum_gyro_diff += df.loc[i]["gyro_magnitude"] - df.loc[i]["prev_gyro_magnitude"]
        used_rows += 1
        i += 1

    return sum_dist_diff / used_rows, sum_gyro_diff / used_rows


def compute_diviation(df: DataFrame, dist_mean, gyro_mean) -> tuple[float, float]:
    sum_dist_diff = 0
    sum_gyro_diff = 0
    used_rows = 0
    i = 0

    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            i += 2
            continue

        sum_dist_diff += ((df.loc[i]["of_distance"] - df.loc[i]["gps_distance"]) - dist_mean) ** 2
        sum_gyro_diff += ((df.loc[i]["gyro_magnitude"] - df.loc[i]["prev_gyro_magnitude"]) - gyro_mean) ** 2
        used_rows += 1
        i += 1

    return (sum_dist_diff / used_rows) ** (1 / 2), (sum_gyro_diff / used_rows) ** (1 / 2)


def cusum(diff: float, mean: float, sd: float, s_pos: float, s_neg: float, k: float) -> tuple[float, float]:
    if NORMALIZE:
        Z = (diff - mean) / sd
    else:
        Z = diff

    s_pos = max(0.0, s_pos + Z - k)
    s_neg = max(0.0, s_neg - Z - k)

    return s_pos, s_neg


def cusum_abs(diff: float, mean: float, sd: float, s: float, k: float) -> float:
    if NORMALIZE:
        Z = abs(diff - mean) / sd
    else:
        Z = abs(diff)

    s = max(0.0, s + Z - k)
    return s


def make_stats_dict(name: str) -> dict:
    return {
        "name": name,
        "runs": 0,
        "detected_runs": 0,
        "true_positive_runs": 0,
        "false_positive_runs": 0,
        "missed_runs": 0,
        "detection_gps_distances": [],
        "detection_distances_after_spoof": [],
        "false_positive_gps_distances": [],
    }


def update_detection_stats(stats: dict, is_spoofed_data: bool, detected: bool, detection_gps_distance: float | None) -> None:
    stats["runs"] += 1

    if detected:
        stats["detected_runs"] += 1
        stats["detection_gps_distances"].append(detection_gps_distance)

        if is_spoofed_data:
            if detection_gps_distance < SPOOF_START_DISTANCE:
                stats["false_positive_runs"] += 1
                stats["false_positive_gps_distances"].append(detection_gps_distance)
            else:
                stats["true_positive_runs"] += 1
                stats["detection_distances_after_spoof"].append(detection_gps_distance - SPOOF_START_DISTANCE)
        else:
            stats["false_positive_runs"] += 1
            stats["false_positive_gps_distances"].append(detection_gps_distance)
    else:
        if is_spoofed_data:
            stats["missed_runs"] += 1


def average(values: list[float]) -> float | None:
    if len(values) == 0:
        return None

    return sum(values) / len(values)


def print_detection_stats(stats: dict) -> None:
    avg_detection_gps_distance = average(stats["detection_gps_distances"])
    avg_detection_after_spoof = average(stats["detection_distances_after_spoof"])
    avg_false_positive_distance = average(stats["false_positive_gps_distances"])

    print(f"\n{stats['name']} SUMMARY")
    print("--------------------------------------")
    print(f"Runs: {stats['runs']}")
    print(f"Detected runs: {stats['detected_runs']} / {stats['runs']}")
    print(f"True positives: {stats['true_positive_runs']}")
    print(f"False positives: {stats['false_positive_runs']}")
    print(f"Missed detections: {stats['missed_runs']}")

    if avg_detection_gps_distance is not None:
        print(f"Average GPS distance at detection: {avg_detection_gps_distance:.2f} m")
    else:
        print("Average GPS distance at detection: N/A")

    if avg_detection_after_spoof is not None:
        print(f"Average distance after spoof start: {avg_detection_after_spoof:.2f} m")
    else:
        print("Average distance after spoof start: N/A")

    if avg_false_positive_distance is not None:
        print(f"Average false-positive GPS distance: {avg_false_positive_distance:.2f} m")
    else:
        print("Average false-positive GPS distance: N/A")

    print()


def test_cusum(df: DataFrame, mean1: float, sd1: float, k1: float, threshold: float, mean2: float, sd2: float, k2: float, label: str = "", is_spoofed_data: bool = False) -> tuple[float, float, float, dict]:
    max_dist_s_pos = 0.0
    max_dist_s_neg = 0.0
    max_gyro_s = 0.0

    run_max_dist_s_pos = 0.0
    run_max_dist_s_neg = 0.0
    run_max_gyro_s = 0.0

    dist_s_pos = 0.0
    dist_s_neg = 0.0
    gyro_s = 0.0

    total_gps_distance = 0.0
    total_of_distance = 0.0

    spoofed = False
    updates_to_detection = 0
    detection_gps_distance = None
    detection_of_distance = None

    stats = make_stats_dict(f"CUSUM {label}")

    used_rows = 0
    run = 1
    i = 0

    def finish_run() -> None:
        nonlocal max_dist_s_pos, max_dist_s_neg, max_gyro_s

        if run_max_dist_s_pos > max_dist_s_pos:
            max_dist_s_pos = run_max_dist_s_pos

        if run_max_dist_s_neg > max_dist_s_neg:
            max_dist_s_neg = run_max_dist_s_neg

        if run_max_gyro_s > max_gyro_s:
            max_gyro_s = run_max_gyro_s

        update_detection_stats(stats, is_spoofed_data, spoofed, detection_gps_distance)

        if TEST_PRINTING:
            print(f"Results run: {run}")
            print("--------------------------------------")
            print(f"Dist run max s_pos: {run_max_dist_s_pos}, current max s_neg: {run_max_dist_s_neg}, Gyro current max s: {run_max_gyro_s}\n")
            print(f"Dist current max s_pos: {max_dist_s_pos}, current max s_neg: {max_dist_s_neg}, Gyro current max s: {max_gyro_s}\n")

            if spoofed:
                print(f"CUSUM spoofing detected during this run, {updates_to_detection * 0.2:.1f}s after spoofing started.")
                print(f"Detection GPS distance: {detection_gps_distance:.2f} m")
                print(f"Detection OF distance: {detection_of_distance:.2f} m")

                if is_spoofed_data:
                    if detection_gps_distance < SPOOF_START_DISTANCE:
                        print("This detection is a false positive before spoofing started.\n")
                    else:
                        print(f"Distance after spoof start: {detection_gps_distance - SPOOF_START_DISTANCE:.2f} m\n")
                else:
                    print("This detection is a false positive in control data.\n")
            else:
                print("CUSUM did not detect during this run.\n")

    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            if run > 1:
                finish_run()

            dist_s_pos = 0.0
            dist_s_neg = 0.0
            gyro_s = 0.0
            total_gps_distance = 0.0
            total_of_distance = 0.0

            run_max_dist_s_pos = 0.0
            run_max_dist_s_neg = 0.0
            run_max_gyro_s = 0.0
            spoofed = False
            updates_to_detection = 0
            detection_gps_distance = None
            detection_of_distance = None

            run += 1
            i += 2
            continue

        if total_gps_distance >= 24 and False:
            i += 1
            continue

        dist_diff = df.loc[i]["of_distance"] - df.loc[i]["gps_distance"]
        dist_s_pos, dist_s_neg = cusum(dist_diff, mean1, sd1, dist_s_pos, dist_s_neg, k1)

        total_gps_distance += df.loc[i]["gps_distance"]
        total_of_distance += df.loc[i]["of_distance"]

        gyro_diff = df.loc[i]["gyro_magnitude"] - df.loc[i]["prev_gyro_magnitude"]
        gyro_s = cusum_abs(gyro_diff, mean2, sd2, gyro_s, k2)

        if threshold > 0:
            if not spoofed and (dist_s_pos > threshold or dist_s_neg > threshold):
                spoofed = True
                detection_gps_distance = total_gps_distance
                detection_of_distance = total_of_distance

                if TEST_PRINTING:
                    print(f"CUSUM DETECTED in run {run}")
                    print(f"GPS distance: {detection_gps_distance:.2f} m")
                    print(f"OF distance: {detection_of_distance:.2f} m")
                    print(f"s_pos: {dist_s_pos:.3f}, s_neg: {dist_s_neg:.3f}\n")

        if total_gps_distance > SPOOF_START_DISTANCE and spoofed is False:
            updates_to_detection += 1

        if dist_s_pos > run_max_dist_s_pos:
            run_max_dist_s_pos = dist_s_pos

        if dist_s_neg > run_max_dist_s_neg:
            run_max_dist_s_neg = dist_s_neg

        if gyro_s > run_max_gyro_s:
            run_max_gyro_s = gyro_s

        used_rows += 1
        i += 1

        if TEST_PRINTING and MANUAL_STEPS:
            print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
            print(f"dist_s_pos: {dist_s_pos}, dist_s_neg: {dist_s_neg}, gyro_s: {gyro_s}")
            input("")

    # Finish the last run if the file does not end with a marker row.
    if used_rows > 0:
        finish_run()

    return max_dist_s_pos, max_dist_s_neg, max_gyro_s, stats


def test_ssdgof(df: DataFrame, threshold: float, label: str = "", is_spoofed_data: bool = False) -> tuple[float, dict]:
    max_ssdgof_error = 0.0
    run_max_ssdgof_error = 0.0

    total_gps_distance = 0.0
    total_of_distance = 0.0

    ssdgof_detected = False
    updates_to_detection = 0
    detection_gps_distance = None
    detection_of_distance = None
    detection_error = None

    stats = make_stats_dict(f"SSDGOF {label}")

    run = 1
    used_rows = 0
    i = 0

    def finish_run() -> None:
        nonlocal max_ssdgof_error

        if run_max_ssdgof_error > max_ssdgof_error:
            max_ssdgof_error = run_max_ssdgof_error

        update_detection_stats(stats, is_spoofed_data, ssdgof_detected, detection_gps_distance)

        if TEST_PRINTING:
            print(f"SSDGOF results run: {run}")
            print("--------------------------------------")
            print(f"SSDGOF run max error: {run_max_ssdgof_error}")
            print(f"SSDGOF current max error: {max_ssdgof_error}\n")

            if ssdgof_detected:
                print(f"SSDGOF spoofing detected during this run, {updates_to_detection * 0.2:.1f}s after spoofing started.")
                print(f"Detection GPS distance: {detection_gps_distance:.2f} m")
                print(f"Detection OF distance: {detection_of_distance:.2f} m")
                print(f"SSDGOF error: {detection_error:.2f} m")

                if is_spoofed_data:
                    if detection_gps_distance < SPOOF_START_DISTANCE:
                        print("This detection is a false positive before spoofing started.\n")
                    else:
                        print(f"Distance after spoof start: {detection_gps_distance - SPOOF_START_DISTANCE:.2f} m\n")
                else:
                    print("This detection is a false positive in control data.\n")
            else:
                print("SSDGOF did not detect during this run.\n")

    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            if run > 1:
                finish_run()

            total_gps_distance = 0.0
            total_of_distance = 0.0

            run_max_ssdgof_error = 0.0
            ssdgof_detected = False
            updates_to_detection = 0
            detection_gps_distance = None
            detection_of_distance = None
            detection_error = None

            run += 1
            i += 2
            continue

        total_gps_distance += df.loc[i]["gps_distance"]
        total_of_distance += df.loc[i]["of_distance"]

        ssdgof_error = abs(total_gps_distance - total_of_distance)

        if ssdgof_error > run_max_ssdgof_error:
            run_max_ssdgof_error = ssdgof_error

        if threshold > 0:
            if not ssdgof_detected and ssdgof_error > threshold:
                ssdgof_detected = True
                detection_gps_distance = total_gps_distance
                detection_of_distance = total_of_distance
                detection_error = ssdgof_error

                if TEST_PRINTING:
                    print(f"SSDGOF DETECTED in run {run}")
                    print(f"GPS distance: {detection_gps_distance:.2f} m")
                    print(f"OF distance: {detection_of_distance:.2f} m")
                    print(f"SSDGOF error: {detection_error:.2f} m\n")

        if total_gps_distance > SPOOF_START_DISTANCE and ssdgof_detected is False:
            updates_to_detection += 1

        used_rows += 1
        i += 1

        if TEST_PRINTING and MANUAL_STEPS:
            print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
            print(f"ssdgof_error: {ssdgof_error}")
            input("")

    # Finish the last run if the file does not end with a marker row.
    if used_rows > 0:
        finish_run()

    return max_ssdgof_error, stats


def main(filename_control: str, filename_spoofed: str):
    data_normal = read_data(filename_control)
    data_normal = remove_runs(data_normal, EXCLUDED_CONTROL_RUNS)

    dist_mean, gyro_mean = compute_means(data_normal)
    dist_diviation, gyro_deviation = compute_diviation(data_normal, dist_mean, gyro_mean)

    data_spoofed = read_data(filename_spoofed)
    data_spoofed = remove_runs(data_spoofed, EXCLUDED_SPOOFED_RUNS)

    data_spoofed = read_data(filename_spoofed)

    if NORMALIZE:
        k1 = 0.25
        k2 = 0.8
    else:
        k1 = 0.0132
        k2 = k1

    max_dist_s_pos, max_dist_s_neg, max_gyro_s, cusum_control_stats = test_cusum(
        data_normal,
        dist_mean,
        dist_diviation,
        k1,
        CUSUM_THRESHOLD,
        gyro_mean,
        gyro_deviation,
        k2,
        label="CONTROL",
        is_spoofed_data=False,
    )

    max_ssdgof_control, ssdgof_control_stats = test_ssdgof(
        data_normal,
        SSDGOF_THRESHOLD,
        label="CONTROL",
        is_spoofed_data=False,
    )

    if TEST_PRINTING:
        print("\n\nSPOOFED RUNS ANALYSIS:")
        print("-------------------------------------------\n\n")

    _, _, _, cusum_spoofed_stats = test_cusum(
        data_spoofed,
        dist_mean,
        dist_diviation,
        k1,
        CUSUM_THRESHOLD,
        gyro_mean,
        gyro_deviation,
        k2,
        label="SPOOFED",
        is_spoofed_data=True,
    )

    max_ssdgof_spoofed, ssdgof_spoofed_stats = test_ssdgof(
        data_spoofed,
        SSDGOF_THRESHOLD,
        label="SPOOFED",
        is_spoofed_data=True,
    )

    print(f"Distance: \nMean: {dist_mean}    Standard diviation: {dist_diviation}")
    print(f"Max s_pos: {max_dist_s_pos}, max s_neg: {max_dist_s_neg}\n")

    print(f"Gyro: \nMean: {gyro_mean}    Standard diviation: {gyro_deviation}")
    print(f"Max s: {max_gyro_s}\n")

    print("SSDGOF:")
    print(f"Threshold: {SSDGOF_THRESHOLD}")
    print(f"Max SSDGOF error on control data: {max_ssdgof_control}")
    print(f"Max SSDGOF error on spoofed data: {max_ssdgof_spoofed}\n")

    print("\n\nFINAL DETECTION COUNTS:")
    print("======================================")
    print_detection_stats(cusum_control_stats)
    print_detection_stats(ssdgof_control_stats)
    print_detection_stats(cusum_spoofed_stats)
    print_detection_stats(ssdgof_spoofed_stats)


main("/Users/isabellalopiano/thesis/PX4-Autopilot/turn_control_log.csv", "/Users/isabellalopiano/thesis/PX4-Autopilot/turn_spoofing100_log.csv")
# main("flight_logs/straight_control_log.csv", "flight_logs/straight_spoofing25_log.csv")

