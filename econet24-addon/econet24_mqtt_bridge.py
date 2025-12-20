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
# Covers Grant/ecoMAX heat pumps and common econet24 parameter names
SENSOR_DEFINITIONS = {
    # ===== GRANT HEAT PUMP SPECIFIC =====
    "GrantOutgoingTemp": {"name": "Heat Pump Flow Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "GrantReturnTemp": {"name": "Heat Pump Return Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "GrantOutdoorTemp": {"name": "Heat Pump Outdoor Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "GrantCompressorFreq": {"name": "Compressor Frequency", "device_class": None, "unit": "Hz", "icon": "mdi:sine-wave"},
    "GrantPumpSpeed": {"name": "Pump Speed", "device_class": None, "unit": "RPM", "icon": "mdi:pump"},
    "GrantWorkState": {"name": "Heat Pump Work State", "device_class": None, "unit": None, "icon": "mdi:heat-pump"},
    "GrantFlow": {"name": "Heat Pump Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "GrantPower": {"name": "Heat Pump Power", "device_class": "power", "unit": "W", "icon": "mdi:flash"},
    "GrantCOP": {"name": "Coefficient of Performance", "device_class": None, "unit": None, "icon": "mdi:chart-line"},

    # ===== TEMPERATURE SENSORS =====
    "TempWthr": {"name": "Weather Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:weather-partly-cloudy"},
    "TempCWU": {"name": "Hot Water Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:water-boiler"},
    "TempBuforUp": {"name": "Buffer Tank Top Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:storage-tank"},
    "TempBuforDown": {"name": "Buffer Tank Bottom Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:storage-tank"},
    "TempClutch": {"name": "Clutch Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempCircuit1": {"name": "Circuit 1 Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempCircuit2": {"name": "Circuit 2 Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempCircuit3": {"name": "Circuit 3 Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempFeeder": {"name": "Feeder Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempExhaust": {"name": "Exhaust Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempRoom": {"name": "Room Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:home-thermometer"},
    "TempOutdoor": {"name": "Outdoor Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempReturn": {"name": "Return Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempSupply": {"name": "Supply Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempFlue": {"name": "Flue Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "TempBoiler": {"name": "Boiler Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    # Polish temperature names
    "tempZasilanie": {"name": "Supply Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "tempPowrot": {"name": "Return Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "tempZewn": {"name": "Outdoor Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "tempPokojowa": {"name": "Room Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:home-thermometer"},
    "tempCWU": {"name": "Hot Water Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:water-boiler"},
    "tempBuforGora": {"name": "Buffer Top Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:storage-tank"},
    "tempBuforDol": {"name": "Buffer Bottom Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:storage-tank"},

    # ===== CALCULATED SETPOINTS / TARGET TEMPERATURES =====
    "HeatSourceCalcPresetTemp": {"name": "Calculated Heating Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "Circuit1SetTemp": {"name": "Circuit 1 Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit2SetTemp": {"name": "Circuit 2 Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "C1CalcTemp": {"name": "Circuit 1 Calculated Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "C2CalcTemp": {"name": "Circuit 2 Calculated Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "TempSetCircuit1": {"name": "Circuit 1 Target Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "TempSetCircuit2": {"name": "Circuit 2 Target Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "CalcTempCircuit1": {"name": "Circuit 1 Calculated Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "CalcTempCircuit2": {"name": "Circuit 2 Calculated Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "SetTempCO": {"name": "Heating Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "SetTempCWU": {"name": "Hot Water Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "CalcSetTempCO": {"name": "Calculated Heating Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "CalcSetTempCWU": {"name": "Calculated Hot Water Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    # Editable params setpoints (from getDeviceEditableParams)
    "HDWTSetPoint": {"name": "Hot Water Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "BuforsetPoint": {"name": "Buffer Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit1ComfortTemp": {"name": "Circuit 1 Comfort Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit1EcoTemp": {"name": "Circuit 1 Eco Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit1BaseTemp": {"name": "Circuit 1 Base Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit2ComfortTemp": {"name": "Circuit 2 Comfort Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit2EcoTemp": {"name": "Circuit 2 Eco Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit2BaseTemp": {"name": "Circuit 2 Base Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit3ComfortTemp": {"name": "Circuit 3 Comfort Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit3EcoTemp": {"name": "Circuit 3 Eco Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit3BaseTemp": {"name": "Circuit 3 Base Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "Circuit1WorkState": {"name": "Circuit 1 Work State", "device_class": None, "unit": None, "icon": "mdi:radiator"},
    "Circuit2WorkState": {"name": "Circuit 2 Work State", "device_class": None, "unit": None, "icon": "mdi:radiator"},
    "Circuit3WorkState": {"name": "Circuit 3 Work State", "device_class": None, "unit": None, "icon": "mdi:radiator"},
    "Circuit1CurveRadiator": {"name": "Circuit 1 Heating Curve", "device_class": None, "unit": None, "icon": "mdi:chart-line"},
    "Circuit2CurveFloor": {"name": "Circuit 2 Heating Curve", "device_class": None, "unit": None, "icon": "mdi:chart-line"},
    "HeatingCooling": {"name": "Heating/Cooling Mode", "device_class": None, "unit": None, "icon": "mdi:hvac"},
    "SummerOn": {"name": "Summer Mode On Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:weather-sunny"},
    "SummerOff": {"name": "Summer Mode Off Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:weather-sunny"},
    # Thermostat temps from curr
    "Circuit1thermostat": {"name": "Circuit 1 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit2thermostatTemp": {"name": "Circuit 2 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit3thermostatTemp": {"name": "Circuit 3 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit4thermostatTemp": {"name": "Circuit 4 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit5thermostatTemp": {"name": "Circuit 5 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit6thermostatTemp": {"name": "Circuit 6 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    "Circuit7thermostatTemp": {"name": "Circuit 7 Thermostat", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermostat"},
    # Polish setpoint names
    "tempZadanaCO": {"name": "Heating Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "tempZadanaCWU": {"name": "Hot Water Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "tempWyliczonaCO": {"name": "Calculated Heating Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "tempWyliczonaObieg1": {"name": "Circuit 1 Calculated Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},
    "tempWyliczonaObieg2": {"name": "Circuit 2 Calculated Setpoint", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-auto"},

    # ===== FLOW RATE =====
    "Flow": {"name": "Current Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "WaterFlow": {"name": "Water Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "FlowRate": {"name": "Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "przepyw": {"name": "Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "przeplyw": {"name": "Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},

    # ===== POWER / ENERGY =====
    "Power": {"name": "Current Power", "device_class": "power", "unit": "W", "icon": "mdi:flash"},
    "ElecPower": {"name": "Electrical Power", "device_class": "power", "unit": "W", "icon": "mdi:flash"},
    "CurrentPower": {"name": "Current Power Usage", "device_class": "power", "unit": "W", "icon": "mdi:flash"},
    "HeatingPower": {"name": "Heating Power", "device_class": "power", "unit": "kW", "icon": "mdi:flash"},
    "ThermalPower": {"name": "Thermal Power", "device_class": "power", "unit": "kW", "icon": "mdi:fire"},
    "EnergyTotal": {"name": "Total Energy", "device_class": "energy", "unit": "kWh", "icon": "mdi:lightning-bolt"},
    "EnergyToday": {"name": "Energy Today", "device_class": "energy", "unit": "kWh", "icon": "mdi:lightning-bolt"},
    "EnergyYesterday": {"name": "Energy Yesterday", "device_class": "energy", "unit": "kWh", "icon": "mdi:lightning-bolt"},
    "EnergyMonth": {"name": "Energy This Month", "device_class": "energy", "unit": "kWh", "icon": "mdi:lightning-bolt"},
    "COP": {"name": "Coefficient of Performance", "device_class": None, "unit": None, "icon": "mdi:chart-line"},
    # Polish power names
    "moc": {"name": "Power", "device_class": "power", "unit": "W", "icon": "mdi:flash"},
    "mocGrzania": {"name": "Heating Power", "device_class": "power", "unit": "kW", "icon": "mdi:fire"},
    "energiaZuzycie": {"name": "Energy Consumption", "device_class": "energy", "unit": "kWh", "icon": "mdi:lightning-bolt"},

    # ===== HEAT DEMAND =====
    "HeatDemand": {"name": "Heat Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "Demand": {"name": "Heating Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "DemandForHeat": {"name": "Demand for Heat", "device_class": None, "unit": None, "icon": "mdi:fire"},
    "HeatingDemand": {"name": "Heating Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "DemandCH": {"name": "Central Heating Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "DemandCWU": {"name": "Hot Water Demand", "device_class": None, "unit": "%", "icon": "mdi:water-boiler"},
    "ModulationLevel": {"name": "Modulation Level", "device_class": None, "unit": "%", "icon": "mdi:percent"},
    # Polish demand names
    "zapotrzebowanie": {"name": "Heat Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "zapotrzebowanieCO": {"name": "Heating Demand", "device_class": None, "unit": "%", "icon": "mdi:fire"},
    "zapotrzebowanieCWU": {"name": "Hot Water Demand", "device_class": None, "unit": "%", "icon": "mdi:water-boiler"},

    # ===== PRESSURE =====
    "Pressure": {"name": "System Pressure", "device_class": "pressure", "unit": "bar", "icon": "mdi:gauge"},
    "WaterPressure": {"name": "Water Pressure", "device_class": "pressure", "unit": "bar", "icon": "mdi:gauge"},
    "SystemPressure": {"name": "System Pressure", "device_class": "pressure", "unit": "bar", "icon": "mdi:gauge"},
    "cisnienie": {"name": "Pressure", "device_class": "pressure", "unit": "bar", "icon": "mdi:gauge"},

    # ===== PUMPS & ACTUATORS =====
    "PumpCH": {"name": "Central Heating Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "PumpCWU": {"name": "Hot Water Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "PumpCirc": {"name": "Circulation Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "PumpCircuit1": {"name": "Circuit 1 Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "PumpCircuit2": {"name": "Circuit 2 Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "Valve3Way": {"name": "3-Way Valve Position", "device_class": None, "unit": "%", "icon": "mdi:valve"},
    "MixerPosition": {"name": "Mixer Position", "device_class": None, "unit": "%", "icon": "mdi:valve"},
    # Polish pump names
    "pompaCO": {"name": "Central Heating Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "pompaCWU": {"name": "Hot Water Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "pompaObieg1": {"name": "Circuit 1 Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "pompaObieg2": {"name": "Circuit 2 Pump", "device_class": None, "unit": None, "icon": "mdi:pump"},
    "zawor3drogowy": {"name": "3-Way Valve", "device_class": None, "unit": "%", "icon": "mdi:valve"},
    "mieszacz": {"name": "Mixer Position", "device_class": None, "unit": "%", "icon": "mdi:valve"},

    # ===== FAN / BLOWER =====
    "FanSpeed": {"name": "Fan Speed", "device_class": None, "unit": "%", "icon": "mdi:fan"},
    "FanPower": {"name": "Fan Power", "device_class": None, "unit": "%", "icon": "mdi:fan"},
    "BlowerSpeed": {"name": "Blower Speed", "device_class": None, "unit": "RPM", "icon": "mdi:fan"},
    "wentylator": {"name": "Fan Speed", "device_class": None, "unit": "%", "icon": "mdi:fan"},
    "dmuchawa": {"name": "Blower Speed", "device_class": None, "unit": "%", "icon": "mdi:fan"},

    # ===== FUEL / CONSUMPTION =====
    "FuelLevel": {"name": "Fuel Level", "device_class": None, "unit": "%", "icon": "mdi:gas-station"},
    "FuelConsumption": {"name": "Fuel Consumption", "device_class": None, "unit": "kg/h", "icon": "mdi:fire"},
    "FuelTotal": {"name": "Total Fuel Used", "device_class": None, "unit": "kg", "icon": "mdi:counter"},
    "FeederWork": {"name": "Feeder Work Time", "device_class": "duration", "unit": "s", "icon": "mdi:clock"},
    # Polish fuel names
    "poziomPaliwa": {"name": "Fuel Level", "device_class": None, "unit": "%", "icon": "mdi:gas-station"},
    "zuzyciePaliwa": {"name": "Fuel Consumption", "device_class": None, "unit": "kg/h", "icon": "mdi:fire"},
    "podajnik": {"name": "Feeder Work Time", "device_class": "duration", "unit": "s", "icon": "mdi:clock"},

    # ===== STATUS / STATE =====
    "WorkMode": {"name": "Work Mode", "device_class": None, "unit": None, "icon": "mdi:state-machine"},
    "OperatingMode": {"name": "Operating Mode", "device_class": None, "unit": None, "icon": "mdi:state-machine"},
    "State": {"name": "System State", "device_class": None, "unit": None, "icon": "mdi:state-machine"},
    "HeaterState": {"name": "Heater State", "device_class": None, "unit": None, "icon": "mdi:fire"},
    "AlarmState": {"name": "Alarm State", "device_class": None, "unit": None, "icon": "mdi:alert"},
    "ErrorCode": {"name": "Error Code", "device_class": None, "unit": None, "icon": "mdi:alert-circle"},
    # Polish state names
    "trybPracy": {"name": "Work Mode", "device_class": None, "unit": None, "icon": "mdi:state-machine"},
    "stanPracy": {"name": "Operating State", "device_class": None, "unit": None, "icon": "mdi:state-machine"},
    "alarm": {"name": "Alarm State", "device_class": None, "unit": None, "icon": "mdi:alert"},

    # ===== RUNTIME / STATISTICS =====
    "RuntimeTotal": {"name": "Total Runtime", "device_class": "duration", "unit": "h", "icon": "mdi:clock"},
    "RuntimeToday": {"name": "Runtime Today", "device_class": "duration", "unit": "h", "icon": "mdi:clock"},
    "CompressorStarts": {"name": "Compressor Starts", "device_class": None, "unit": None, "icon": "mdi:counter"},
    "BurnerStarts": {"name": "Burner Starts", "device_class": None, "unit": None, "icon": "mdi:counter"},
    "czasPracyCalkowity": {"name": "Total Runtime", "device_class": "duration", "unit": "h", "icon": "mdi:clock"},
    "iloscZapalania": {"name": "Ignition Count", "device_class": None, "unit": None, "icon": "mdi:counter"},

    # ===== WIFI / CONNECTIVITY =====
    "wifiQuality": {"name": "WiFi Quality", "device_class": None, "unit": "%", "icon": "mdi:wifi"},
    "wifiStrength": {"name": "WiFi Signal Strength", "device_class": "signal_strength", "unit": "dBm", "icon": "mdi:wifi"},

    # ===== INFORMATION PARAMS (from getDeviceEditableParams.informationParams) =====
    # These use numeric keys from the API, mapped to friendly names
    "info_compressor_hz": {"name": "Compressor Frequency", "device_class": None, "unit": "Hz", "icon": "mdi:sine-wave"},
    "info_fan_rpm": {"name": "Fan Speed", "device_class": None, "unit": "RPM", "icon": "mdi:fan"},
    "info_flow_rate": {"name": "Current Flow Rate", "device_class": None, "unit": "L/min", "icon": "mdi:water-pump"},
    "info_electrical_power": {"name": "Electrical Power", "device_class": "power", "unit": "kW", "icon": "mdi:flash"},
    "info_pump_rpm": {"name": "Circulation Pump Speed", "device_class": None, "unit": "RPM", "icon": "mdi:pump"},
    "info_energy_wh": {"name": "Heat Energy", "device_class": "energy", "unit": "Wh", "icon": "mdi:lightning-bolt"},
    "info_hp_target_temp": {"name": "Heat Pump Target Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-check"},
    "info_hp_return_temp": {"name": "Heat Pump Return Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "info_outdoor_temp": {"name": "Outdoor Temperature (HP)", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "info_hp_flow_temp": {"name": "Heat Pump Flow Temperature", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer"},
    "info_cop": {"name": "Current COP", "device_class": None, "unit": None, "icon": "mdi:chart-line"},

    # ===== CALCULATED SENSORS =====
    "calc_delta_t": {"name": "Delta T (Flow - Return)", "device_class": "temperature", "unit": "°C", "icon": "mdi:thermometer-lines"},
}

# Mapping from informationParams numeric keys to sensor keys
# Based on analysis of getDeviceEditableParams response while heating is active
INFORMATION_PARAMS_MAP = {
    "21": "info_compressor_hz",      # Compressor frequency (Hz)
    "22": "info_fan_rpm",            # Fan speed (RPM)
    "231": "info_flow_rate",         # Current flow rate (L/min)
    "211": "info_electrical_power",  # Electrical power (kW)
    "26": "info_pump_rpm",           # Circulation pump speed (RPM)
    "203": "info_energy_wh",         # Heat energy (Wh)
    "24": "info_hp_target_temp",     # Heat pump target temperature
    "25": "info_hp_return_temp",     # Heat pump return temperature
    "212": "info_cop",               # COP value
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

                # Fetch current data from econet24
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

                    # Skip null values
                    if value is None:
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

                # Calculate and publish Delta T (Flow - Return temperature)
                flow_temp = curr.get("GrantOutgoingTemp")
                return_temp = curr.get("GrantReturnTemp")
                if (flow_temp is not None and return_temp is not None and
                    flow_temp != 999.0 and return_temp != 999.0):
                    delta_t = round(flow_temp - return_temp, 1)
                    self._publish_ha_discovery(device_uid, "calc_delta_t", SENSOR_DEFINITIONS["calc_delta_t"])
                    self._publish_sensor_value(device_uid, "calc_delta_t", delta_t)
                    logger.debug(f"[CALC] Delta T = {flow_temp} - {return_temp} = {delta_t}°C")

                # Fetch and publish editable params (setpoints, etc.)
                try:
                    editable = self.econet_client.get_editable_params(device_uid)
                    editable_data = editable.get("data", {})
                    editable_count = 0

                    # Parameters we want to expose from editable params
                    wanted_editable = [
                        "HDWTSetPoint", "BuforsetPoint",
                        "Circuit1ComfortTemp", "Circuit1EcoTemp", "Circuit1BaseTemp", "Circuit1WorkState",
                        "Circuit2ComfortTemp", "Circuit2EcoTemp", "Circuit2BaseTemp", "Circuit2WorkState",
                        "Circuit3ComfortTemp", "Circuit3EcoTemp", "Circuit3BaseTemp", "Circuit3WorkState",
                        "Circuit1CurveRadiator", "Circuit2CurveFloor",
                        "HeatingCooling", "SummerOn", "SummerOff",
                    ]

                    for param_id, param_data in editable_data.items():
                        param_name = param_data.get("name")
                        if param_name in wanted_editable:
                            value = param_data.get("value")
                            if value is not None:
                                if param_name in SENSOR_DEFINITIONS:
                                    self._publish_ha_discovery(device_uid, param_name, SENSOR_DEFINITIONS[param_name])
                                self._publish_sensor_value(device_uid, param_name, value)
                                editable_count += 1

                    if editable_count > 0:
                        logger.info(f"[MQTT] Published {editable_count} setpoint values to MQTT")

                    # Extract informationParams (flow rate, fan speed, power, etc.)
                    # These contain real-time operational data not available in curr
                    info_params = editable.get("informationParams", {})
                    info_count = 0

                    for info_key, info_data in info_params.items():
                        if info_key not in INFORMATION_PARAMS_MAP:
                            continue

                        sensor_key = INFORMATION_PARAMS_MAP[info_key]

                        # Structure: [visible_bool, [[value, unit_id, ???]]]
                        try:
                            if isinstance(info_data, list) and len(info_data) >= 2:
                                is_visible = info_data[0]
                                if not is_visible:
                                    continue

                                value_array = info_data[1]
                                if isinstance(value_array, list) and len(value_array) > 0:
                                    inner = value_array[0]
                                    if isinstance(inner, list) and len(inner) > 0:
                                        value = inner[0]
                                        # Convert string numbers to float
                                        if isinstance(value, str):
                                            try:
                                                value = float(value)
                                            except ValueError:
                                                pass

                                        if sensor_key in SENSOR_DEFINITIONS:
                                            self._publish_ha_discovery(device_uid, sensor_key, SENSOR_DEFINITIONS[sensor_key])
                                        self._publish_sensor_value(device_uid, sensor_key, value)
                                        info_count += 1
                                        logger.debug(f"[INFO] {sensor_key} = {value}")
                        except (IndexError, TypeError) as e:
                            logger.debug(f"[INFO] Could not parse {info_key}: {e}")

                    if info_count > 0:
                        logger.info(f"[MQTT] Published {info_count} information params (flow, power, etc.) to MQTT")

                except Exception as e:
                    logger.debug(f"[ECONET] Could not fetch editable params: {e}")

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
