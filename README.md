# PX4/Gazebo Mission Execution and Path-Deviation Analysis

## Overview

This project is intended for running repeatable drone missions in simulation and analyzing deviation from a planned route using PX4 flight logs.

- **PX4**: autopilot
- **Gazebo**: simulator
- **QGroundControl**: mission planning and mission execution interface


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

and set the following parameters:
```bash
EKF2_GPS_P_GATE=500
EKF2_GPS_V_GATE=500
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


QGroundControl is used for:

- loading the mission plan
- uploading the mission to PX4
- arming the vehicle
- switching to Mission mode



