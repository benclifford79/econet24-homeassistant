# Econet24 MQTT Bridge

This add-on bridges your Plum ecoMAX/Grant heat pump data from econet24.com to Home Assistant via MQTT.

## Requirements

- An account on [econet24.com](https://www.econet24.com)
- A Plum ecoMAX controller (e.g., ecoMAX360i) connected to econet24
- The Mosquitto MQTT broker add-on (or another MQTT broker)

## Installation

1. Add this repository to your Home Assistant Add-on Store
2. Install the "Econet24 MQTT Bridge" add-on
3. Configure your credentials (see below)
4. Start the add-on

## Configuration

| Option | Description |
|--------|-------------|
| `econet24_username` | Your econet24.com email address |
| `econet24_password` | Your econet24.com password |
| `mqtt_host` | MQTT broker hostname (default: `core-mosquitto`) |
| `mqtt_port` | MQTT broker port (default: `1883`) |
| `mqtt_username` | MQTT username (optional) |
| `mqtt_password` | MQTT password (optional) |
| `poll_interval` | Seconds between data fetches (default: `60`) |
| `log_level` | Logging verbosity: debug, info, warning, error |
| `device_name` | Custom device name for friendly entity IDs (optional) |
| `generate_package` | Auto-generate HA package with proxy sensors (default: `true`) |

### Device Name

Setting `device_name` gives you predictable, friendly entity IDs:

- **Without device_name**: `sensor.econet24_0fsecpma_heat_pump_flow_temperature`
- **With device_name: "Grant"**: `sensor.econet24_grant_heat_pump_flow_temperature`

This makes it easier to share dashboard configurations with other users.

## Sensors

The following sensors are automatically discovered in Home Assistant:

### Heat Pump
- Heat Pump Flow Temperature
- Heat Pump Return Temperature
- Heat Pump Outdoor Temperature
- Compressor Frequency
- Pump Speed
- Work State

### Temperatures
- Weather Temperature
- Hot Water Temperature (CWU)
- Buffer Tank Top/Bottom Temperature
- Heating Circuit Temperatures

### Diagnostics
- WiFi Quality
- WiFi Signal Strength

## Auto-Generated Files

When `generate_package` is enabled (default), the add-on automatically creates:

| File | Description |
|------|-------------|
| `/config/packages/econet24_package.yaml` | Template sensors with friendly names |
| `/config/www/econet24_heat_pump.svg` | Visual diagram for dashboard card |
| `/config/www/econet24_card.yaml` | Ready-to-paste card configuration |

### Proxy Sensors Created

- `sensor.heat_pump_flow_temperature`
- `sensor.heat_pump_return_temperature`
- `sensor.heat_pump_outdoor_temperature`
- `sensor.heat_pump_status` (with friendly text: Off, Heating, etc.)
- `sensor.heat_pump_delta_t` (calculated)
- `sensor.heat_pump_compressor_frequency`
- `binary_sensor.compressor_running`
- And more...

### Setup

1. Set `device_name` in the add-on configuration (e.g., "Grant")

2. Enable packages in your `configuration.yaml` (one-time):
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```

3. Restart the add-on - files will be generated automatically

4. Restart Home Assistant to load the package

5. Add the visual card to your dashboard:
   - Edit Dashboard > Add Card > **Manual**
   - Open `/config/www/econet24_card.yaml` in File Editor
   - Copy everything below `# ---- COPY FROM HERE ----`
   - Paste into the card editor

### Manual Installation

Set `generate_package: false` to disable auto-generation and manage files manually.

## Support

Report issues at: https://github.com/benclifford79/econet24-homeassistant/issues
