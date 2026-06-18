"""Runtime configuration for the Pipecat Assist add-on."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

DATA_DIR = Path(os.getenv("PIPECAT_ASSIST_DATA_DIR", "/data"))
CONFIG_PATH = DATA_DIR / "pipecat_assist.json"
REDACTED = "__redacted__"

DEFAULT_INSTRUCTIONS = (
    "You are a realtime Home Assistant voice agent. Speak naturally and briefly. "
    "Use Home Assistant MCP tools only when the user clearly asks to control, "
    "inspect, or automate the home. Never invent device state. If a room, "
    "device, or action is ambiguous, ask one short clarification."
)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class FlowConfig(BaseModel):
    """One realtime assistant flow."""

    id: str = "home-default"
    name: str = "Home Assistant realtime"
    enabled: bool = True
    provider: Literal["openai_realtime"] = "openai_realtime"
    model: str = "gpt-realtime-2"
    voice: str = "marin"
    speed: float = Field(default=1.0, ge=0.25, le=1.5)
    language: str | None = None
    instructions: str = DEFAULT_INSTRUCTIONS
    greeting: str = "Greet the user briefly and wait for their request."
    transcription_model: str = "gpt-realtime-whisper"
    noise_reduction: Literal["off", "near_field", "far_field"] = "near_field"
    vad_mode: Literal["semantic_vad", "server_vad"] = "semantic_vad"
    vad_eagerness: Literal["low", "medium", "high", "auto"] = "low"
    interrupt_response: bool = False
    max_output_tokens: int | None = Field(default=None, ge=1, le=4096)
    reasoning_effort: Literal["minimal", "low", "medium", "high", "xhigh"] | None = None
    mcp_enabled: bool = True
    mcp_tool_allowlist: list[str] = Field(default_factory=list)
    video_enabled: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("Flow id cannot be empty")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if any(char not in allowed for char in clean):
            raise ValueError("Flow id may only contain letters, numbers, _ and -")
        return clean


class RuntimeConfig(BaseModel):
    """Persisted runtime configuration edited by the web UI."""

    version: int = 1
    openai_api_key: str = ""
    text_model: str = "gpt-5.4-mini"
    ha_mcp_url: str = ""
    longlived_token: str = ""
    satellite_shared_secret: str = ""
    runner_host: str = "0.0.0.0"
    runner_port: int = Field(default=7860, ge=1024, le=65535)
    esp32_mode: bool = False
    enable_default_ice_servers: bool = False
    selected_flow_id: str = "home-default"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    flows: list[FlowConfig] = Field(default_factory=lambda: [FlowConfig()])

    @field_validator("flows")
    @classmethod
    def validate_flows(cls, value: list[FlowConfig]) -> list[FlowConfig]:
        if not value:
            raise ValueError("At least one flow is required")
        ids = [flow.id for flow in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Flow ids must be unique")
        return value

    def selected_flow(self, requested_flow_id: str | None = None) -> FlowConfig:
        """Return the requested flow, falling back to selected/default flow."""

        candidates = [requested_flow_id, self.selected_flow_id, self.flows[0].id]
        for candidate in candidates:
            if not candidate:
                continue
            for flow in self.flows:
                if flow.id == candidate:
                    return flow
        return self.flows[0]

    @property
    def effective_mcp_url(self) -> str:
        """Return the MCP URL used by the add-on."""

        return self.ha_mcp_url or os.getenv("HA_MCP_URL") or "http://supervisor/core/api/mcp"

    @property
    def effective_mcp_token(self) -> str:
        """Return the Home Assistant token used for MCP."""

        return self.longlived_token or os.getenv("LONGLIVED_TOKEN") or os.getenv("SUPERVISOR_TOKEN", "")

    def public_dict(self) -> dict[str, Any]:
        """Return configuration safe enough for the UI."""

        data = self.model_dump()
        for key in ("openai_api_key", "longlived_token", "satellite_shared_secret"):
            configured = bool(data.get(key))
            data[f"{key}_configured"] = configured
            data[key] = REDACTED if configured else ""
        data["effective_mcp_url"] = self.effective_mcp_url
        return data


def default_config_from_environment() -> RuntimeConfig:
    """Create the first-run configuration from add-on options."""

    instructions = os.getenv("INSTRUCTIONS") or DEFAULT_INSTRUCTIONS
    tool_allowlist = _split_csv(os.getenv("MCP_TOOL_ALLOWLIST"))
    flow = FlowConfig(
        model=os.getenv("REALTIME_MODEL", "gpt-realtime-2"),
        voice=os.getenv("REALTIME_VOICE", "marin"),
        instructions=instructions,
        mcp_tool_allowlist=tool_allowlist,
    )
    return RuntimeConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        text_model=os.getenv("TEXT_MODEL", "gpt-5.4-mini"),
        ha_mcp_url=os.getenv("HA_MCP_URL", ""),
        longlived_token=os.getenv("LONGLIVED_TOKEN", ""),
        satellite_shared_secret=os.getenv("SATELLITE_SHARED_SECRET", ""),
        runner_host=os.getenv("RUNNER_HOST", "0.0.0.0"),
        runner_port=_env_int("RUNNER_PORT", 7860),
        esp32_mode=_env_bool("ESP32_MODE", False),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        flows=[flow],
    )


class ConfigStore:
    """Read and write runtime configuration."""

    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path

    def load(self) -> RuntimeConfig:
        """Load persisted config, creating it when absent."""

        default = default_config_from_environment()
        if not self.path.exists():
            if not default.satellite_shared_secret:
                default.satellite_shared_secret = secrets.token_urlsafe(24)
            self.save(default)
            return default

        with self.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        data = default.model_dump()
        data.update(raw)
        config = RuntimeConfig.model_validate(data)

        if not config.openai_api_key:
            config.openai_api_key = default.openai_api_key
        if not config.longlived_token:
            config.longlived_token = default.longlived_token
        if not config.satellite_shared_secret:
            config.satellite_shared_secret = (
                default.satellite_shared_secret or secrets.token_urlsafe(24)
            )
            self.save(config)
        return config

    def save(self, config: RuntimeConfig) -> None:
        """Persist config atomically enough for a single add-on process."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(config.model_dump(), file, indent=2, sort_keys=True)
            file.write("\n")
        tmp_path.replace(self.path)

    def update_from_public(self, payload: dict[str, Any]) -> RuntimeConfig:
        """Apply a UI update while preserving redacted secrets."""

        current = self.load()
        data = current.model_dump()
        data.update(payload)
        for key in ("openai_api_key", "longlived_token", "satellite_shared_secret"):
            incoming = payload.get(key)
            if incoming in (None, "", REDACTED):
                data[key] = getattr(current, key)
        config = RuntimeConfig.model_validate(data)
        self.save(config)
        return config

