from pathlib import Path

import csv
import pandas as pd
from pandas import DataFrame


COLUMNS = [
    "of_distance",
    "gps_distance",
    "gyro_magnitude",
    "prev_gyro_magnitude",
    "time_us",
]

TEST_PRINTING = True
MANUAL_STEPS = False
TEST_MANUAL_START = 9
NORMALIZE = True
TESTING_SPOOFED_RUNS = True
SPOOF_START_DISTANCE = 140

csv_file = Path("plot_files/run22_140.csv")

# Create file with headers if it does not exist yet

with csv_file.open("w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["timestamp", "value1", "value2", "value3"])

def log_data(time, value1, value2, value3):
    with csv_file.open("a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([time, value1, value2, value3])


def csv_sort_key(path: Path):
    """
    Sort 1.csv, 2.csv, 10.csv numerically instead of alphabetically.
    """
    if path.stem.isdigit():
        return 0, int(path.stem)
    return 1, path.stem


def read_runs(directory: str) -> list[DataFrame]:
    """
    Reads all CSV files in a directory as separate runs.
    Skips the first row of each run.
    """
    directory_path = Path(directory)
    csv_files = sorted(directory_path.glob("*.csv"), key=csv_sort_key)

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {directory_path}")

    runs = []

    for csv_file in csv_files:
        csv_df = pd.read_csv(csv_file, names=COLUMNS)

        # Skip first row of each run
        csv_df = csv_df.iloc[1:].reset_index(drop=True)

        runs.append(csv_df)

    return runs


def should_manual_step(run_number: int) -> bool:
    return MANUAL_STEPS and run_number >= TEST_MANUAL_START


def compute_means(runs: list[DataFrame]) -> tuple[float, float]:
    sum_dist_diff = 0.0
    sum_gyro_diff = 0.0
    used_rows = 0

    for df in runs:
        for row in df.itertuples(index=False):
            sum_dist_diff += row.of_distance - row.gps_distance
            sum_gyro_diff += row.gyro_magnitude - row.prev_gyro_magnitude
            used_rows += 1

    if used_rows == 0:
        raise ValueError("No usable rows found while computing means.")

    return sum_dist_diff / used_rows, sum_gyro_diff / used_rows


def compute_diviation(
    runs: list[DataFrame],
    dist_mean: float,
    gyro_mean: float,
) -> tuple[float, float]:
    sum_dist_diff = 0.0
    sum_gyro_diff = 0.0
    used_rows = 0

    for df in runs:
        for row in df.itertuples(index=False):
            sum_dist_diff += ((row.of_distance - row.gps_distance) - dist_mean) ** 2
            sum_gyro_diff += (
                (row.gyro_magnitude - row.prev_gyro_magnitude) - gyro_mean
            ) ** 2
            used_rows += 1

    if used_rows == 0:
        raise ValueError("No usable rows found while computing deviations.")

    return (sum_dist_diff / used_rows) ** (1 / 2), (
        sum_gyro_diff / used_rows
    ) ** (1 / 2)


def cusum(
    diff: float,
    mean: float,
    sd: float,
    s_pos: float,
    s_neg: float,
    k: float,
) -> tuple[float, float]:
    if NORMALIZE:
        Z = (diff - mean) / sd
    else:
        Z = diff

    s_pos = max(0.0, s_pos + Z - k)
    s_neg = max(0.0, s_neg - Z - k)

    return s_pos, s_neg


def cusum_abs(
    diff: float,
    mean: float,
    sd: float,
    s: float,
    k: float,
    upper_limit: float,
    lower_limit: float,
) -> float:
    if NORMALIZE:
        Z = abs(diff - mean) / sd
    else:
        Z = abs(diff)

    k = 0.25

    s = s + Z - k
    s = max(s, lower_limit)
    s = min(s, upper_limit)

    if TEST_PRINTING and MANUAL_STEPS:
        print(f"CUSUM ABS   Z: {Z}, k: {k}, s: {s}")


    return s


def compute_ssdgof_error(
    total_of_distance: float,
    total_gps_distance: float,
) -> float:
    return abs(total_of_distance - total_gps_distance)


def average(values: list[float]) -> float | None:
    if len(values) == 0:
        return None

    return sum(values) / len(values)


def format_detection_details(details: list[dict]) -> str:
    if not details:
        return "None"

    return ", ".join(
        f"run {detail['run_number']} ({detail['gps_distance']:.2f} m)"
        for detail in details
    )


def format_cusum_control_false_positive_details(details: list[dict]) -> str:
    if not details:
        return "None"

    return ", ".join(
        f"run {detail['run_number']} ({detail['gps_distance']:.2f} m)"
        for detail in details
    )


def make_largest_dist_s_jump_stats() -> dict:
    return {
        "jump": 0.0,
        "run_number": None,
        "signal": None,
        "gps_distance": None,
        "time_us": None,
        "previous_value": None,
        "new_value": None,
    }


def update_largest_dist_s_jump(
    stats: dict,
    jump: float,
    run_number: int,
    signal: str,
    gps_distance: float,
    time_us: float,
    previous_value: float,
    new_value: float,
) -> None:
    if jump > stats["jump"]:
        stats["jump"] = jump
        stats["run_number"] = run_number
        stats["signal"] = signal
        stats["gps_distance"] = gps_distance
        stats["time_us"] = time_us
        stats["previous_value"] = previous_value
        stats["new_value"] = new_value


def print_largest_dist_s_jump_summary(stats: dict) -> None:
    print("Largest control CUSUM s-value jump:")

    if stats["run_number"] is None:
        print("No positive jump found.")
        print()
        return

    print(f"Signal: {stats['signal']}")
    print(f"Run: {stats['run_number']}")
    print(f"Jump size: {stats['jump']:.4f}")
    print(
        f"Value change: "
        f"{stats['previous_value']:.4f} -> {stats['new_value']:.4f}"
    )
    print(f"GPS distance at jump: {stats['gps_distance']:.2f} m")
    print(f"Time at jump: {stats['time_us']} us")
    print()


def print_run_largest_dist_s_jump_summary(stats: dict, run_number: int) -> None:
    print(f"Largest CUSUM s-value jump during run {run_number}:")

    if stats["run_number"] is None:
        print("No positive jump found during this run.")
        print()
        return

    print(f"Signal: {stats['signal']}")
    print(f"Jump size: {stats['jump']:.4f}")
    print(
        f"Value change: "
        f"{stats['previous_value']:.4f} -> {stats['new_value']:.4f}"
    )
    print(f"GPS distance at jump: {stats['gps_distance']:.2f} m")
    print(f"Time at jump: {stats['time_us']} us")
    print()


def make_detection_stats() -> dict:
    return {
        "total_runs": 0,
        "total_detected_runs": 0,
        "detected_runs_after_spoof_start": 0,
        "false_positive_runs_before_spoof_start": 0,
        "no_detection_runs": 0,
        "missed_runs": 0,
        "detection_details": [],
        "false_positive_details": [],
        "detection_times_after_spoof_s": [],
        "detection_distances_after_spoof_m": [],
    }


def print_detection_summary(name: str, stats: dict) -> None:
    detection_times = stats["detection_times_after_spoof_s"]
    detection_distances = stats["detection_distances_after_spoof_m"]

    print(f"{name} spoofed detection summary:")
    print(f"Total runs: {stats['total_runs']}")
    print(f"Total detected runs: {stats['total_detected_runs']}")
    print(
        f"Detections after spoof start: "
        f"{stats['detected_runs_after_spoof_start']}"
    )
    print(
        f"False positives before spoof start: "
        f"{stats['false_positive_runs_before_spoof_start']}"
    )
    print(f"No-detection runs: {stats['no_detection_runs']}")

    if detection_times:
        print(f"Average detection time after spoof start: {average(detection_times):.2f} s")
        print(f"Min detection time after spoof start: {min(detection_times):.2f} s")
        print(f"Max detection time after spoof start: {max(detection_times):.2f} s")
    else:
        print("Average detection time after spoof start: N/A")
        print("Min detection time after spoof start: N/A")
        print("Max detection time after spoof start: N/A")

    if detection_distances:
        print(
            f"Average detection distance after spoof start: "
            f"{average(detection_distances):.2f} m"
        )
        print(
            f"Min detection distance after spoof start: "
            f"{min(detection_distances):.2f} m"
        )
        print(
            f"Max detection distance after spoof start: "
            f"{max(detection_distances):.2f} m"
        )
    else:
        print("Average detection distance after spoof start: N/A")
        print("Min detection distance after spoof start: N/A")
        print("Max detection distance after spoof start: N/A")

    print()


def print_cusum_control_false_positive_summary(stats: dict) -> None:
    false_positive_runs = stats["total_detected_runs"]
    clean_runs = stats["total_runs"] - false_positive_runs

    print("CUSUM control-run false positive summary:")
    print(f"Control runs: {stats['total_runs']}")
    print(f"False-positive control runs: {false_positive_runs}")
    print(f"Clean control runs: {clean_runs}")
    print(
        f"False-positive control runs: "
        f"{format_cusum_control_false_positive_details(stats['detection_details'])}"
    )

    if false_positive_runs > 0:
        print("CUSUM gave false positives during control runs.")
    else:
        print("CUSUM gave no false positives during control runs.")

    print()


def print_adaptive_control_false_positive_summary(stats: dict) -> None:
    false_positive_runs = stats["total_detected_runs"]
    clean_runs = stats["total_runs"] - false_positive_runs

    print("Adaptive CUSUM control-run false positive summary:")
    print(f"Control runs: {stats['total_runs']}")
    print(f"False-positive control runs: {false_positive_runs}")
    print(f"Clean control runs: {clean_runs}")
    print(
        f"False-positive control runs: "
        f"{format_detection_details(stats['detection_details'])}"
    )

    if false_positive_runs > 0:
        print("Adaptive CUSUM gave false positives during control runs.")
    else:
        print("Adaptive CUSUM gave no false positives during control runs.")

    print()


def print_adaptive_spoofed_false_positive_details(stats: dict) -> None:
    print("Adaptive CUSUM spoofed-run false positive details:")
    print(
        f"False-positive spoofed runs before spoof start: "
        f"{format_detection_details(stats['false_positive_details'])}"
    )
    print()


def estimate_spoof_start_time_us(
    spoof_start_time_us: float | None,
    previous_total_gps_distance: float,
    total_gps_distance: float,
    previous_time_us: float | None,
    current_time_us: float,
) -> float | None:
    """
    Estimates the timestamp where accumulated GPS distance crosses SPOOF_START_DISTANCE.
    """
    if spoof_start_time_us is not None:
        return spoof_start_time_us

    if not (
        previous_total_gps_distance <= SPOOF_START_DISTANCE < total_gps_distance
    ):
        return spoof_start_time_us

    if previous_time_us is not None and total_gps_distance != previous_total_gps_distance:
        fraction = (
            (SPOOF_START_DISTANCE - previous_total_gps_distance)
            / (total_gps_distance - previous_total_gps_distance)
        )

        return previous_time_us + fraction * (current_time_us - previous_time_us)

    return current_time_us


def record_detection_stats(
    stats: dict,
    run_number: int,
    detected: bool,
    spoof_start_time_us: float | None,
    detection_time_us: float | None,
    detection_gps_distance: float | None,
    detection_elapsed_time_s: float | None,
) -> tuple[bool, float | None, float | None]:
    """
    Records detection time and distance after spoof start.

    Missed runs are counted as runs without a valid detection after spoof start.
    That means a false positive before spoof start also counts as missed for
    the actual spoof.
    """
    stats["total_runs"] += 1

    if not detected:
        stats["no_detection_runs"] += 1
        stats["missed_runs"] += 1
        return False, None, None

    stats["total_detected_runs"] += 1

    if detection_gps_distance is not None:
        stats["detection_details"].append(
            {
                "run_number": run_number,
                "gps_distance": detection_gps_distance,
                "elapsed_time_s": detection_elapsed_time_s,
            }
        )

    detection_after_spoof_start = (
        spoof_start_time_us is not None
        and detection_time_us is not None
        and detection_gps_distance is not None
        and detection_gps_distance >= SPOOF_START_DISTANCE
    )

    if not detection_after_spoof_start:
        stats["false_positive_runs_before_spoof_start"] += 1
        stats["missed_runs"] += 1

        if detection_gps_distance is not None:
            stats["false_positive_details"].append(
                {
                    "run_number": run_number,
                    "gps_distance": detection_gps_distance,
                    "elapsed_time_s": detection_elapsed_time_s,
                }
            )

        return False, None, None

    detection_delay_seconds = (
        detection_time_us - spoof_start_time_us
    ) / 1_000_000

    detection_distance_after_spoof = (
        detection_gps_distance - SPOOF_START_DISTANCE
    )

    stats["detected_runs_after_spoof_start"] += 1
    stats["detection_times_after_spoof_s"].append(detection_delay_seconds)
    stats["detection_distances_after_spoof_m"].append(
        detection_distance_after_spoof
    )

    return True, detection_delay_seconds, detection_distance_after_spoof


def test_cusum(
    runs: list[DataFrame],
    mean1: float,
    sd1: float,
    k1: float,
    threshold: float,
    mean2: float,
    sd2: float,
    k2: float,
) -> tuple[float, float, float, dict, dict, dict]:
    max_dist_s_pos = 0.0
    max_dist_s_neg = 0.0
    max_gyro_s = 0.0

    largest_dist_s_jump_stats = make_largest_dist_s_jump_stats()

    detection_stats = make_detection_stats()
    adaptive_detection_stats = make_detection_stats()

    for run_number, df in enumerate(runs, start=1):
        run_max_dist_s_pos = 0.0
        run_max_dist_s_neg = 0.0
        run_max_gyro_s = 0.0

        run_largest_dist_s_jump_stats = make_largest_dist_s_jump_stats()

        dist_s_pos = 0.0
        dist_s_neg = 0.0
        gyro_s = 0.0

        total_gps_distance = 0.0
        total_of_distance = 0.0

        detected = False
        adaptive_detected = False

        spoof_start_time_us = None

        detection_time_us = None
        detection_gps_distance = None
        detection_of_distance = None
        detection_elapsed_time_s = None

        adaptive_detection_time_us = None
        adaptive_detection_gps_distance = None
        adaptive_detection_of_distance = None
        adaptive_detection_threshold = None
        adaptive_detection_elapsed_time_s = None

        run_start_time_us = None
        last_time_us = None

        for row in df.itertuples(index=False):
            if run_start_time_us is None:
                run_start_time_us = row.time_us

            previous_total_gps_distance = total_gps_distance
            previous_time_us = last_time_us

            previous_dist_s_pos = dist_s_pos
            previous_dist_s_neg = dist_s_neg

            dist_diff = row.of_distance - row.gps_distance
            dist_s_pos, dist_s_neg = cusum(
                dist_diff,
                mean1,
                sd1,
                dist_s_pos,
                dist_s_neg,
                k1,
            )

            total_gps_distance += row.gps_distance
            total_of_distance += row.of_distance

            dist_s_pos_jump = dist_s_pos - previous_dist_s_pos
            dist_s_neg_jump = dist_s_neg - previous_dist_s_neg

            update_largest_dist_s_jump(
                largest_dist_s_jump_stats,
                dist_s_pos_jump,
                run_number,
                "dist_s_pos",
                total_gps_distance,
                row.time_us,
                previous_dist_s_pos,
                dist_s_pos,
            )

            update_largest_dist_s_jump(
                largest_dist_s_jump_stats,
                dist_s_neg_jump,
                run_number,
                "dist_s_neg",
                total_gps_distance,
                row.time_us,
                previous_dist_s_neg,
                dist_s_neg,
            )

            update_largest_dist_s_jump(
                run_largest_dist_s_jump_stats,
                dist_s_pos_jump,
                run_number,
                "dist_s_pos",
                total_gps_distance,
                row.time_us,
                previous_dist_s_pos,
                dist_s_pos,
            )

            update_largest_dist_s_jump(
                run_largest_dist_s_jump_stats,
                dist_s_neg_jump,
                run_number,
                "dist_s_neg",
                total_gps_distance,
                row.time_us,
                previous_dist_s_neg,
                dist_s_neg,
            )

            spoof_start_time_us = estimate_spoof_start_time_us(
                spoof_start_time_us,
                previous_total_gps_distance,
                total_gps_distance,
                previous_time_us,
                row.time_us,
            )

            gyro_diff = row.gyro_magnitude - row.prev_gyro_magnitude
            gyro_s = cusum_abs(
                gyro_diff,
                mean2,
                sd2,
                gyro_s,
                k2,
                20.15,
                8.79
            )

            if total_gps_distance > 1.0 and run_number == 22 and threshold < 0:
                time = (row.time_us - run_start_time_us) / 1000000
                log_data(total_of_distance, gyro_s, max(dist_s_pos, dist_s_neg), 0)


            if threshold > 0:
                if not detected and (
                    dist_s_pos > threshold or dist_s_neg > threshold
                ):
                    detected = True
                    detection_time_us = row.time_us
                    detection_gps_distance = total_gps_distance
                    detection_of_distance = total_of_distance

                    if run_start_time_us is not None:
                        detection_elapsed_time_s = (
                            row.time_us - run_start_time_us
                        ) / 1_000_000

            # Adaptive CUSUM here
            adaptive_threshold = gyro_s

            if not adaptive_detected and (
                dist_s_pos > adaptive_threshold
                or dist_s_neg > adaptive_threshold
            ):
                adaptive_detected = True
                adaptive_detection_time_us = row.time_us
                adaptive_detection_gps_distance = total_gps_distance
                adaptive_detection_of_distance = total_of_distance
                adaptive_detection_threshold = adaptive_threshold

                if run_start_time_us is not None:
                    adaptive_detection_elapsed_time_s = (
                        row.time_us - run_start_time_us
                    ) / 1_000_000

            if dist_s_pos > run_max_dist_s_pos:
                run_max_dist_s_pos = dist_s_pos

            if dist_s_neg > run_max_dist_s_neg:
                run_max_dist_s_neg = dist_s_neg

            if gyro_s > run_max_gyro_s:
                run_max_gyro_s = gyro_s

            last_time_us = row.time_us

            if TEST_PRINTING and should_manual_step(run_number):
                print(
                    f"Gps distance: {total_gps_distance}, "
                    f"OF distance: {total_of_distance}"
                )
                print(f"Time: {row.time_us} us")
                print(
                    f"dist_s_pos: {dist_s_pos}, "
                    f"dist_s_neg: {dist_s_neg}, "
                    f"gyro_s: {gyro_s}"
                )
                print(f"dist_s_pos jump: {dist_s_pos_jump}")
                print(f"dist_s_neg jump: {dist_s_neg_jump}")

                if threshold > 0:
                    print(f"CUSUM threshold: {threshold}")

                print(f"Adaptive CUSUM threshold: {adaptive_threshold}")

                input("")

        if run_max_dist_s_pos > max_dist_s_pos:
            max_dist_s_pos = run_max_dist_s_pos

        if run_max_dist_s_neg > max_dist_s_neg:
            max_dist_s_neg = run_max_dist_s_neg

        if run_max_gyro_s > max_gyro_s:
            max_gyro_s = run_max_gyro_s

        (
            detection_after_spoof_start,
            detection_delay_seconds,
            detection_distance_after_spoof,
        ) = record_detection_stats(
            detection_stats,
            run_number,
            detected,
            spoof_start_time_us,
            detection_time_us,
            detection_gps_distance,
            detection_elapsed_time_s,
        )

        (
            adaptive_detection_after_spoof_start,
            adaptive_detection_delay_seconds,
            adaptive_detection_distance_after_spoof,
        ) = record_detection_stats(
            adaptive_detection_stats,
            run_number,
            adaptive_detected,
            spoof_start_time_us,
            adaptive_detection_time_us,
            adaptive_detection_gps_distance,
            adaptive_detection_elapsed_time_s,
        )

        if TEST_PRINTING:
            print(f"CUSUM results run: {run_number}")
            print("--------------------------------------")
            print(
                f"Dist run max s_pos: {run_max_dist_s_pos}, "
                f"current max s_neg: {run_max_dist_s_neg}, "
                f"Gyro current max s: {run_max_gyro_s}\n"
            )
            print(
                f"Dist current max s_pos: {max_dist_s_pos}, "
                f"current max s_neg: {max_dist_s_neg}, "
                f"Gyro current max s: {max_gyro_s}\n"
            )

            print_run_largest_dist_s_jump_summary(
                run_largest_dist_s_jump_stats,
                run_number,
            )

            if detected:
                print(f"Spoof started at: {spoof_start_time_us / 1000000}s\n")
                print("CUSUM spoofing detected during this run.")


                if detection_after_spoof_start:
                    print(
                        f"Detection time after spoof start: "
                        f"{detection_delay_seconds:.2f} s"
                    )

                    print(
                        f"Detection distance after spoof start: "
                        f"{detection_distance_after_spoof:.2f} m"
                    )
                else:
                    print("Detection happened before spoof start distance was reached.")

                if detection_elapsed_time_s is not None:
                    print(
                        f"Detection time after run start: "
                        f"{detection_elapsed_time_s:.2f} s"
                    )

                if detection_gps_distance is not None:
                    print(f"Detection GPS distance: {detection_gps_distance:.2f} m")

                if detection_of_distance is not None:
                    print(f"Detection OF distance: {detection_of_distance:.2f} m")

                print()
            else:
                print("CUSUM spoofing not detected during this run.\n")

            if adaptive_detected:
                print(f"Adaptive CUSUM spoofing detected during this run at {adaptive_detection_time_us / 1000000}s.")

                if adaptive_detection_after_spoof_start:
                    print(
                        f"Adaptive detection time after spoof start: "
                        f"{adaptive_detection_delay_seconds:.2f} s"
                    )

                    print(
                        f"Adaptive detection distance after spoof start: "
                        f"{adaptive_detection_distance_after_spoof:.2f} m"
                    )
                else:
                    print(
                        "Adaptive detection happened before spoof start distance "
                        "was reached."
                    )

                if adaptive_detection_gps_distance is not None:
                    print(
                        f"Adaptive detection GPS distance: "
                        f"{adaptive_detection_gps_distance:.2f} m"
                    )

                if adaptive_detection_of_distance is not None:
                    print(
                        f"Adaptive detection OF distance: "
                        f"{adaptive_detection_of_distance:.2f} m"
                    )

                if adaptive_detection_threshold is not None:
                    print(
                        f"Adaptive threshold at detection: "
                        f"{adaptive_detection_threshold:.4f}"
                    )

                print()
            else:
                print("Adaptive CUSUM spoofing not detected during this run.\n")

    return (
        max_dist_s_pos,
        max_dist_s_neg,
        max_gyro_s,
        detection_stats,
        adaptive_detection_stats,
        largest_dist_s_jump_stats,
    )


def test_ssdgof(
    runs: list[DataFrame],
    threshold: float,
) -> tuple[float, dict]:
    max_ssdgof_error = 0.0
    detection_stats = make_detection_stats()

    for run_number, df in enumerate(runs, start=1):
        run_max_ssdgof_error = 0.0

        total_gps_distance = 0.0
        total_of_distance = 0.0

        detected = False

        spoof_start_time_us = None
        detection_time_us = None
        detection_gps_distance = None
        detection_of_distance = None
        detection_error = None
        detection_elapsed_time_s = None

        run_start_time_us = None
        last_time_us = None

        for row in df.itertuples(index=False):
            if run_start_time_us is None:
                run_start_time_us = row.time_us

            previous_total_gps_distance = total_gps_distance
            previous_time_us = last_time_us

            total_gps_distance += row.gps_distance
            total_of_distance += row.of_distance

            spoof_start_time_us = estimate_spoof_start_time_us(
                spoof_start_time_us,
                previous_total_gps_distance,
                total_gps_distance,
                previous_time_us,
                row.time_us,
            )

            ssdgof_error = compute_ssdgof_error(
                total_of_distance,
                total_gps_distance,
            )

            if ssdgof_error > run_max_ssdgof_error:
                run_max_ssdgof_error = ssdgof_error

            if threshold > 0:
                if not detected and ssdgof_error > threshold:
                    detected = True
                    detection_time_us = row.time_us
                    detection_gps_distance = total_gps_distance
                    detection_of_distance = total_of_distance
                    detection_error = ssdgof_error

                    if run_start_time_us is not None:
                        detection_elapsed_time_s = (
                            row.time_us - run_start_time_us
                        ) / 1_000_000

            last_time_us = row.time_us

            if TEST_PRINTING and should_manual_step(run_number):
                print(
                    f"Gps distance: {total_gps_distance}, "
                    f"OF distance: {total_of_distance}"
                )
                print(f"Time: {row.time_us} us")
                print(f"SSDGOF error: {ssdgof_error}")
                input("")

        if run_max_ssdgof_error > max_ssdgof_error:
            max_ssdgof_error = run_max_ssdgof_error

        (
            detection_after_spoof_start,
            detection_delay_seconds,
            detection_distance_after_spoof,
        ) = record_detection_stats(
            detection_stats,
            run_number,
            detected,
            spoof_start_time_us,
            detection_time_us,
            detection_gps_distance,
            detection_elapsed_time_s,
        )

        if TEST_PRINTING:
            print(f"SSDGOF results run: {run_number}")
            print("--------------------------------------")
            print(f"SSDGOF run max error: {run_max_ssdgof_error}")
            print(f"SSDGOF current max error: {max_ssdgof_error}\n")

            if detected:
                print("SSDGOF spoofing detected during this run.")

                if detection_after_spoof_start:
                    print(
                        f"Detection time after spoof start: "
                        f"{detection_delay_seconds:.2f} s"
                    )

                    print(
                        f"Detection distance after spoof start: "
                        f"{detection_distance_after_spoof:.2f} m"
                    )
                else:
                    print("Detection happened before spoof start distance was reached.")

                if detection_gps_distance is not None:
                    print(f"Detection GPS distance: {detection_gps_distance:.2f} m")

                if detection_of_distance is not None:
                    print(f"Detection OF distance: {detection_of_distance:.2f} m")

                if detection_error is not None:
                    print(f"Detection SSDGOF error: {detection_error:.2f} m")

                print()

    return max_ssdgof_error, detection_stats


def main(directory_control: str, directory_spoofed: str):
    data_normal = read_runs(directory_control)

    dist_mean, gyro_mean = compute_means(data_normal)
    dist_diviation, gyro_deviation = compute_diviation(
        data_normal,
        dist_mean,
        gyro_mean,
    )

    if TESTING_SPOOFED_RUNS:
        data_spoofed = read_runs(directory_spoofed)

    if NORMALIZE:
        k1 = 0.25
        k2 = 0.5
    else:
        k1 = 0.0132
        k2 = k1

    print("\n\nCUSUM CONTROL RUNS ANALYSIS:")
    print("-------------------------------------------\n")

    (
        max_dist_s_pos,
        max_dist_s_neg,
        max_gyro_s,
        cusum_control_detection_stats,
        adaptive_cusum_control_detection_stats,
        largest_control_dist_s_jump_stats,
    ) = test_cusum(
        data_normal,
        dist_mean,
        dist_diviation,
        k1,
        -1,
        gyro_mean,
        gyro_deviation,
        k2,
    )

    print("\n\nSSDGOF CONTROL RUNS ANALYSIS:")
    print("-------------------------------------------\n")

    max_ssdgof_control, _ = test_ssdgof(
        data_normal,
        -1,
    )

    max_s_value = max(max_dist_s_pos, max_dist_s_neg)

    cusum_spoofed_detection_stats = make_detection_stats()
    adaptive_cusum_spoofed_detection_stats = make_detection_stats()
    ssdgof_spoofed_detection_stats = make_detection_stats()
    max_ssdgof_spoofed = None

    if TESTING_SPOOFED_RUNS:
        print("\n\nCUSUM SPOOFED RUNS ANALYSIS:")
        print("-------------------------------------------\n")

        (
            _,
            _,
            _,
            cusum_spoofed_detection_stats,
            adaptive_cusum_spoofed_detection_stats,
            _,
        ) = test_cusum(
            data_spoofed,
            dist_mean,
            dist_diviation,
            k1,
            max_s_value * 1.1,
            gyro_mean,
            gyro_deviation,
            k2,
        )

        print("\n\nSSDGOF SPOOFED RUNS ANALYSIS:")
        print("-------------------------------------------\n")

        max_ssdgof_spoofed, ssdgof_spoofed_detection_stats = test_ssdgof(
            data_spoofed,
            max_ssdgof_control * 1.1,
        )

    print(f"\n\n\nData Summary:")
    print("-------------------------------------------")

    print("CUSUM:")
    print(f"Distance: \nMean: {dist_mean}    Standard diviation: {dist_diviation}")
    print(f"Max s_pos: {max_dist_s_pos}, max s_neg: {max_dist_s_neg}")
    print(f"CUSUM threshold used on spoofed data: {max_s_value * 1.1}\n")

    print_cusum_control_false_positive_summary(
        cusum_control_detection_stats,
    )

    print_largest_dist_s_jump_summary(
        largest_control_dist_s_jump_stats,
    )

    print(f"Gyro: \nMean: {gyro_mean}    Standard diviation: {gyro_deviation}")
    print(f"Max s: {max_gyro_s}\n")

    print_adaptive_control_false_positive_summary(
        adaptive_cusum_control_detection_stats,
    )

    print_detection_summary(
        "CUSUM",
        cusum_spoofed_detection_stats,
    )

    print_detection_summary(
        "Adaptive CUSUM",
        adaptive_cusum_spoofed_detection_stats,
    )

    print_adaptive_spoofed_false_positive_details(
        adaptive_cusum_spoofed_detection_stats,
    )

    print("SSDGOF:")
    print(f"SSDGOF threshold: {max_ssdgof_control * 1.1}")
    print(f"Max SSDGOF error on control data: {max_ssdgof_control}")

    if max_ssdgof_spoofed is not None:
        print(f"Max SSDGOF error on spoofed data: {max_ssdgof_spoofed}")
    else:
        print("Max SSDGOF error on spoofed data: N/A")

    print()

    print_detection_summary(
        "SSDGOF",
        ssdgof_spoofed_detection_stats,
    )


#"""
main(
    "flight_logs/turns_control",
    "flight_logs/turns_spoofed_140",
)
#"""

"""
main(
    "flight_logs/straight_control",
    "flight_logs/straight_spoofed_25",
)
"""

"""
main(
    "flight_logs/straight_control",
    "flight_logs/straight_spoofed_25",
)
"""