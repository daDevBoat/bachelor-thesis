import pandas as pd
from pandas import DataFrame


COLUMNS = ["of_distance", "gps_distance", "gyro_magnitude", "prev_gyro_magnitude"]
TEST_PRINTING = True
MANUAL_STEPS = True
NORMALIZE = True
SPOOF_START_DISTANCE = 25

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

def test_cusum(df: DataFrame, mean1: float, sd1: float, k1: float, threshold: float, mean2: float, sd2: float, k2: float) -> tuple[float, float, float]:
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

    used_rows = 0
    run = 1
    i = 0
    while i < len(df):
        if df.loc[i]["of_distance"] == 0 and df.loc[i]["gps_distance"] == 0 and df.loc[i]["gyro_magnitude"] == 0 and df.loc[i]["prev_gyro_magnitude"] == 0:
            dist_s_pos = 0.0
            dist_s_neg = 0.0
            gyro_s = 0.0
            total_gps_distance = 0.0
            total_of_distance = 0.0

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

                if spoofed:
                    print(f"Spoofing detected during this run, {updates_to_detection * 0.2:.1f}s after sppofing started.\n")

            run_max_dist_s_pos = 0.0
            run_max_dist_s_neg = 0.0
            run_max_gyro_s = 0.0
            spoofed = False
            updates_to_detection = 0

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

        used_rows += 1
        i += 1

        if TEST_PRINTING and MANUAL_STEPS:
            print(f"Gps distance: {total_gps_distance}, OF distance: {total_of_distance}")
            print(f"dist_s_pos: {dist_s_pos}, dist_s_neg: {dist_s_neg}, gyro_s: {gyro_s}")
            input("")

    return max_dist_s_pos, max_dist_s_neg, max_gyro_s

def main(filename_control: str, filename_spoofed: str):
    data_normal = read_data(filename_control)
    dist_mean, gyro_mean = compute_means(data_normal)
    dist_diviation, gyro_deviation = compute_diviation(data_normal, dist_mean, gyro_mean)

    data_spoofed = read_data(filename_spoofed)

    if NORMALIZE:
        k1 = 0.5
        k2 = 0.8
    else:
        k1 = 0.0132
        k2 = k1

    max_dist_s_pos, max_dist_s_neg, max_gyro_s = test_cusum(data_normal, dist_mean, dist_diviation, k1, -1, gyro_mean, gyro_deviation, k2)

    if TEST_PRINTING:
        print("\n\nSPOOFED RUNS ANALYSIS:")
        print("-------------------------------------------\n\n")

    test_cusum(data_spoofed, dist_mean, dist_diviation, k1, 11 * 1.1, gyro_mean, gyro_deviation, k2)

    print(f"Distance: \nMean: {dist_mean}    Standard diviation: {dist_diviation}")
    print(f"Max s_pos: {max_dist_s_pos}, max s_neg: {max_dist_s_neg}\n")

    print(f"Gyro: \nMean: {gyro_mean}    Standard diviation: {gyro_deviation}")
    print(f"Max s: {max_gyro_s}\n")


    #inspect_z_values(data, dist_mean, dist_diviation)


main("flight_logs/turn_control_log.csv", "flight_logs/turn_spoofing100_log.csv")
#main("flight_logs/straight_control_log.csv", "flight_logs/straight_spoofing25_log.csv")


"""
SPOOFING:
Distance:
Mean: -0.04610479089979569    Standard diviation: 0.1226234698918926
Max s_pos: 8.109029964276756, max s_neg: 9.27549364489186

Gyro:
Mean: -0.009408999284253561    Standard diviation: 0.034359389254892556
Max s: 35.74869412877917

NORMAL:

Distance:
Mean: -0.005893799895506772    Standard diviation: 0.12280581496735504
Max s_pos: 5.759822345737595, max s_neg: 22.350318257122723

Gyro:
Mean: -0.010460795611285243    Standard diviation: 0.032510004759917964
Max s: 38.20054227017472



"""