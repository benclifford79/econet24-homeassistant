#!/usr/bin/env python3
"""
Discover all available parameters from econet24.com API endpoints.

This script logs in and queries multiple endpoints to discover
all available parameters for sensor definitions.

Usage:
    export ECONET24_USERNAME='your_email'
    export ECONET24_PASSWORD='your_password'
    python discover_params.py
"""

import os
import json
import sys
from econet24_client import Econet24Client, LoginError

def main():
    username = os.environ.get("ECONET24_USERNAME")
    password = os.environ.get("ECONET24_PASSWORD")

    if not username or not password:
        print("Set ECONET24_USERNAME and ECONET24_PASSWORD environment variables")
        sys.exit(1)

    client = Econet24Client()

    print("=" * 60)
    print("ECONET24 PARAMETER DISCOVERY")
    print("=" * 60)

    try:
        print("\n[1] Logging in...")
        client.login(username, password)
        print(f"    Found devices: {client.devices}")

        uid = client.devices[0] if client.devices else None
        if not uid:
            print("No devices found!")
            sys.exit(1)

        # Query getDeviceParams (main endpoint)
        print("\n" + "=" * 60)
        print("[2] getDeviceParams - Main sensor data")
        print("=" * 60)
        try:
            params = client.get_device_params(uid)
            print(f"\nTop-level keys: {list(params.keys())}")

            # Current values
            curr = params.get("curr", {})
            units = params.get("currUnits", {})
            print(f"\n--- curr ({len(curr)} parameters) ---")
            for key in sorted(curr.keys()):
                value = curr[key]
                unit = units.get(key, "")
                marker = "" if value != 999.0 else " [NOT CONNECTED]"
                print(f"  {key}: {value} {unit}{marker}")

            # Schema params
            schema = params.get("schemaParams", {})
            if schema:
                print(f"\n--- schemaParams ({len(schema)} params) ---")
                print(json.dumps(schema, indent=2, default=str)[:2000])

            # Tiles params
            tiles = params.get("tilesParams", {})
            if tiles:
                print(f"\n--- tilesParams ({len(tiles)} params) ---")
                print(json.dumps(tiles, indent=2, default=str)[:2000])

        except Exception as e:
            print(f"    ERROR: {e}")

        # Query getDeviceEditableParams
        print("\n" + "=" * 60)
        print("[3] getDeviceEditableParams - Editable/setpoint data")
        print("=" * 60)
        try:
            editable = client.get_editable_params(uid)
            print(f"\nTop-level keys: {list(editable.keys())}")
            print("\nFull response (first 5000 chars):")
            print(json.dumps(editable, indent=2, default=str)[:5000])
        except Exception as e:
            print(f"    ERROR: {e}")

        # Query getRegParams
        print("\n" + "=" * 60)
        print("[4] getRegParams - Registration/config parameters")
        print("=" * 60)
        try:
            reg = client.get_reg_params(uid)
            print(f"\nTop-level keys: {list(reg.keys())}")
            print("\nFull response (first 3000 chars):")
            print(json.dumps(reg, indent=2, default=str)[:3000])
        except Exception as e:
            print(f"    ERROR: {e}")

        # Query getSysParams
        print("\n" + "=" * 60)
        print("[5] getSysParams - System parameters")
        print("=" * 60)
        try:
            sys_params = client.get_sys_params(uid)
            print(f"\nTop-level keys: {list(sys_params.keys())}")
            print("\nFull response (first 3000 chars):")
            print(json.dumps(sys_params, indent=2, default=str)[:3000])
        except Exception as e:
            print(f"    ERROR: {e}")

        # Query getHistoryParamsValues (to see what params have history)
        print("\n" + "=" * 60)
        print("[6] getHistoryParamsValues - Historical data params")
        print("=" * 60)
        try:
            from datetime import datetime, timedelta
            end = datetime.now()
            start = end - timedelta(hours=1)
            history = client.get_history(uid, start, end)
            print(f"\nTop-level keys: {list(history.keys())}")
            if "data" in history:
                data_keys = list(history["data"].keys()) if isinstance(history["data"], dict) else "list"
                print(f"Data keys: {data_keys}")
            print("\nFull response (first 3000 chars):")
            print(json.dumps(history, indent=2, default=str)[:3000])
        except Exception as e:
            print(f"    ERROR: {e}")

        # Save full dump to file
        print("\n" + "=" * 60)
        print("[7] Saving full JSON dump to econet24_params_dump.json")
        print("=" * 60)

        full_dump = {
            "device_uid": uid,
            "device_params": None,
            "editable_params": None,
            "reg_params": None,
            "sys_params": None,
        }

        try:
            full_dump["device_params"] = client.get_device_params(uid)
        except:
            pass
        try:
            full_dump["editable_params"] = client.get_editable_params(uid)
        except:
            pass
        try:
            full_dump["reg_params"] = client.get_reg_params(uid)
        except:
            pass
        try:
            full_dump["sys_params"] = client.get_sys_params(uid)
        except:
            pass

        with open("econet24_params_dump.json", "w") as f:
            json.dump(full_dump, f, indent=2, default=str)
        print("    Done! Check econet24_params_dump.json for full data")

    except LoginError as e:
        print(f"Login failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
