#!/usr/bin/env python3
"""
Econet24 to MQTT Bridge for Home Assistant

This daemon polls econet24.com for sensor data and publishes it to MQTT
with Home Assistant auto-discovery enabled.

Usage:
    python econet24_mqtt_bridge.py

Environment variables:
    ECONET24_USERNAME - Your econet24.com email
    ECONET24_PASSWORD - Your econet24.com password
    MQTT_HOST - MQTT broker host (default: localhost)
    MQTT_PORT - MQTT broker port (default: 1883)
    MQTT_USERNAME - MQTT username (optional)
    MQTT_PASSWORD - MQTT password (optional)
    POLL_INTERVAL - Seconds between polls (default: 60)
    LOG_LEVEL - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
"""

import os
import sys
import json
import time
import signal
import logging
from typing import Any

import paho.mqtt.client as mqtt

from econet24_client import Econet24Client, LoginError, Econet24Error

# Configure logging based on environment
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("econet24")

# Also set level for the client module
logging.getLogger("econet24_client").setLevel(getattr(logging, log_level, logging.INFO))

# Sensor definitions with HA device classes and units
SENSOR_DEFINITIONS = {
    # Grant heat pump sensors
    "GrantOutgoingTemp": {
        "name": "Heat Pump Flow Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "GrantReturnTemp": {
        "name": "Heat Pump Return Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "GrantOutdoorTemp": {
        "name": "Heat Pump Outdoor Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "GrantCompressorFreq": {
        "name": "Compressor Frequency",
        "device_class": None,
        "unit": "Hz",
        "icon": "mdi:sine-wave"
    },
    "GrantPumpSpeed": {
        "name": "Pump Speed",
        "device_class": None,
        "unit": "RPM",
        "icon": "mdi:pump"
    },
    "GrantWorkState": {
        "name": "Heat Pump Work State",
        "device_class": None,
        "unit": None,
        "icon": "mdi:heat-pump"
    },
    # Temperature sensors
    "TempWthr": {
        "name": "Weather Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:weather-partly-cloudy"
    },
    "TempCWU": {
        "name": "Hot Water Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:water-boiler"
    },
    "TempBuforUp": {
        "name": "Buffer Tank Top Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:storage-tank"
    },
    "TempBuforDown": {
        "name": "Buffer Tank Bottom Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:storage-tank"
    },
    "TempClutch": {
        "name": "Clutch Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "TempCircuit2": {
        "name": "Circuit 2 Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "TempCircuit3": {
        "name": "Circuit 3 Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer"
    },
    "HeatSourceCalcPresetTemp": {
        "name": "Calculated Preset Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "icon": "mdi:thermometer-auto"
    },
    # WiFi
    "wifiQuality": {
        "name": "WiFi Quality",
        "device_class": None,
        "unit": "%",
        "icon": "mdi:wifi"
    },
    "wifiStrength": {
        "name": "WiFi Signal Strength",
        "device_class": "signal_strength",
        "unit": "dBm",
        "icon": "mdi:wifi"
    },
}


def slugify(text: str) -> str:
    """Convert text to a slug suitable for entity IDs."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


class Econet24MQTTBridge:
    """Bridge between econet24.com and MQTT for Home Assistant."""

    def __init__(
        self,
        econet_username: str,
        econet_password: str,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        mqtt_username: str = None,
        mqtt_password: str = None,
        poll_interval: int = 60,
        ha_discovery_prefix: str = "homeassistant",
        topic_prefix: str = "econet24",
        device_name: str = None,
    ):
        self.econet_username = econet_username
        self.econet_password = econet_password
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.poll_interval = poll_interval
        self.ha_discovery_prefix = ha_discovery_prefix
        self.topic_prefix = topic_prefix
        self.device_name = device_name  # Custom device name for friendly entity IDs

        self.econet_client = None
        self.mqtt_client = None
        self.running = False
        self._discovery_published = set()
        self._device_name_map = {}  # Maps device UID to friendly name

    def _get_device_slug(self, device_uid: str) -> str:
        """Get a friendly slug for the device (for entity IDs)."""
        if device_uid in self._device_name_map:
            return self._device_name_map[device_uid]

        # Use custom device name if provided, otherwise use first 8 chars of UID
        if self.device_name:
            slug = slugify(self.device_name)
        else:
            slug = device_uid[:8].lower()

        self._device_name_map[device_uid] = slug
        return slug

    def _get_device_display_name(self, device_uid: str) -> str:
        """Get a friendly display name for the device."""
        if self.device_name:
            return self.device_name
        return f"Econet24 {device_uid[:8]}"

    def _setup_econet(self):
        """Initialize and login to econet24."""
        logger.info("[ECONET] Connecting to econet24.com...")
        self.econet_client = Econet24Client()

        try:
            self.econet_client.login(self.econet_username, self.econet_password)
            logger.info(f"[ECONET] Login successful!")
            logger.info(f"[ECONET] Found {len(self.econet_client.devices)} device(s): {self.econet_client.devices}")
        except LoginError as e:
            logger.error(f"[ECONET] Login FAILED: {e}")
            raise
        except Exception as e:
            logger.error(f"[ECONET] Connection error: {e}")
            raise

    def _setup_mqtt(self):
        """Initialize MQTT client."""
        logger.info(f"[MQTT] Connecting to broker at {self.mqtt_host}:{self.mqtt_port}...")
        self.mqtt_client = mqtt.Client(client_id="econet24_bridge")

        if self.mqtt_username:
            logger.debug(f"[MQTT] Using authentication (user: {self.mqtt_username})")
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)

        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self.mqtt_client.on_publish = self._on_mqtt_publish

        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"[MQTT] Connection FAILED: {e}")
            raise

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        rc_codes = {
            0: "Connection successful",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized",
        }
        if rc == 0:
            logger.info("[MQTT] Connected to broker successfully!")
        else:
            logger.error(f"[MQTT] Connection FAILED: {rc_codes.get(rc, f'Unknown error code {rc}')}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        if rc == 0:
            logger.info("[MQTT] Disconnected cleanly")
        else:
            logger.warning(f"[MQTT] Unexpected disconnection (rc={rc}), will auto-reconnect...")

    def _on_mqtt_publish(self, client, userdata, mid):
        """Handle MQTT publish confirmation."""
        logger.debug(f"[MQTT] Message {mid} published")

    def _publish_ha_discovery(self, device_uid: str, sensor_key: str, sensor_def: dict):
        """Publish Home Assistant MQTT discovery config."""
        if sensor_key in self._discovery_published:
            return

        device_slug = self._get_device_slug(device_uid)
        device_display_name = self._get_device_display_name(device_uid)
        sensor_slug = slugify(sensor_def["name"])

        # Use friendly names for entity IDs: econet24_heatpump_flow_temperature
        unique_id = f"econet24_{device_slug}_{sensor_slug}"
        state_topic = f"{self.topic_prefix}/{device_uid}/{sensor_key}"

        config = {
            "name": sensor_def["name"],
            "unique_id": unique_id,
            "object_id": f"econet24_{device_slug}_{sensor_slug}",  # Controls entity_id
            "state_topic": state_topic,
            "device": {
                "identifiers": [f"econet24_{device_uid}"],
                "name": device_display_name,
                "manufacturer": "Plum",
                "model": "ecoMAX360i",
                "via_device": "econet24_bridge",
            },
        }

        if sensor_def.get("device_class"):
            config["device_class"] = sensor_def["device_class"]

        if sensor_def.get("unit"):
            config["unit_of_measurement"] = sensor_def["unit"]

        if sensor_def.get("icon"):
            config["icon"] = sensor_def["icon"]

        # Publish discovery config
        discovery_topic = f"{self.ha_discovery_prefix}/sensor/{unique_id}/config"
        result = self.mqtt_client.publish(
            discovery_topic,
            json.dumps(config),
            retain=True
        )
        logger.info(f"[MQTT] Registered new sensor: {sensor_def['name']} -> sensor.{unique_id}")
        logger.debug(f"[MQTT] Discovery topic: {discovery_topic}")
        self._discovery_published.add(sensor_key)

    def _publish_sensor_value(self, device_uid: str, sensor_key: str, value: Any):
        """Publish a sensor value to MQTT."""
        topic = f"{self.topic_prefix}/{device_uid}/{sensor_key}"
        # Convert None to empty string, otherwise HA shows "unknown"
        if value is None:
            payload = ""
        else:
            payload = str(value)
        result = self.mqtt_client.publish(topic, payload, retain=True)
        logger.debug(f"[MQTT] Published {sensor_key}={payload} to {topic}")

    def _poll_and_publish(self):
        """Poll econet24 and publish data to MQTT."""
        try:
            for device_uid in self.econet_client.devices:
                logger.debug(f"[ECONET] Polling device {device_uid}...")

                # Fetch data from econet24
                params = self.econet_client.get_device_params(device_uid)
                curr = params.get("curr", {})

                # Count valid sensors (excluding 999.0 values)
                valid_sensors = {k: v for k, v in curr.items() if v != 999.0}
                logger.info(f"[ECONET] Received {len(valid_sensors)} sensor values from device {device_uid[:8]}")

                # Log some key values at INFO level for quick diagnostics
                key_sensors = ["GrantOutgoingTemp", "GrantReturnTemp", "TempCWU", "GrantCompressorFreq"]
                key_values = {k: curr.get(k) for k in key_sensors if k in curr and curr.get(k) != 999.0}
                if key_values:
                    logger.info(f"[ECONET] Key readings: {key_values}")

                # Publish WiFi info
                for key in ["wifiQuality", "wifiStrength"]:
                    if key in params:
                        if key in SENSOR_DEFINITIONS:
                            self._publish_ha_discovery(device_uid, key, SENSOR_DEFINITIONS[key])
                        self._publish_sensor_value(device_uid, key, params[key])

                # Publish current sensor values
                published_count = 0
                for key, value in curr.items():
                    # Skip invalid/disconnected sensors (999.0)
                    if value == 999.0:
                        logger.debug(f"[ECONET] Skipping {key} (value=999.0, sensor not connected)")
                        continue

                    # Publish discovery if we have a definition
                    if key in SENSOR_DEFINITIONS:
                        self._publish_ha_discovery(device_uid, key, SENSOR_DEFINITIONS[key])
                    else:
                        # Create a generic sensor definition
                        generic_def = {
                            "name": key,
                            "device_class": None,
                            "unit": None,
                            "icon": "mdi:information"
                        }
                        self._publish_ha_discovery(device_uid, key, generic_def)

                    self._publish_sensor_value(device_uid, key, value)
                    published_count += 1

                logger.info(f"[MQTT] Published {published_count} sensor values to MQTT")

        except Econet24Error as e:
            logger.error(f"[ECONET] API error: {e}")
            logger.info("[ECONET] Attempting re-login...")
            try:
                self._setup_econet()
                logger.info("[ECONET] Re-login successful")
            except Exception as re_e:
                logger.error(f"[ECONET] Re-login FAILED: {re_e}")

        except Exception as e:
            logger.error(f"[POLL] Unexpected error: {e}", exc_info=True)

    def run(self):
        """Main loop."""
        self.running = True

        logger.info("=" * 50)
        logger.info("Econet24 MQTT Bridge starting...")
        logger.info(f"Log level: {log_level}")
        if self.device_name:
            logger.info(f"Device name: {self.device_name}")
        logger.info("=" * 50)

        # Setup connections
        self._setup_econet()
        self._setup_mqtt()

        # Give MQTT time to connect
        time.sleep(2)

        logger.info("=" * 50)
        logger.info(f"[POLL] Starting polling loop (interval: {self.poll_interval}s)")
        logger.info("=" * 50)

        poll_count = 0
        while self.running:
            poll_count += 1
            logger.debug(f"[POLL] Poll cycle #{poll_count}")

            try:
                self._poll_and_publish()
            except Exception as e:
                logger.error(f"[POLL] Error in poll loop: {e}", exc_info=True)

            # Sleep in small increments to allow clean shutdown
            logger.debug(f"[POLL] Sleeping for {self.poll_interval}s until next poll...")
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("[SHUTDOWN] Shutting down...")
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("[SHUTDOWN] Goodbye!")

    def stop(self):
        """Stop the bridge."""
        self.running = False


def main():
    """Main entry point."""
    # Load configuration from environment
    econet_username = os.environ.get("ECONET24_USERNAME")
    econet_password = os.environ.get("ECONET24_PASSWORD")
    mqtt_host = os.environ.get("MQTT_HOST", "localhost")
    mqtt_port = int(os.environ.get("MQTT_PORT", "1883"))
    mqtt_username = os.environ.get("MQTT_USERNAME")
    mqtt_password = os.environ.get("MQTT_PASSWORD")
    poll_interval = int(os.environ.get("POLL_INTERVAL", "60"))
    device_name = os.environ.get("DEVICE_NAME", "").strip() or None

    if not econet_username or not econet_password:
        print("Error: ECONET24_USERNAME and ECONET24_PASSWORD must be set")
        print("\nUsage:")
        print("  export ECONET24_USERNAME='your_email@example.com'")
        print("  export ECONET24_PASSWORD='your_password'")
        print("  export MQTT_HOST='localhost'  # optional")
        print("  export DEVICE_NAME='Heat Pump'  # optional, for friendly entity IDs")
        print("  python econet24_mqtt_bridge.py")
        sys.exit(1)

    bridge = Econet24MQTTBridge(
        econet_username=econet_username,
        econet_password=econet_password,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        poll_interval=poll_interval,
        device_name=device_name,
    )

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        bridge.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        bridge.run()
    except KeyboardInterrupt:
        bridge.stop()


if __name__ == "__main__":
    main()
