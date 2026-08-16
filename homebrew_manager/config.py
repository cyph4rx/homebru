from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a Homebru connection configuration is invalid."""


def default_config_path() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "homebrew" / "config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "homebrew" / "config.json"


@dataclass(slots=True)
class ServerConfig:
    host: str
    token: str
    port: int = 8420
    scheme: str = "http"
    refresh_interval: float = 2.0
    request_timeout: float = 5.0

    def __post_init__(self) -> None:
        raw_host = self.host.strip()
        if raw_host.startswith("https://"):
            self.scheme = "https"
        elif raw_host.startswith("http://"):
            self.scheme = "http"
        self.host = raw_host.removeprefix("http://").removeprefix("https://").rstrip("/")
        self.token = self.token.strip()
        self.scheme = self.scheme.lower().strip()
        if not self.host or any(char.isspace() for char in self.host):
            raise ConfigError("host must be a hostname or IP address without spaces")
        if not self.token:
            raise ConfigError("token cannot be empty")
        if self.scheme not in {"http", "https"}:
            raise ConfigError("scheme must be http or https")
        if not 1 <= int(self.port) <= 65535:
            raise ConfigError("port must be between 1 and 65535")
        if not 0.5 <= float(self.refresh_interval) <= 60:
            raise ConfigError("refresh interval must be between 0.5 and 60 seconds")
        if not 1 <= float(self.request_timeout) <= 120:
            raise ConfigError("request timeout must be between 1 and 120 seconds")
        self.port = int(self.port)
        self.refresh_interval = float(self.refresh_interval)
        self.request_timeout = float(self.request_timeout)

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ServerConfig":
        try:
            return cls(
                host=value["host"],
                token=value["token"],
                port=value.get("port", 8420),
                scheme=value.get("scheme", "http"),
                refresh_interval=value.get("refresh_interval", 2.0),
                request_timeout=value.get("request_timeout", 5.0),
            )
        except (KeyError, TypeError) as exc:
            raise ConfigError(f"invalid configuration: {exc}") from exc


def load_config(path: Path | None = None) -> ServerConfig | None:
    config_path = path or default_config_path()
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not read {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError(f"configuration in {config_path} must be a JSON object")
    return ServerConfig.from_dict(payload)


def save_config(config: ServerConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(config_path)
    return config_path
