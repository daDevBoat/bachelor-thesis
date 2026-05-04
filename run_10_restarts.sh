#!/usr/bin/env bash
set -euo pipefail

RUNS="${1:-10}"

PROJECT="$HOME/bachelor-project"

QGC_DIR="$PROJECT"
QGC_CMD="./QGroundControl-x86_64.AppImage"

SPOOF_DIR="$PROJECT/bachelor-thesis/src/GPS-spoofing/GZ-bridge_spoofing/build"
SPOOF_CMD="./GZSpoofing baylands x500_depth_0 null 50"

PX4_DIR="$PROJECT/PX4-Autopilot"
PX4_CMD="make HEADLESS=1 px4_sitl gz_x500_depth_baylands"

MISSION_SCRIPT="$PROJECT/arm_start_mission.py"
PYTHON_BIN="$PROJECT/.venv/bin/python"

MAVSDK_CONNECTION="${MAVSDK_CONNECTION:-udp://:14540}"
MISSION_TIMEOUT_SECONDS="${MISSION_TIMEOUT_SECONDS:-900}"

QGC_WAIT_SECONDS="${QGC_WAIT_SECONDS:-8}"
SPOOF_WAIT_SECONDS="${SPOOF_WAIT_SECONDS:-3}"
PX4_WAIT_SECONDS="${PX4_WAIT_SECONDS:-35}"
BETWEEN_RUNS_WAIT_SECONDS="${BETWEEN_RUNS_WAIT_SECONDS:-8}"

PGIDS=()

if [[ ! -x "$PYTHON_BIN" ]]; then
	echo "ERROR: Could not find virtual environment Python:"
	echo "$PYTHON_BIN"
	exit 1
fi

if [[ ! -f "$MISSION_SCRIPT" ]]; then
	echo "ERROR: Mission script not found:"
	echo "$MISSION_SCRIPT"
	exit 1
fi

start_group() {
	local name="$1"
	local dir="$2"
	local cmd="$3"

	echo "Starting $name..."

	setsid bash -lc "cd \"$dir\" && exec $cmd" > /dev/null 2>&1 &
	local pgid=$!

	echo "$name started with process group $pgid"
	PGIDS+=("$pgid:$name")
}

kill_group() {
	local pgid="$1"
	local name="$2"

	if [[ -z "$pgid" ]]; then
		return
	fi

	echo "Stopping $name..."

	kill -INT -- "-$pgid" 2>/dev/null || true
	sleep 3

	kill -TERM -- "-$pgid" 2>/dev/null || true
	sleep 2

	kill -KILL -- "-$pgid" 2>/dev/null || true
}

stop_current_run() {
	for entry in "${PGIDS[@]:-}"; do
		local pgid="${entry%%:*}"
		local name="${entry#*:}"
		kill_group "$pgid" "$name"
	done

	PGIDS=()
}

cleanup() {
	echo ""
	echo "Cleaning up..."
	stop_current_run
}

trap cleanup EXIT INT TERM

for run in $(seq 1 "$RUNS"); do
	echo ""
	echo "============================================================"
	echo "Starting experiment run $run / $RUNS"
	echo "============================================================"

	start_group "QGroundControl" "$QGC_DIR" "$QGC_CMD"
	sleep "$QGC_WAIT_SECONDS"

	start_group "GZSpoofing" "$SPOOF_DIR" "$SPOOF_CMD"
	sleep "$SPOOF_WAIT_SECONDS"

	start_group "PX4 SITL" "$PX4_DIR" "$PX4_CMD"

	echo "Waiting $PX4_WAIT_SECONDS seconds for PX4/Gazebo/MAVLink to be ready..."
	sleep "$PX4_WAIT_SECONDS"

	echo "Arming and starting mission for run $run..."

	RUN_ID="$run" \
	MAVSDK_CONNECTION="$MAVSDK_CONNECTION" \
	MISSION_TIMEOUT_SECONDS="$MISSION_TIMEOUT_SECONDS" \
	"$PYTHON_BIN" "$MISSION_SCRIPT"

	echo "Mission run $run finished."
	echo "Closing QGroundControl, GZSpoofing, and PX4..."
	stop_current_run

	echo "Waiting $BETWEEN_RUNS_WAIT_SECONDS seconds before next run..."
	sleep "$BETWEEN_RUNS_WAIT_SECONDS"
done

trap - EXIT INT TERM

echo ""
echo "============================================================"
echo "All $RUNS runs complete."
echo "Your PX4 CSV log should be here:"
echo "/home/isabella-lopiano/bachelor-project/PX4-Autopilot/straight_control_log.csv"
echo "============================================================"
