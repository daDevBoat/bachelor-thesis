import pandas as pd
from pandas import DataFrame

COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]
TEST_PRINTING = True
MANUAL_STEPS = False
NORMALIZE = True
z_values = []

def read_data(filename: str) -> DataFrame:
    csv_df = pd.read_csv(filename, names=COLUMNS)
    return csv_df


def compute_means(df: DataFrame) -> tuple[float, float]:
    sum_dist_diff = 0
    sum_gyro_diff = 0
    used_rows = 0
    i = 0
    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and  df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
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
        if df.loc[i]["of_distance"] == 0 and  df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            i += 2
            continue

        sum_dist_diff += ((df.loc[i]["of_distance"] - df.loc[i]["gps_distance"]) - dist_mean)**2
        sum_gyro_diff += ((df.loc[i]["gyro_magnitude"] - df.loc[i]["prev_gyro_magnitude"]) - gyro_mean)**2
        used_rows += 1
        i += 1

    return (sum_dist_diff / used_rows)**(1/2), (sum_gyro_diff / used_rows)**(1/2)

def cusum(diff: float, mean: float, sd: float, s_pos: float, s_neg: float, k: float) -> tuple[float, float]:
    if NORMALIZE:
        Z = (diff - mean) / sd
    else:
        Z = diff
    s_pos = max(0.0, s_pos + Z - k)
    s_neg = max(0.0, s_neg - Z - k)
    #z_values.append(Z)
    return s_pos, s_neg

def cusum_abs(diff: float, mean: float, sd: float, s: float, k: float) -> float:
    if NORMALIZE:
        Z = abs(diff - mean) / sd
    else:
        Z = abs(diff)
    s = max(0.0, s + Z - k)
    return s

def test_cusum(df: DataFrame, mean1: float, sd1: float, k1: float, mean2: float, sd2: float, k2: float) -> tuple[float, float, float]:
    max_dist_s_pos = 0.0
    max_dist_s_neg = 0.0
    max_gyro_s = 0.0

    run_max_dist_s_pos = 0.0
    run_max_dist_s_neg = 0.0
    run_max_gyro_s = 0.0

    dist_s_pos = 0.0
    dist_s_neg = 0.0
    gyro_s = 0.0

    run_distance = 0.0

    used_rows = 0
    run = 1
    i = 0
    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            dist_s_pos = 0.0
            dist_s_neg = 0.0
            gyro_s = 0.0
            run_distance = 0.0

            if run_max_dist_s_pos > max_dist_s_pos:
                max_dist_s_pos = run_max_dist_s_pos
            if run_max_dist_s_neg > max_dist_s_neg:
                max_dist_s_neg = run_max_dist_s_neg
            if run_max_gyro_s > max_gyro_s:
                max_gyro_s = run_max_gyro_s

            if TEST_PRINTING and run > 1:
                print(f"Results run: {run - 1}")
                print("--------------------------------------")
                print(f"Dist run max s_pos: {run_max_dist_s_pos}, current max s_neg: {run_max_dist_s_neg}, Gyro current max s: {run_max_gyro_s}\n")
                print(f"Dist current max s_pos: {max_dist_s_pos}, current max s_neg: {max_dist_s_neg}, Gyro current max s: {max_gyro_s}\n")

            run_max_dist_s_pos = 0.0
            run_max_dist_s_neg = 0.0
            run_max_gyro_s = 0.0

            run += 1
            i += 2
            continue

        if run_distance >= 49:
            i += 1
            continue

        dist_diff = df.loc[i]["of_distance"] - df.loc[i]["gps_distance"]
        dist_s_pos, dist_s_neg = cusum(dist_diff, mean1, sd1, dist_s_pos, dist_s_neg, k1)

        run_distance += df.loc[i]["gps_distance"]

        gyro_diff = df.loc[i]["gyro_magnitude"] - df.loc[i]["prev_gyro_magnitude"]
        gyro_s = cusum_abs(gyro_diff, mean2, sd2, gyro_s, k2)

        if dist_s_pos > run_max_dist_s_pos:
            run_max_dist_s_pos = dist_s_pos
        if dist_s_neg > run_max_dist_s_neg:
            run_max_dist_s_neg = dist_s_neg

        if gyro_s > run_max_gyro_s:
            run_max_gyro_s = gyro_s

        used_rows += 1
        i += 1

        if TEST_PRINTING and MANUAL_STEPS:
            print(f"dist_s_pos: {dist_s_pos}, dist_s_neg: {dist_s_neg}")
            print(f"gyro_s: {gyro_s}")
            input("")

    return max_dist_s_pos, max_dist_s_neg, max_gyro_s

def inspect_z_values(df: DataFrame, dist_mean: float, dist_sd: float):
    rows = []

    i = 0
    while i < len(df):
        row = df.loc[i]

        if (
            row["of_distance"] == 0 and
            row["gps_distance"] == 0 and
            row["gyro_magnitude"] == 0 and
            row["prev_gyro_magnitude"] == 0
        ):
            i += 1
            continue

        dist_diff = row["of_distance"] - row["gps_distance"]
        z = (dist_diff - dist_mean) / dist_sd

        rows.append((i, z, dist_diff, row["of_distance"], row["gps_distance"]))

        i += 1

    rows.sort(key=lambda x: x[1])

    print("\nMost negative distance Z-values:")
    for r in rows[:10]:
        print(
            f"row={r[0]}, Z={r[1]:.3f}, "
            f"diff={r[2]:.6f}, of={r[3]}, gps={r[4]}"
        )

    print("\nMost positive distance Z-values:")
    for r in rows[-10:]:
        print(
            f"row={r[0]}, Z={r[1]:.3f}, "
            f"diff={r[2]:.6f}, of={r[3]}, gps={r[4]}"
        )

def main(filename: str):
    data = read_data(filename)
    dist_mean, gyro_mean = compute_means(data)
    dist_diviation, gyro_deviation = compute_diviation(data, dist_mean, gyro_mean)

    if NORMALIZE:
        k1 = 0.5
        k2 = 0.8
    else:
        k1 = 0.0132
        k2 = k1

    max_dist_s_pos, max_dist_s_neg, max_gyro_s = test_cusum(data, dist_mean, dist_diviation, k1, gyro_mean, gyro_deviation, k2)


    print(f"Distance: \nMean: {dist_mean}    Standard diviation: {dist_diviation}")
    print(f"Max s_pos: {max_dist_s_pos}, max s_neg: {max_dist_s_neg}\n")

    print(f"Gyro: \nMean: {gyro_mean}    Standard diviation: {gyro_deviation}")
    print(f"Max s: {max_gyro_s}\n")


    #inspect_z_values(data, dist_mean, dist_diviation)


#main("flight_logs/straight_control_log.csv")
main("flight_logs/turn_control_log.csv")
#main("flight_logs/turn_spoofing100_log.csv")
