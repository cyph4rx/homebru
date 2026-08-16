import json
import os
import secrets
from pathlib import Path
from typing import Any


def default_config_path() -> Path:
    override = os.environ.get("AGENT_CONFIG_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "data" / "config.json"


CONFIG_PATH = default_config_path()

VALID_SERVICE_NAME_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


class ConfigError(ValueError):
    pass


def _generate_token() -> str:
    return secrets.token_hex(24)


def _new_default_config() -> dict[str, Any]:
    return {
        "token": None,
        "port": 8420,
        "allowed_services": [],
        "managed_apps": [],
        "cors_origins": [],
    }


def _read_config_file(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return _new_default_config()
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"could not read {config_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError("agent configuration must be a JSON object")
    return {**_new_default_config(), **loaded}


def _validate_port(config: dict[str, Any]) -> None:
    try:
        config["port"] = int(config["port"])
    except (TypeError, ValueError) as exc:
        raise ConfigError("port must be a number") from exc
    if not 1 <= config["port"] <= 65535:
        raise ConfigError("port must be between 1 and 65535")


def _validate_allowed_services(config: dict[str, Any]) -> list[str]:
    if not isinstance(config["allowed_services"], list) or not all(
        isinstance(name, str) and name.strip() for name in config["allowed_services"]
    ):
        raise ConfigError("allowed_services must be a list of non-empty service names")
    allowed_services = list(dict.fromkeys(name.strip() for name in config["allowed_services"]))
    config["allowed_services"] = allowed_services
    return allowed_services


def _validate_managed_apps(config: dict[str, Any], allowed_services: list[str]) -> None:
    if not isinstance(config["managed_apps"], list):
        raise ConfigError("managed_apps must be a list")
    managed_names: set[str] = set()
    for app in config["managed_apps"]:
        if not isinstance(app, dict):
            raise ConfigError("each managed app must be an object")
        name = app.get("name")
        command = app.get("command")
        working_directory = app.get("cwd")
        if (
            not isinstance(name, str)
            or not name
            or any(character not in VALID_SERVICE_NAME_CHARACTERS for character in name)
        ):
            raise ConfigError("managed app names may contain only letters, numbers, dots, dashes, and underscores")
        if name in managed_names or name in allowed_services:
            raise ConfigError(f"duplicate service or managed app name: {name}")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            raise ConfigError(f"managed app '{name}' command must be a non-empty list of strings")
        if not isinstance(working_directory, str) or not working_directory:
            raise ConfigError(f"managed app '{name}' cwd must be a path string")
        for optional_path in ("env_file", "log_file"):
            if optional_path in app and not isinstance(app[optional_path], str):
                raise ConfigError(f"managed app '{name}' {optional_path} must be a path string")
        managed_names.add(name)


def _validate_config(config: dict[str, Any]) -> None:
    _validate_port(config)
    allowed_services = _validate_allowed_services(config)
    _validate_managed_apps(config, allowed_services)
    if not isinstance(config["cors_origins"], list) or not all(
        isinstance(origin, str) for origin in config["cors_origins"]
    ):
        raise ConfigError("cors_origins must be a list of strings")
    if config["token"] is not None and not isinstance(config["token"], str):
        raise ConfigError("token must be a string or null")


def load_config(*, announce_token: bool = True) -> dict:
    config = _read_config_file(CONFIG_PATH)
    _validate_config(config)

    if not config["token"]:
        config["token"] = _generate_token()
        save_config(config)
        if announce_token:
            print(f"Generated new agent token. Enter this into the client app:\n{config['token']}")

    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")
    if os.name != "nt":
        os.chmod(CONFIG_PATH, 0o600)
