#!/usr/bin/with-contenv bashio
set -e

OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
INSTRUCTIONS="$(bashio::config 'instructions')"
TEXT_MODEL="$(bashio::config 'text_model')"
REALTIME_MODEL="$(bashio::config 'realtime_model')"
REALTIME_VOICE="$(bashio::config 'realtime_voice')"
RUNNER_HOST="$(bashio::config 'runner_host')"
RUNNER_PORT="$(bashio::config 'runner_port')"
ESP32_MODE="$(bashio::config 'esp32_mode')"
SATELLITE_SHARED_SECRET="$(bashio::config 'satellite_shared_secret')"
HA_MCP_URL="$(bashio::config 'ha_mcp_url')"
LONGLIVED_TOKEN="$(bashio::config 'longlived_token')"
MCP_TOOL_ALLOWLIST="$(bashio::config 'mcp_tool_allowlist')"
LOG_LEVEL="$(bashio::config 'log_level')"

export OPENAI_API_KEY
export INSTRUCTIONS
export TEXT_MODEL
export REALTIME_MODEL
export REALTIME_VOICE
export RUNNER_HOST
export RUNNER_PORT
export ESP32_MODE
export SATELLITE_SHARED_SECRET
export LONGLIVED_TOKEN
export MCP_TOOL_ALLOWLIST
export LOG_LEVEL

if [ -n "$HA_MCP_URL" ]; then
    export HA_MCP_URL
fi

ARGS=(--host "$RUNNER_HOST" --port "$RUNNER_PORT" -t webrtc)
if bashio::var.true "$ESP32_MODE"; then
    ARGS+=(--esp32)
fi

exec python3 -m app.main "${ARGS[@]}"

