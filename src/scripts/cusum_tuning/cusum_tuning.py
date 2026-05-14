from pathlib import Path

import pandas as pd
from pandas import DataFrame


COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]
TEST_PRINTING = True
MANUAL_STEPS = False
NORMALIZE = True
TESTING_SPOOFED_RUNS = False
SPOOF_START_DISTANCE = 100


def csv_sort_key(path: Path):
    """
    Sort 1.csv, 2.csv, 10.csv numerically instead of alphabetically.
    """
    if path.stem.isdigit():
        return int(path.stem)
    return path.stem


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
            sum_gyro_diff += ((row.gyro_magnitude - row.prev_gyro_magnitude) - gyro_mean) ** 2
            used_rows += 1

    if used_rows == 0:
        raise ValueError("No usable rows found while computing deviations.")

    return (sum_dist_diff / used_rows) ** (1 / 2), (sum_gyro_diff / used_rows) ** (1 / 2)


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
) -> float:
    if NORMALIZE:
        Z = abs(diff - mean) / sd
    else:
        Z = abs(diff)

    s = max(0.0, s + Z - k)

    return s


def test_cusum(
    runs: list[DataFrame],
    mean1: float,
    sd1: float,
    k1: float,
    threshold: float,
    mean2: float,
    sd2: float,
    k2: float,
) -> tuple[float, float, float]:
    max_dist_s_pos = 0.0
    max_dist_s_neg = 0.0
    max_gyro_s = 0.0

    for run_number, df in enumerate(runs, start=1):
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

        for row in df.itertuples(index=False):
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

            gyro_diff = row.gyro_magnitude - row.prev_gyro_magnitude
            gyro_s = cusum_abs(
                gyro_diff,
                mean2,
                sd2,
                gyro_s,
                k2,
            )

            if threshold > 0:
                if dist_s_pos > threshold or dist_s_neg > threshold:
                    spoofed = True

            if total_gps_distance > SPOOF_START_DISTANCE and spoofed is False:
                updates_to_detection += 1

            if dist_s_pos > run_max_dist_s_pos:
                run_max_dist_s_pos = dist_s_pos

            if dist_s_neg > run_max_dist_s_neg:
                run_max_dist_s_neg = dist_s_neg

            if gyro_s > run_max_gyro_s:
                run_max_gyro_s = gyro_s

            if TEST_PRINTING and MANUAL_STEPS:
                print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
                print(f"dist_s_pos: {dist_s_pos}, dist_s_neg: {dist_s_neg}, gyro_s: {gyro_s}")
                input("")

        if run_max_dist_s_pos > max_dist_s_pos:
            max_dist_s_pos = run_max_dist_s_pos

        if run_max_dist_s_neg > max_dist_s_neg:
            max_dist_s_neg = run_max_dist_s_neg

        if run_max_gyro_s > max_gyro_s:
            max_gyro_s = run_max_gyro_s

        if TEST_PRINTING:
            print(f"Results run: {run_number}")
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

            if spoofed:
                print(
                    f"Spoofing detected during this run, "
                    f"{updates_to_detection} updates after spoofing started.\n"
                )

    return max_dist_s_pos, max_dist_s_neg, max_gyro_s


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
        k2 = 0.8
    else:
        k1 = 0.0132
        k2 = k1

    max_dist_s_pos, max_dist_s_neg, max_gyro_s = test_cusum(
        data_normal,
        dist_mean,
        dist_diviation,
        k1,
        -1,
        gyro_mean,
        gyro_deviation,
        k2,
    )

    if TEST_PRINTING:
        print("\n\nSPOOFED RUNS ANALYSIS:")
        print("-------------------------------------------\n\n")

    if TESTING_SPOOFED_RUNS:
        test_cusum(
            data_spoofed,
            dist_mean,
            dist_diviation,
            k1,
            21.7 * 1.1,
            gyro_mean,
            gyro_deviation,
            k2,
        )

    print(f"Distance: \nMean: {dist_mean}    Standard diviation: {dist_diviation}")
    print(f"Max s_pos: {max_dist_s_pos}, max s_neg: {max_dist_s_neg}\n")

    print(f"Gyro: \nMean: {gyro_mean}    Standard diviation: {gyro_deviation}")
    print(f"Max s: {max_gyro_s}\n")


main(
    "flight_logs_new/turn_control",
    "flight_logs_new/turn_spoofing100",
)