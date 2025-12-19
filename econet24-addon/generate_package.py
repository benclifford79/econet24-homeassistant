#!/usr/bin/env python3
"""
Generate Home Assistant files for Econet24 integration.

This script creates:
- Package YAML with template sensors (/config/packages/econet24_package.yaml)
- SVG diagram for dashboard (/config/www/econet24_heat_pump.svg)
- Card YAML for easy copy/paste (/config/www/econet24_card.yaml)
"""

import os
import re
import sys
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to a slug suitable for entity IDs."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def generate_svg(output_path: str) -> bool:
    """Generate the heat pump SVG diagram."""

    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" style="background:#1a1a2e">
  <defs>
    <linearGradient id="flowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#ff6b6b"/>
      <stop offset="100%" style="stop-color:#ee5a5a"/>
    </linearGradient>
    <linearGradient id="returnGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#4dabf7"/>
      <stop offset="100%" style="stop-color:#339af0"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Background panel -->
  <rect x="10" y="10" width="380" height="280" rx="15" fill="#16213e" stroke="#0f3460" stroke-width="2"/>

  <!-- Title -->
  <text x="200" y="285" text-anchor="middle" fill="#ffffff" font-family="Arial" font-size="14" font-weight="bold">Heat Pump</text>

  <!-- Outdoor section (top) -->
  <g id="outdoor">
    <path d="M180 35 Q175 25 185 25 Q190 20 200 25 Q210 20 215 25 Q225 25 220 35 Z" fill="#4dabf7" opacity="0.8"/>
    <rect id="outdoor_temp_bg" x="230" y="22" width="50" height="22" rx="4" fill="#0f3460"/>
  </g>

  <!-- Heat Pump Unit (center) -->
  <g id="heat_pump_unit">
    <rect x="100" y="70" width="120" height="100" rx="8" fill="#0f3460" stroke="#4dabf7" stroke-width="2"/>

    <!-- Compressor fan icon -->
    <circle cx="140" cy="120" r="30" fill="none" stroke="#4dabf7" stroke-width="2"/>
    <g id="fan_blades" fill="#4dabf7">
      <ellipse cx="140" cy="105" rx="6" ry="12" transform="rotate(0 140 120)"/>
      <ellipse cx="140" cy="105" rx="6" ry="12" transform="rotate(72 140 120)"/>
      <ellipse cx="140" cy="105" rx="6" ry="12" transform="rotate(144 140 120)"/>
      <ellipse cx="140" cy="105" rx="6" ry="12" transform="rotate(216 140 120)"/>
      <ellipse cx="140" cy="105" rx="6" ry="12" transform="rotate(288 140 120)"/>
    </g>
    <circle cx="140" cy="120" r="5" fill="#4dabf7"/>

    <!-- Secondary fan (smaller) -->
    <circle cx="190" cy="110" r="18" fill="none" stroke="#4dabf7" stroke-width="1.5"/>
    <g fill="#4dabf7" opacity="0.8">
      <ellipse cx="190" cy="100" rx="4" ry="8" transform="rotate(0 190 110)"/>
      <ellipse cx="190" cy="100" rx="4" ry="8" transform="rotate(90 190 110)"/>
      <ellipse cx="190" cy="100" rx="4" ry="8" transform="rotate(180 190 110)"/>
      <ellipse cx="190" cy="100" rx="4" ry="8" transform="rotate(270 190 110)"/>
    </g>
    <circle cx="190" cy="110" r="3" fill="#4dabf7"/>

    <!-- Status labels area -->
    <rect id="pump_status_bg" x="105" y="155" width="35" height="12" rx="2" fill="#0a1628"/>
    <rect id="freq_status_bg" x="145" y="155" width="35" height="12" rx="2" fill="#0a1628"/>
    <rect id="comp_status_bg" x="185" y="155" width="30" height="12" rx="2" fill="#0a1628"/>
  </g>

  <!-- Pressure gauge (top of unit) -->
  <g id="pressure">
    <circle cx="160" cy="60" r="12" fill="#0f3460" stroke="#ffd43b" stroke-width="1.5"/>
    <rect id="pressure_bg" x="175" y="52" width="40" height="16" rx="3" fill="#0a1628"/>
  </g>

  <!-- Flow pipe (hot - going out) -->
  <g id="flow_pipe">
    <path d="M220 100 L280 100 L280 180 L320 180" fill="none" stroke="url(#flowGrad)" stroke-width="8" stroke-linecap="round"/>
    <path d="M220 100 L280 100 L280 180 L320 180" fill="none" stroke="#ff6b6b" stroke-width="4" stroke-linecap="round" opacity="0.5" filter="url(#glow)"/>
    <rect id="flow_temp_bg" x="285" y="85" width="55" height="22" rx="4" fill="#0f3460" stroke="#ff6b6b" stroke-width="1"/>
  </g>

  <!-- Return pipe (cold - coming back) -->
  <g id="return_pipe">
    <path d="M220 140 L260 140 L260 220 L320 220" fill="none" stroke="url(#returnGrad)" stroke-width="8" stroke-linecap="round"/>
    <path d="M220 140 L260 140 L260 220 L320 220" fill="none" stroke="#4dabf7" stroke-width="4" stroke-linecap="round" opacity="0.5" filter="url(#glow)"/>
    <rect id="return_temp_bg" x="285" y="205" width="55" height="22" rx="4" fill="#0f3460" stroke="#4dabf7" stroke-width="1"/>
  </g>

  <!-- Buffer tank / Underfloor heating (bottom) -->
  <g id="buffer">
    <path d="M50 200 L50 260 Q50 270 60 270 L150 270 Q160 270 160 260 L160 200" fill="none" stroke="#4dabf7" stroke-width="2"/>
    <path d="M70 240 Q80 235 90 240 Q100 245 110 240 Q120 235 130 240" fill="none" stroke="#4dabf7" stroke-width="1.5" opacity="0.6"/>
    <path d="M70 250 Q80 245 90 250 Q100 255 110 250 Q120 245 130 250" fill="none" stroke="#4dabf7" stroke-width="1.5" opacity="0.4"/>
    <line x1="40" y1="270" x2="170" y2="270" stroke="#4dabf7" stroke-width="1" opacity="0.5"/>
  </g>

  <!-- Connection from heat pump to buffer -->
  <path d="M100 140 L60 140 L60 200" fill="none" stroke="#4dabf7" stroke-width="6" stroke-linecap="round"/>

  <!-- Status indicator (bottom left of unit) -->
  <g id="status_indicator">
    <circle cx="45" cy="120" r="8" fill="#0f3460" stroke="#51cf66" stroke-width="2"/>
    <circle id="status_dot" cx="45" cy="120" r="4" fill="#51cf66"/>
  </g>

  <!-- Hot water icon (left side) -->
  <g id="hot_water" transform="translate(30, 60)">
    <path d="M10 25 Q5 15 10 10 Q15 5 10 0" fill="none" stroke="#4dabf7" stroke-width="2" stroke-linecap="round"/>
    <ellipse cx="10" cy="30" rx="8" ry="5" fill="#4dabf7" opacity="0.6"/>
  </g>

  <!-- Delta T indicator (between pipes) -->
  <g id="delta_t">
    <text x="270" y="160" fill="#ffd43b" font-family="Arial" font-size="10">DT</text>
    <rect id="delta_t_bg" x="280" y="150" width="35" height="16" rx="3" fill="#0a1628"/>
  </g>

</svg>'''

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(svg_content)

    return True


def generate_card(output_path: str) -> bool:
    """Generate the dashboard card YAML."""

    card_content = '''# =============================================================================
# Econet24 Heat Pump Picture Elements Card
# =============================================================================
# AUTO-GENERATED by Econet24 MQTT Bridge add-on
#
# HOW TO USE:
# 1. Edit your dashboard
# 2. Add Card > Manual Card
# 3. Copy everything below the dashed line and paste it
# =============================================================================
# ---- COPY FROM HERE ----

type: picture-elements
image: /local/econet24_heat_pump.svg
elements:
  # Outdoor Temperature (top)
  - type: state-label
    entity: sensor.heat_pump_outdoor_temperature
    style:
      top: 11%
      left: 67%
      color: white
      font-size: 14px
      font-weight: bold
      text-shadow: 1px 1px 2px black

  # Flow Temperature (red pipe)
  - type: state-label
    entity: sensor.heat_pump_flow_temperature
    style:
      top: 34%
      left: 82%
      color: "#ff6b6b"
      font-size: 13px
      font-weight: bold

  # Return Temperature (blue pipe)
  - type: state-label
    entity: sensor.heat_pump_return_temperature
    style:
      top: 74%
      left: 82%
      color: "#4dabf7"
      font-size: 13px
      font-weight: bold

  # Delta T
  - type: state-label
    entity: sensor.heat_pump_delta_t
    style:
      top: 53%
      left: 80%
      color: "#ffd43b"
      font-size: 11px

  # Compressor Frequency
  - type: state-label
    entity: sensor.heat_pump_compressor_frequency
    suffix: " Hz"
    style:
      top: 56%
      left: 42%
      color: "#4dabf7"
      font-size: 10px

  # Pump Speed
  - type: state-label
    entity: sensor.heat_pump_pump_speed
    suffix: " rpm"
    style:
      top: 56%
      left: 30%
      color: "#4dabf7"
      font-size: 10px

  # Status
  - type: state-label
    entity: sensor.heat_pump_status
    style:
      top: 56%
      left: 54%
      color: "#51cf66"
      font-size: 10px

  # Weather Icon
  - type: icon
    icon: mdi:weather-partly-cloudy
    style:
      top: 11%
      left: 48%
      color: "#4dabf7"
      font-size: 18px
    tap_action:
      action: more-info
      entity: sensor.heat_pump_outdoor_temperature
'''

    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(card_content)

    return True


def generate_package(device_prefix: str, output_path: str) -> bool:
    """Generate the Home Assistant package YAML file."""

    package_content = f'''# =============================================================================
# Econet24 Heat Pump Package for Home Assistant
# =============================================================================
# AUTO-GENERATED by Econet24 MQTT Bridge add-on
# Device prefix: {device_prefix}
#
# This package creates proxy sensors with friendly names that reference
# your actual Econet24 entities. Use these sensors in your dashboards.
# =============================================================================

# -----------------------------------------------------------------------------
# TEMPLATE SENSORS - Proxy sensors with friendly names
# -----------------------------------------------------------------------------

template:
  # ---------------------------------------------------------------------------
  # Heat Pump Core Sensors
  # ---------------------------------------------------------------------------
  - sensor:
      - name: "Heat Pump Flow Temperature"
        unique_id: econet24_proxy_flow_temp
        icon: mdi:thermometer
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_flow_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_flow_temperature') not in ['unknown', 'unavailable'] }}}}

      - name: "Heat Pump Return Temperature"
        unique_id: econet24_proxy_return_temp
        icon: mdi:thermometer
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_return_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_return_temperature') not in ['unknown', 'unavailable'] }}}}

      - name: "Heat Pump Outdoor Temperature"
        unique_id: econet24_proxy_outdoor_temp
        icon: mdi:thermometer
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_outdoor_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_outdoor_temperature') not in ['unknown', 'unavailable'] }}}}

      - name: "Heat Pump Compressor Frequency"
        unique_id: econet24_proxy_compressor_freq
        icon: mdi:sine-wave
        unit_of_measurement: "Hz"
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_compressor_frequency') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_compressor_frequency') not in ['unknown', 'unavailable'] }}}}

      - name: "Heat Pump Pump Speed"
        unique_id: econet24_proxy_pump_speed
        icon: mdi:pump
        unit_of_measurement: "RPM"
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_pump_speed') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_pump_speed') not in ['unknown', 'unavailable'] }}}}

      # Work State with friendly text
      - name: "Heat Pump Status"
        unique_id: econet24_proxy_status
        icon: mdi:heat-pump
        state: >
          {{% set state = states('sensor.econet24_{device_prefix}_heat_pump_work_state') | int(-1) %}}
          {{% set modes = {{
            0: 'Off',
            1: 'Running',
            2: 'Heating',
            3: 'Hot Water',
            4: 'Defrost',
            5: 'Standby',
            6: 'Cooling',
            7: 'Error'
          }} %}}
          {{{{ modes.get(state, 'Unknown (' ~ state ~ ')') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_work_state') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # Hot Water & Buffer Tank
  # ---------------------------------------------------------------------------
      - name: "Hot Water Temperature"
        unique_id: econet24_proxy_hot_water_temp
        icon: mdi:water-boiler
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_hot_water_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_hot_water_temperature') not in ['unknown', 'unavailable'] }}}}

      - name: "Buffer Tank Temperature"
        unique_id: econet24_proxy_buffer_temp
        icon: mdi:storage-tank
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_buffer_tank_bottom_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_buffer_tank_bottom_temperature') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # Weather & Outdoor
  # ---------------------------------------------------------------------------
      - name: "Weather Temperature"
        unique_id: econet24_proxy_weather_temp
        icon: mdi:weather-partly-cloudy
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_weather_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_weather_temperature') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # Heating Circuits
  # ---------------------------------------------------------------------------
      - name: "Circuit 2 Temperature"
        unique_id: econet24_proxy_circuit2_temp
        icon: mdi:thermometer
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_circuit_2_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_circuit_2_temperature') not in ['unknown', 'unavailable'] }}}}

      - name: "Circuit 3 Temperature"
        unique_id: econet24_proxy_circuit3_temp
        icon: mdi:thermometer
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_circuit_3_temperature') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_circuit_3_temperature') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # System Info
  # ---------------------------------------------------------------------------
      - name: "Econet24 WiFi Quality"
        unique_id: econet24_proxy_wifi_quality
        icon: mdi:wifi
        unit_of_measurement: "%"
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_wifi_quality') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_wifi_quality') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # Calculated Sensors
  # ---------------------------------------------------------------------------
      # Delta T (Flow - Return) - useful for efficiency monitoring
      - name: "Heat Pump Delta T"
        unique_id: econet24_proxy_delta_t
        icon: mdi:thermometer-lines
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{% set flow = states('sensor.econet24_{device_prefix}_heat_pump_flow_temperature') | float(none) %}}
          {{% set ret = states('sensor.econet24_{device_prefix}_heat_pump_return_temperature') | float(none) %}}
          {{% if flow is not none and ret is not none and flow > 0 and ret > 0 %}}
            {{{{ (flow - ret) | round(1) }}}}
          {{% else %}}
            unknown
          {{% endif %}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_flow_temperature') not in ['unknown', 'unavailable']
             and states('sensor.econet24_{device_prefix}_heat_pump_return_temperature') not in ['unknown', 'unavailable'] }}}}

      # Calculated Heating Setpoint (what the heat pump is targeting)
      - name: "Heat Pump Target Temperature"
        unique_id: econet24_proxy_target_temp
        icon: mdi:thermometer-auto
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        state: >
          {{{{ states('sensor.econet24_{device_prefix}_calculated_heating_setpoint') }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_calculated_heating_setpoint') not in ['unknown', 'unavailable'] }}}}

  # ---------------------------------------------------------------------------
  # Binary Sensors
  # ---------------------------------------------------------------------------
  - binary_sensor:
      - name: "Heat Pump Running"
        unique_id: econet24_proxy_running
        icon: mdi:heat-pump
        device_class: running
        state: >
          {{% set state = states('sensor.econet24_{device_prefix}_heat_pump_work_state') | int(0) %}}
          {{{{ state > 0 }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_heat_pump_work_state') not in ['unknown', 'unavailable'] }}}}

      - name: "Compressor Running"
        unique_id: econet24_proxy_compressor_running
        icon: mdi:sine-wave
        device_class: running
        state: >
          {{% set freq = states('sensor.econet24_{device_prefix}_compressor_frequency') | int(0) %}}
          {{{{ freq > 0 }}}}
        availability: >
          {{{{ states('sensor.econet24_{device_prefix}_compressor_frequency') not in ['unknown', 'unavailable'] }}}}
'''

    # Ensure packages directory exists
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write the package file
    with open(output_path, 'w') as f:
        f.write(package_content)

    return True


def main():
    """Main entry point."""
    device_name = os.environ.get("DEVICE_NAME", "").strip()
    device_uid = os.environ.get("DEVICE_UID", "").strip()
    generate = os.environ.get("GENERATE_PACKAGE", "false").lower() == "true"

    if not generate:
        print("[GENERATE] File generation disabled, skipping")
        return

    # Determine the device prefix (same logic as the bridge)
    if device_name:
        device_prefix = slugify(device_name)
        print(f"[GENERATE] Using device_name as prefix: {device_prefix}")
    elif device_uid:
        device_prefix = device_uid[:8].lower()
        print(f"[GENERATE] Using device UID as prefix: {device_prefix}")
    else:
        print("[GENERATE] ERROR: No device_name or device_uid available")
        print("[GENERATE] Set device_name in add-on config to enable file generation")
        return

    # File paths (all prefixed with econet24_)
    package_path = "/config/packages/econet24_package.yaml"
    svg_path = "/config/www/econet24_heat_pump.svg"
    card_path = "/config/www/econet24_card.yaml"

    print(f"[GENERATE] Device prefix: {device_prefix}")

    # Generate package file
    try:
        print(f"[GENERATE] Creating {package_path}")
        generate_package(device_prefix, package_path)
        print(f"[GENERATE] SUCCESS: {package_path}")
    except Exception as e:
        print(f"[GENERATE] ERROR creating package: {e}")

    # Generate SVG diagram
    try:
        print(f"[GENERATE] Creating {svg_path}")
        generate_svg(svg_path)
        print(f"[GENERATE] SUCCESS: {svg_path}")
    except Exception as e:
        print(f"[GENERATE] ERROR creating SVG: {e}")

    # Generate card YAML
    try:
        print(f"[GENERATE] Creating {card_path}")
        generate_card(card_path)
        print(f"[GENERATE] SUCCESS: {card_path}")
    except Exception as e:
        print(f"[GENERATE] ERROR creating card: {e}")

    print("[GENERATE] ----------------------------------------")
    print("[GENERATE] Files generated! Next steps:")
    print("[GENERATE] 1. Restart Home Assistant to load the package")
    print("[GENERATE] 2. Edit Dashboard > Add Card > Manual")
    print("[GENERATE] 3. Copy contents from /config/www/econet24_card.yaml")
    print("[GENERATE] ----------------------------------------")


if __name__ == "__main__":
    main()
