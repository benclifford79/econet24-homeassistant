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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

        self.econet_client = None
        self.mqtt_client = None
        self.running = False
        self._discovery_published = set()

    def _setup_econet(self):
        """Initialize and login to econet24."""
        self.econet_client = Econet24Client()
        logger.info("Logging into econet24.com...")
        self.econet_client.login(self.econet_username, self.econet_password)
        logger.info(f"Logged in. Devices: {self.econet_client.devices}")

    def _setup_mqtt(self):
        """Initialize MQTT client."""
        self.mqtt_client = mqtt.Client(client_id="econet24_bridge")

        if self.mqtt_username:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)

        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect

        logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
        self.mqtt_client.loop_start()

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"MQTT connection failed with code {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        logger.warning(f"Disconnected from MQTT broker (rc={rc})")

    def _publish_ha_discovery(self, device_uid: str, sensor_key: str, sensor_def: dict):
        """Publish Home Assistant MQTT discovery config."""
        if sensor_key in self._discovery_published:
            return

        unique_id = f"econet24_{device_uid}_{sensor_key}"
        state_topic = f"{self.topic_prefix}/{device_uid}/{sensor_key}"

        config = {
            "name": sensor_def["name"],
            "unique_id": unique_id,
            "state_topic": state_topic,
            "device": {
                "identifiers": [f"econet24_{device_uid}"],
                "name": f"Econet24 {device_uid[:8]}",
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
        self.mqtt_client.publish(
            discovery_topic,
            json.dumps(config),
            retain=True
        )
        logger.debug(f"Published discovery for {sensor_key}")
        self._discovery_published.add(sensor_key)

    def _publish_sensor_value(self, device_uid: str, sensor_key: str, value: Any):
        """Publish a sensor value to MQTT."""
        topic = f"{self.topic_prefix}/{device_uid}/{sensor_key}"
        # Convert None to empty string, otherwise HA shows "unknown"
        if value is None:
            payload = ""
        else:
            payload = str(value)
        self.mqtt_client.publish(topic, payload, retain=True)

    def _poll_and_publish(self):
        """Poll econet24 and publish data to MQTT."""
        try:
            for device_uid in self.econet_client.devices:
                logger.debug(f"Polling device {device_uid}")
                params = self.econet_client.get_device_params(device_uid)

                # Publish WiFi info
                for key in ["wifiQuality", "wifiStrength"]:
                    if key in params:
                        if key in SENSOR_DEFINITIONS:
                            self._publish_ha_discovery(device_uid, key, SENSOR_DEFINITIONS[key])
                        self._publish_sensor_value(device_uid, key, params[key])

                # Publish current sensor values
                curr = params.get("curr", {})
                for key, value in curr.items():
                    # Skip invalid/disconnected sensors (999.0)
                    if value == 999.0:
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

                logger.info(f"Published {len(curr)} sensors for device {device_uid}")

        except Econet24Error as e:
            logger.error(f"Econet24 error: {e}")
            # Try to re-login
            logger.info("Attempting re-login...")
            try:
                self._setup_econet()
            except Exception as re_e:
                logger.error(f"Re-login failed: {re_e}")

    def run(self):
        """Main loop."""
        self.running = True

        # Setup connections
        self._setup_econet()
        self._setup_mqtt()

        # Give MQTT time to connect
        time.sleep(2)

        logger.info(f"Starting polling loop (interval: {self.poll_interval}s)")

        while self.running:
            try:
                self._poll_and_publish()
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            # Sleep in small increments to allow clean shutdown
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Shutting down...")
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

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

    if not econet_username or not econet_password:
        print("Error: ECONET24_USERNAME and ECONET24_PASSWORD must be set")
        print("\nUsage:")
        print("  export ECONET24_USERNAME='your_email@example.com'")
        print("  export ECONET24_PASSWORD='your_password'")
        print("  export MQTT_HOST='localhost'  # optional")
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
