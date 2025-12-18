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

LOG_LEVEL=$(bashio::config 'log_level')

# Set Python log level
case "${LOG_LEVEL}" in
    debug)
        export PYTHONUNBUFFERED=1
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

bashio::log.info "Starting Econet24 MQTT Bridge..."
bashio::log.info "MQTT Host: ${MQTT_HOST}:${MQTT_PORT}"
bashio::log.info "Poll Interval: ${POLL_INTERVAL} seconds"

# Run the bridge
cd /app
exec python3 -u econet24_mqtt_bridge.py
