from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from agent import setup_agent

from .config import ServerConfig


@dataclass(slots=True)
class LocalSetupResult:
    connection: ServerConfig
    server_name: str
    project_dir: Path
    next_step: str = ""


_AGENT_PROCESS: subprocess.Popen | None = None
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
AGENT_START_TIMEOUT_SECONDS = 15
AGENT_PROBE_INTERVAL_SECONDS = 0.25


def default_server_directory(name: str = "discord-bot") -> Path:
    return setup_agent.AGENT_DIR / "servers" / setup_agent.slugify(name)


def _probe_local_agent(port: int, token: str) -> int | None:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/services",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=1) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except OSError:
        return None


def _launch_agent_process() -> tuple[subprocess.Popen, Path]:
    agent_python = setup_agent.venv_python(setup_agent.AGENT_DIR / ".venv")
    log_path = setup_agent.AGENT_DIR / "data" / "agent.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creation_flags = (
        subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        if os.name == "nt"
        else 0
    )
    with log_path.open("ab") as log:
        process = subprocess.Popen(
            [str(agent_python), str(setup_agent.AGENT_DIR / "main.py")],
            cwd=setup_agent.AGENT_DIR,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=os.name != "nt",
            creationflags=creation_flags,
        )
    return process, log_path


def _wait_for_agent(process: subprocess.Popen, log_path: Path, port: int, token: str) -> None:
    deadline = time.monotonic() + AGENT_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
            raise RuntimeError(f"the local agent stopped during startup: {detail.strip()}")
        if _probe_local_agent(port, token) == 200:
            return
        time.sleep(AGENT_PROBE_INTERVAL_SECONDS)
    raise RuntimeError(f"the local agent did not start on port {port}")


def _start_agent(port: int, token: str) -> None:
    global _AGENT_PROCESS
    status = _probe_local_agent(port, token)
    if status == 200:
        return
    if status is not None:
        raise RuntimeError(f"port {port} is already used by another server")

    _AGENT_PROCESS, log_path = _launch_agent_process()
    _wait_for_agent(_AGENT_PROCESS, log_path, port, token)


def ensure_local_agent(config: ServerConfig) -> None:
    if config.host.lower() not in LOCAL_HOSTS:
        return
    _start_agent(config.port, config.token)


def _register_app_and_start_agent(app_config: dict, next_step: str = "") -> LocalSetupResult:
    setup_agent.install_requirements(
        setup_agent.AGENT_DIR / ".venv",
        setup_agent.AGENT_DIR / "requirements.txt",
        quiet=True,
    )
    agent_config = setup_agent.register_app(app_config)
    _start_agent(agent_config["port"], agent_config["token"])
    return LocalSetupResult(
        connection=ServerConfig(
            host="127.0.0.1",
            port=agent_config["port"],
            token=agent_config["token"],
        ),
        server_name=app_config["name"],
        project_dir=Path(app_config["cwd"]),
        next_step=next_step,
    )


def _parse_template_number(value: str, default: int, error_message: str) -> int:
    try:
        return int(value or default)
    except ValueError as exc:
        raise ValueError(error_message) from exc


def _create_discord_template(name: str, project_dir: Path, token: str) -> tuple[dict, str]:
    app_config = setup_agent.create_discord_bot(name, project_dir, token, install=False)
    setup_agent.install_requirements(
        Path(app_config["cwd"]) / ".venv",
        Path(app_config["cwd"]) / "requirements.txt",
        quiet=True,
    )
    next_step = "" if token.strip() else "Add the Discord token to .env before starting the bot."
    return app_config, next_step


def _create_minecraft_template(name: str, project_dir: Path, memory: str) -> tuple[dict, str]:
    memory_mb = _parse_template_number(memory, 2048, "Minecraft memory must be a number in MB")
    app_config = setup_agent.create_minecraft_server(name, project_dir, memory_mb)
    next_step = "Add server.jar and accept the EULA using the generated README.txt instructions."
    return app_config, next_step


def _create_python_template(name: str, project_dir: Path, port_text: str) -> tuple[dict, str]:
    port = _parse_template_number(port_text, 8000, "server port must be a number")
    app_config = setup_agent.create_python_http_server(name, project_dir, port)
    return app_config, f"Edit the public folder, then start the server on port {port}."


def _create_node_template(name: str, project_dir: Path, port_text: str) -> tuple[dict, str]:
    port = _parse_template_number(port_text, 3000, "server port must be a number")
    app_config = setup_agent.create_node_http_server(name, project_dir, port)
    return app_config, f"Make sure Node.js is installed, then start the server on port {port}."


def create_local_template_server(
    template_id: str,
    name: str,
    project_dir: Path,
    option: str = "",
) -> LocalSetupResult:
    if template_id == "discord-bot":
        app_config, next_step = _create_discord_template(name, project_dir, option)
    elif template_id == "minecraft-java":
        app_config, next_step = _create_minecraft_template(name, project_dir, option)
    elif template_id == "python-http":
        app_config, next_step = _create_python_template(name, project_dir, option)
    elif template_id == "node-http":
        app_config, next_step = _create_node_template(name, project_dir, option)
    else:
        raise ValueError(f"unknown server template: {template_id}")
    return _register_app_and_start_agent(app_config, next_step)


def create_local_custom_server(
    name: str,
    project_dir: Path,
    command: str,
    description: str,
) -> LocalSetupResult:
    app_config = setup_agent.create_custom_server(name, project_dir, command, description)
    return _register_app_and_start_agent(
        app_config,
        "The server is registered. Select it in the dashboard and choose Start.",
    )
