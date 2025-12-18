#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

# Read configuration from add-on options
export ECONET24_USERNAME=$(bashio::config 'econet24_username')
export ECONET24_PASSWORD=$(bashio::config 'econet24_password')
export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USERNAME=$(bashio::config 'mqtt_username')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export POLL_INTERVAL=$(bashio::config 'poll_interval')
export DEVICE_NAME=$(bashio::config 'device_name')

# Get log level from config and convert to uppercase for Python
LOG_LEVEL_CONFIG=$(bashio::config 'log_level')

case "${LOG_LEVEL_CONFIG}" in
    debug)
        export LOG_LEVEL="DEBUG"
        ;;
    warning)
        export LOG_LEVEL="WARNING"
        ;;
    error)
        export LOG_LEVEL="ERROR"
        ;;
    *)
        export LOG_LEVEL="INFO"
        ;;
esac

# Ensure Python output is unbuffered (shows logs immediately)
export PYTHONUNBUFFERED=1

bashio::log.info "========================================"
bashio::log.info "Econet24 MQTT Bridge Add-on"
bashio::log.info "========================================"
bashio::log.info "Log Level: ${LOG_LEVEL}"
bashio::log.info "MQTT Host: ${MQTT_HOST}:${MQTT_PORT}"
bashio::log.info "Poll Interval: ${POLL_INTERVAL} seconds"
bashio::log.info "========================================"

# Run the bridge
cd /app
exec python3 -u econet24_mqtt_bridge.py
