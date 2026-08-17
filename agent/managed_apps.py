from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import psutil

try:
    from .processes import hidden_window_creation_flags
except ImportError:  # Support running this file directly.
    from processes import hidden_window_creation_flags


class ManagedAppError(RuntimeError):
    pass


_LAUNCHED_PROCESSES: dict[str, subprocess.Popen] = {}
MAX_LOG_READ_BYTES = 256 * 1024
MAX_LOG_LINES = 1000


def _state_path(app: dict, runtime_dir: Path) -> Path:
    return runtime_dir / f"{app['name']}.json"


def _read_environment_file(path: str | None) -> dict[str, str]:
    environment: dict[str, str] = {}
    if not path:
        return environment
    env_path = Path(path)
    if not env_path.exists():
        raise ManagedAppError(f"environment file does not exist: {env_path}")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        environment[key.strip()] = value.strip().strip('"').strip("'")
    return environment


def _find_running_process(app_config: dict, runtime_dir: Path) -> psutil.Process | None:
    state_path = _state_path(app_config, runtime_dir)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        process = psutil.Process(int(state["pid"]))
        if abs(process.create_time() - float(state["created_at"])) > 1:
            return None
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return None
        return process
    except (OSError, ValueError, KeyError, json.JSONDecodeError, psutil.Error):
        return None


def get_status(app: dict, runtime_dir: Path) -> dict:
    process = _find_running_process(app, runtime_dir)
    state_path = _state_path(app, runtime_dir)
    if process is None:
        state_path.unlink(missing_ok=True)
        active_state, sub_state = "inactive", "stopped"
    else:
        active_state, sub_state = "active", "running"
    return {
        "name": app["name"],
        "active_state": active_state,
        "sub_state": sub_state,
        "enabled": "managed",
        "description": app.get("description", "Managed application"),
        "kind": "managed_app",
        "console_available": console_input_available(app, runtime_dir),
    }


def has_manageable_target(app: dict, runtime_dir: Path) -> bool:
    """Return whether the app still has files or a tracked running process."""
    if Path(app["cwd"]).is_dir():
        return True
    return _find_running_process(app, runtime_dir) is not None


def _launch_managed_process(
    app: dict,
    working_directory: Path,
    environment: dict[str, str],
    log_path: Path,
) -> subprocess.Popen:
    try:
        with log_path.open("ab") as log:
            return subprocess.Popen(
                app["command"],
                cwd=working_directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=hidden_window_creation_flags(new_process_group=True),
            )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManagedAppError(f"could not start {app['name']}: {exc}") from exc


def _save_process_state(app: dict, runtime_dir: Path, process: subprocess.Popen) -> None:
    created_at = psutil.Process(process.pid).create_time()
    try:
        _state_path(app, runtime_dir).write_text(
            json.dumps({"pid": process.pid, "created_at": created_at}) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        process.terminate()
        process.wait(timeout=3)
        raise ManagedAppError(f"could not save runtime state for {app['name']}: {exc}") from exc


def start(app: dict, runtime_dir: Path) -> None:
    if _find_running_process(app, runtime_dir) is not None:
        return
    working_directory = Path(app["cwd"])
    if not working_directory.is_dir():
        raise ManagedAppError(f"working directory does not exist: {working_directory}")
    command = app["command"]
    executable = Path(command[0])
    if executable.is_absolute() and not executable.exists():
        raise ManagedAppError(f"executable does not exist: {executable}")

    environment = os.environ.copy()
    environment.update(_read_environment_file(app.get("env_file")))
    if getattr(sys, "frozen", False) and Path(command[0]).resolve() == Path(sys.executable).resolve():
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    log_path = Path(app.get("log_file") or working_directory / "homebrew.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    process = _launch_managed_process(app, working_directory, environment, log_path)
    _save_process_state(app, runtime_dir, process)
    _LAUNCHED_PROCESSES[app["name"]] = process


def _discard_finished_process_handle(name: str) -> None:
    launched_process = _LAUNCHED_PROCESSES.pop(name, None)
    if launched_process and launched_process.poll() is not None:
        if launched_process.stdin:
            launched_process.stdin.close()
        launched_process.wait()


def _wait_for_launched_process(name: str) -> None:
    launched_process = _LAUNCHED_PROCESSES.pop(name, None)
    if not launched_process:
        return
    if launched_process.stdin:
        launched_process.stdin.close()
    try:
        launched_process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def _terminate_process_tree(process: psutil.Process) -> None:
    process_tree = process.children(recursive=True) + [process]
    for child_process in process_tree:
        child_process.terminate()
    _, still_running = psutil.wait_procs(process_tree, timeout=5)
    for child_process in still_running:
        child_process.kill()
    if still_running:
        psutil.wait_procs(still_running, timeout=3)


def stop(app: dict, runtime_dir: Path) -> None:
    process = _find_running_process(app, runtime_dir)
    if process is None:
        _state_path(app, runtime_dir).unlink(missing_ok=True)
        _discard_finished_process_handle(app["name"])
        return
    try:
        _terminate_process_tree(process)
    except psutil.NoSuchProcess:
        pass
    except (psutil.AccessDenied, psutil.TimeoutExpired) as exc:
        raise ManagedAppError(f"could not stop {app['name']}: {exc}") from exc
    finally:
        _state_path(app, runtime_dir).unlink(missing_ok=True)
        _wait_for_launched_process(app["name"])


def _active_process_handle(app: dict, runtime_dir: Path) -> subprocess.Popen | None:
    process = _find_running_process(app, runtime_dir)
    launched_process = _LAUNCHED_PROCESSES.get(app["name"])
    if (
        process is None
        or launched_process is None
        or launched_process.pid != process.pid
        or launched_process.poll() is not None
    ):
        return None
    return launched_process


def console_input_available(app: dict, runtime_dir: Path) -> bool:
    process = _active_process_handle(app, runtime_dir)
    return process is not None and process.stdin is not None


def send_console_command(app: dict, command: str, runtime_dir: Path) -> None:
    command = command.rstrip("\r\n")
    if not command:
        raise ManagedAppError("console command cannot be empty")
    if "\n" in command or "\r" in command:
        raise ManagedAppError("console commands must be a single line")
    if len(command) > 4096:
        raise ManagedAppError("console command is too long")

    if _find_running_process(app, runtime_dir) is None:
        raise ManagedAppError(f"{app['name']} is not running")
    process = _active_process_handle(app, runtime_dir)
    if process is None or process.stdin is None:
        raise ManagedAppError(
            "console input is unavailable; restart this server from Homebru and try again"
        )
    try:
        process.stdin.write((command + "\n").encode("utf-8"))
        process.stdin.flush()
    except (BrokenPipeError, OSError) as exc:
        raise ManagedAppError(f"could not send console input to {app['name']}: {exc}") from exc


def read_log_tail(app: dict, line_count: int = 200) -> str:
    if not 1 <= line_count <= MAX_LOG_LINES:
        raise ManagedAppError(f"log line count must be between 1 and {MAX_LOG_LINES}")

    working_directory = Path(app["cwd"])
    log_path = Path(app.get("log_file") or working_directory / "homebrew.log")
    if not log_path.exists():
        return ""
    try:
        with log_path.open("rb") as log_file:
            log_file.seek(0, os.SEEK_END)
            file_size = log_file.tell()
            log_file.seek(max(file_size - MAX_LOG_READ_BYTES, 0))
            content = log_file.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise ManagedAppError(f"could not read the log for {app['name']}: {exc}") from exc
    return "\n".join(content.splitlines()[-line_count:])


def control(app: dict, action: str, runtime_dir: Path) -> dict:
    if action == "start":
        start(app, runtime_dir)
    elif action == "stop":
        stop(app, runtime_dir)
    elif action == "restart":
        stop(app, runtime_dir)
        start(app, runtime_dir)
    else:
        raise ManagedAppError(f"invalid action '{action}'")
    return get_status(app, runtime_dir)
