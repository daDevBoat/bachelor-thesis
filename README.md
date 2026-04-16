# PX4/Gazebo Mission Execution and Path-Deviation Analysis

## Overview

This project is intended for running repeatable drone missions in simulation and analyzing deviation from a planned route using PX4 flight logs.

The top-level project structure is:

- **bachelor-thesis/**: main project repository
- **PX4-Autopilot/**: PX4 source tree and simulator code
- **Missions/**: mission plans, logs, CSV exports, analysis scripts, and experiment folders

The software stack consists of:

- **PX4**: autopilot
- **Gazebo**: simulator
- **QGroundControl**: mission planning and mission execution interface

The main objective is to:

1. create a repeatable mission,
2. execute it in simulation,
3. save the PX4 flight log,
4. convert the log to CSV,
5. compute path-deviation metrics in Python,
6. aggregate repeated runs within a condition,
7. compare multiple experimental groups.


## Git Tracking Rules

The repository is set up so that:

- `.ulg` files can be committed
- `.csv` files are ignored through `.gitignore`

This keeps the repository smaller while preserving the main raw PX4 flight logs.

---

## Mission Definition

A **QGroundControl `.plan` file** was created for a simple rectangular mission.

Mission shape:

- takeoff
- fly a **20 m × 20 m rectangle**
- return to launch area
- land

This shape is useful because it is:

- repeatable,
- easy to visualize,
- easy to compare across runs,
- suitable for measuring path deviation, especially around corners.

---

## Running the Full Simulation Stack

This setup is normally launched using multiple terminals.

### Terminal 1: Start the spoofing topic
Inside GPS-spoofing/GZ-bridge_spoofing/build (make a build folder if none present) run:

```bash
make
./GZSpoofing baylands x500_depth_0 constant 50
```

### Terminal 2: Open QGroundControl

Launch QGroundControl separately, for example:

```bash
cd ~/Downloads
./QGroundControl.AppImage
```

### Terminal 3: Start PX4 and Gazebo
```bash
make px4_sitl gz_x500_depth_baylands
```
or 
```bash
make HEADLESS=1 px4_sitl gz_x500_depth_baylands
```
for running Gazebo headless.



Run:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run ros_gz_bridge parameter_bridge /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

This br

QGroundControl is used for:

- loading the mission plan
- uploading the mission to PX4
- arming the vehicle
- switching to Mission mode
- downloading `.ulg` flight logs after the run


Stop the recording with `Ctrl+C` after the flight finishes.

---

## Mission Execution

### 1. Start PX4 and Gazebo

Run from inside `PX4-Autopilot/`:

```bash
cd ~/bachelor-thesis/PX4-Autopilot
make px4_sitl gz_x500_depth
```

### 2. Open QGroundControl

Launch QGroundControl separately.

### 3. Upload the mission

In QGroundControl:

1. open **Plan**
2. load `~/bachelor-thesis/Missions/px4_rectangle_mission.plan`
3. click **Upload**

### 4. Execute the mission

In QGroundControl:

1. return to **Fly**
2. **Arm** the vehicle
3. switch to **Mission** mode

PX4 then executes the uploaded rectangular mission in Gazebo.

---

## Flight Log Collection

PX4 automatically logs each armed flight.

After the mission:

1. open **QGroundControl**
2. go to **Analyze**
3. open **Log Download**
4. download the latest `.ulg` file
5. save it inside the run folder, for example:

```text
bachelor-thesis/Missions/baseline/run_01/run_01_baseline.ulg
```

The `.ulg` file is the PX4 flight log used for later analysis.

---

## Python Environment for Log Conversion

Ubuntu 24.04 blocks direct `pip --user` installation into the system-managed Python environment, so a virtual environment is used.

### 1. Install required packages

```bash
sudo apt install -y python3-venv python3-pip
```

### 2. Create a virtual environment

```bash
python3 -m venv ~/venvs/ulog
```

### 3. Activate it

```bash
source ~/venvs/ulog/bin/activate
```

### 4. Install `pyulog`

```bash
pip install pyulog
```

---

## Converting `.ulg` to CSV

Example workflow for the first baseline run:

```bash
mkdir -p ~/bachelor-thesis/Missions/baseline/run_01
cd ~/bachelor-thesis/Missions/baseline/run_01
ulog2csv ~/bachelor-thesis/Missions/baseline/run_01/run_01_baseline.ulg
```

This exports the PX4 log into multiple CSV files inside the same run folder.

---

## Important Exported CSV Files

The most useful CSV files for path-deviation analysis are:

- `vehicle_local_position_0.csv`  
  PX4 estimated local position

- `vehicle_local_position_groundtruth_0.csv`  
  simulator ground-truth local position

- `vehicle_status_0.csv`  
  vehicle state / flight mode information

- `mission_result_0.csv`  
  mission completion information

Optional supporting files:

- `vehicle_global_position_0.csv`
- `vehicle_global_position_groundtruth_0.csv`
- `sensor_gps_0.csv`
- `estimator_gps_status_0.csv`

---

## Why Local Position Is Used

The exported local-position CSV contains fields such as:

- `timestamp`
- `x`
- `y`
- `z`

These are easier to use than latitude/longitude because:

- values are already in meters,
- distance calculations are straightforward,
- waypoint-path comparisons are simpler.

The local frame in the log does not necessarily start at `(0, 0)`, so the trajectory is shifted so that the first recorded point becomes the origin before comparing it to the planned mission.

---

## Planned Path Used in Analysis

The mission path used in Python analysis is:

- `(0, 0)`
- `(20, 0)`
- `(20, 20)`
- `(0, 20)`
- `(0, 0)`

This represents the rectangular mission in local XY coordinates.

---

## Path-Deviation Metrics

The following metrics are used:

### Mean Cross-Track Error (CTE)

Average distance between the flown path and the planned path.

### Max Cross-Track Error

Largest path deviation at any point in the flight.

### RMS Cross-Track Error

Root-mean-square path deviation, which penalizes larger deviations more strongly.

These metrics are appropriate for comparing baseline and anomaly-condition runs.

---

## Script 1: Estimated Path vs Planned Path

File:

```text
Missions/scripts/analyze_estimated_vs_planned.py
```

### Purpose

This script:

- loads `vehicle_local_position_0.csv`
- reads `timestamp`, `x`, and `y`
- shifts the trajectory so the first point is `(0, 0)`
- compares the estimated path against the planned rectangle
- computes:
  - mean cross-track error
  - max cross-track error
  - RMS cross-track error
- saves:
  - `run_name_metrics_summary.csv`
  - `run_name_cte_timeseries.csv`
  - `run_name_estimated_vs_planned.png`
  - `run_name_cte_over_time.png`

### Run it

```bash
python3 ~/bachelor-thesis/Missions/scripts/analyze_estimated_vs_planned.py   ~/bachelor-thesis/Missions/baseline/run_01
```

### Baseline Result Example

For the first baseline run, this script produced:

- **Mean cross-track error:** `0.111 m`
- **Max cross-track error:** `0.621 m`
- **RMS cross-track error:** `0.199 m`

This serves as a baseline reference for later comparisons.

---

## Script 2: Ground Truth and Estimation Analysis

File:

```text
Missions/scripts/analyze_groundtruth_and_estimation.py
```

### Purpose

This script uses both:

- `vehicle_local_position_0.csv`
- `vehicle_local_position_groundtruth_0.csv`

It computes:

1. **Ground-truth path vs planned mission**
2. **Estimated path vs ground-truth path**

### Outputs

It saves:

- `run_name_groundtruth_estimation_summary.csv`
- `run_name_estimation_error_timeseries.csv`
- `run_name_estimated_vs_groundtruth_vs_planned.png`
- `run_name_groundtruth_cte_over_time.png`
- `run_name_estimation_error_over_time.png`

### Run it

```bash
python3 ~/bachelor-thesis/Missions/scripts/analyze_groundtruth_and_estimation.py   ~/bachelor-thesis/Missions/baseline/run_01
```

### Why it matters

This separates:

- **actual flight deviation**
- **navigation estimation error**

which is especially important for later anomaly-condition comparisons.

---

## Repeated Baseline Runs

For repeated baseline testing, use a structure like:

```text
Missions/baseline/
├── run_01/
├── run_02/
├── run_03/
├── ...
└── run_10/
```

For each run folder:

1. save the `.ulg`
2. convert it to CSV
3. run script 1
4. run script 2

This produces consistent per-run summary outputs and figures.

---

## Script 3: Aggregate Runs Within One Group

File:

```text
Missions/scripts/aggregate_run_group.py
```

### Purpose

This script aggregates repeated runs within one group, such as:

- `baseline/`
- `spoofing/`
- `dropout/`

It:

- scans all `run_*` folders in the group
- reads:
  - `*_metrics_summary.csv`
  - `*_groundtruth_estimation_summary.csv`
- combines them into one per-run table
- computes group statistics:
  - mean
  - std
  - min
  - max
  - count
- saves plots for common metrics

### Run it

For baseline:

```bash
python3 ~/bachelor-thesis/Missions/scripts/aggregate_run_group.py   ~/bachelor-thesis/Missions/baseline
```

For another group:

```bash
python3 ~/bachelor-thesis/Missions/scripts/aggregate_run_group.py   ~/bachelor-thesis/Missions/spoofing
```

### Outputs

For a group called `baseline`, this script saves:

- `baseline_combined_results.csv`
- `baseline_group_statistics.csv`
- metric plots such as:
  - `baseline_mean_cte_m_by_run.png`
  - `baseline_rms_cte_m_by_run.png`
  - `baseline_gt_mean_cte_m_by_run.png`
  - `baseline_est_gt_mean_error_m_by_run.png`

### Why it matters

This is the per-condition summary layer. It makes it possible to compare repeated runs statistically instead of analyzing only one run at a time.

---

## Script 4: Compare Multiple Groups

File:

```text
Missions/scripts/compare_multiple_groups.py
```

### Purpose

This script compares **any number of experiment groups**, not just two.

Example groups:

- `baseline`
- `spoofing`
- `dropout`
- `noise_low`
- `noise_high`
- `bias_small`
- `bias_large`

It:

- scans the parent `Missions/` folder
- finds all group folders except `scripts/`
- reads each group's:
  - `GROUPNAME_combined_results.csv`
- merges all groups into one master table
- computes statistics by group
- generates comparison plots across groups

### Run it

```bash
python3 ~/bachelor-thesis/Missions/scripts/compare_multiple_groups.py   ~/bachelor-thesis/Missions
```

### Outputs

Inside `Missions/`, it saves:

- `all_groups_combined_results.csv`
- `all_groups_statistics.csv`
- boxplots such as:
  - `mean_cte_m_boxplot.png`
  - `rms_cte_m_boxplot.png`
  - `gt_mean_cte_m_boxplot.png`
  - `est_gt_mean_error_m_boxplot.png`
- mean ± std bar charts such as:
  - `mean_cte_m_mean_std.png`
  - `rms_cte_m_mean_std.png`
  - `gt_mean_cte_m_mean_std.png`
  - `est_gt_mean_error_m_mean_std.png`

### Why it matters

This is the final comparison layer for the thesis. It makes it possible to compare multiple experiment conditions in one consistent framework.

---

## Complete Workflow

The full workflow is:

1. create the mission file in `Missions/`
2. start PX4/Gazebo from `PX4-Autopilot/`
3. start ROS 2 and the Gazebo bridge in separate terminals
4. open QGroundControl and upload the mission
5. execute the mission in simulation
6. save the PX4 `.ulg` file into a run folder, for example:
   - `Missions/baseline/run_01/`
7. convert the `.ulg` file to CSV in the same run folder
8. run script 1
9. run script 2
10. repeat for all runs in that group
11. run script 3 for each group
12. run script 4 across all groups

---

## Example Command Sequence

### Single baseline run

```bash
cd ~/bachelor-thesis/PX4-Autopilot
make px4_sitl gz_x500_depth
```

```bash
source /opt/ros/jazzy/setup.bash
```

```bash
source /opt/ros/jazzy/setup.bash
ros2 run ros_gz_bridge parameter_bridge /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock
```

```bash
cd ~/Downloads
./QGroundControl.AppImage
```

After the run, convert and analyze:

```bash
source ~/venvs/ulog/bin/activate
cd ~/bachelor-thesis/Missions/baseline/run_01
ulog2csv ~/bachelor-thesis/Missions/baseline/run_01/run_01_baseline.ulg
```

```bash
python3 ~/bachelor-thesis/Missions/scripts/analyze_estimated_vs_planned.py   ~/bachelor-thesis/Missions/baseline/run_01
```

```bash
python3 ~/bachelor-thesis/Missions/scripts/analyze_groundtruth_and_estimation.py   ~/bachelor-thesis/Missions/baseline/run_01
```

### Aggregate baseline runs

```bash
python3 ~/bachelor-thesis/Missions/scripts/aggregate_run_group.py   ~/bachelor-thesis/Missions/baseline
```

### Aggregate anomaly-condition runs

```bash
python3 ~/bachelor-thesis/Missions/scripts/aggregate_run_group.py   ~/bachelor-thesis/Missions/spoofing
```

### Compare all groups

```bash
python3 ~/bachelor-thesis/Missions/scripts/compare_multiple_groups.py   ~/bachelor-thesis/Missions
```

---

## How to setup GPS-spoofing environment

Go to the px4_ros_ws dir. Run the following commands. 

For linking the package from the github repo:
```bash
ln -s ~/projects/bachelor-thesis/src/GPS-spoofing/constant_gps_bias .
```

For building:
```bash
colcon build --packages-select constant_gps_bias --symlink-install
```

## How to run GPS-spoofing
Start the simulation and everythin else like mentioned in the start of the README.

For starting the spoofing (for now it just displays the GPS pos) use the following commands (while in the px4_ros_ws dir).

First source:
```bash
source install/setup.bash
```

Then start the spoofing:
```bash
ros2 run constant_gps_bias spoof
```
The source code is found in ```spoof.cpp```.

## Summary

A repeatable rectangular mission was created in QGroundControl and flown in PX4/Gazebo simulation. Each run produced a PX4 `.ulg` log, which was converted into CSV files and analyzed with Python. The first script measured deviation between the estimated path and the planned rectangle. The second script added ground-truth path deviation and estimation error relative to simulator truth. Repeated runs within a single condition were aggregated with a third script, and multiple experiment groups were compared with a fourth script. This provides a complete framework for comparing nominal flights against multiple anomaly-condition experiment groups.
