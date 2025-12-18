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

## Support

Report issues at: https://github.com/YOUR_USERNAME/econet-scraper/issues
