#!/usr/bin/env python3

import asyncio
import os
import sys
from mavsdk import System

CONNECTION = os.environ.get("MAVSDK_CONNECTION", "udp://:14540")
MISSION_TIMEOUT_SECONDS = int(os.environ.get("MISSION_TIMEOUT_SECONDS", "900"))
RUN_ID = os.environ.get("RUN_ID", "unknown")


async def wait_connected(drone):
    print(f"[run {RUN_ID}] Waiting for drone connection on {CONNECTION}...")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print(f"[run {RUN_ID}] Drone connected.")
            return


async def wait_health_ok(drone):
    print(f"[run {RUN_ID}] Waiting for global position and home position...")

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print(f"[run {RUN_ID}] Position estimate OK.")
            return


async def wait_until_landed_after_takeoff(drone):
    print(f"[run {RUN_ID}] Waiting for mission to complete and vehicle to land...")

    was_in_air = False

    async for in_air in drone.telemetry.in_air():
        if in_air:
            was_in_air = True

        if was_in_air and not in_air:
            print(f"[run {RUN_ID}] Vehicle landed.")
            return


async def main():
    drone = System()
    await drone.connect(system_address=CONNECTION)

    await wait_connected(drone)
    await wait_health_ok(drone)

    # Check that a mission is already uploaded/stored on PX4.
    try:
        mission_plan = await drone.mission.download_mission()
        mission_items = getattr(mission_plan, "mission_items", [])

        if len(mission_items) == 0:
            print(f"[run {RUN_ID}] ERROR: No mission uploaded to PX4.")
            sys.exit(2)

        print(f"[run {RUN_ID}] Found mission with {len(mission_items)} items.")

    except Exception as e:
        print(f"[run {RUN_ID}] WARNING: Could not download mission to verify it: {e}")

    print(f"[run {RUN_ID}] Resetting mission to item 0...")
    await drone.mission.set_current_mission_item(0)

    await asyncio.sleep(1)

    print(f"[run {RUN_ID}] Arming...")
    await drone.action.arm()

    print(f"[run {RUN_ID}] Starting mission...")
    await drone.mission.start_mission()

    await asyncio.wait_for(
        wait_until_landed_after_takeoff(drone),
        timeout=MISSION_TIMEOUT_SECONDS,
    )

    print(f"[run {RUN_ID}] Disarming...")
    try:
        await drone.action.disarm()
    except Exception as e:
        print(f"[run {RUN_ID}] Disarm failed or vehicle already disarmed: {e}")

    print(f"[run {RUN_ID}] Mission run complete.")


if __name__ == "__main__":
    asyncio.run(main())
