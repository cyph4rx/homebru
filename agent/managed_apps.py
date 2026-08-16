from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import psutil


class ManagedAppError(RuntimeError):
    pass


_LAUNCHED_PROCESSES: dict[str, subprocess.Popen] = {}


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
    }


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
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
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
    log_path = Path(app.get("log_file") or working_directory / "homebrew.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    process = _launch_managed_process(app, working_directory, environment, log_path)
    _save_process_state(app, runtime_dir, process)
    _LAUNCHED_PROCESSES[app["name"]] = process


def _discard_finished_process_handle(name: str) -> None:
    launched_process = _LAUNCHED_PROCESSES.pop(name, None)
    if launched_process and launched_process.poll() is not None:
        launched_process.wait()


def _wait_for_launched_process(name: str) -> None:
    launched_process = _LAUNCHED_PROCESSES.pop(name, None)
    if not launched_process:
        return
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
