import platform
import subprocess
import time
from pathlib import Path

import psutil

try:
    from . import managed_apps as app_manager
except ImportError:  # Support running this file directly.
    import managed_apps as app_manager

VALID_ACTIONS = {"start", "stop", "restart"}


class ServiceError(Exception):
    pass


def backend_name() -> str:
    return "windows" if platform.system() == "Windows" else "systemd"


def _run_service_command(executable: str, args: list[str], fallback_error: str) -> str:
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise ServiceError(str(exc)) from exc

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or fallback_error
        raise ServiceError(message)
    return result.stdout


def _run_systemctl(args: list[str]) -> str:
    return _run_service_command(
        "systemctl",
        ["--no-pager", *args],
        f"systemctl {' '.join(args)} failed",
    )


def _run_sc(args: list[str]) -> str:
    return _run_service_command("sc.exe", args, f"sc.exe {' '.join(args)} failed")


def _get_systemd_service_status(name: str) -> dict:
    output = _run_systemctl([
        "show", name,
        "--property=ActiveState,SubState,UnitFileState,Description",
    ])
    props = {}
    for line in output.strip().splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            props[key] = value

    return {
        "name": name,
        "active_state": props.get("ActiveState", "unknown"),
        "sub_state": props.get("SubState", "unknown"),
        "enabled": props.get("UnitFileState", "unknown"),
        "description": props.get("Description", ""),
    }


def _get_windows_service_status(name: str) -> dict:
    try:
        service = psutil.win_service_get(name)
        details = service.as_dict()
    except (psutil.Error, OSError) as exc:
        raise ServiceError(f"could not query Windows service '{name}': {exc}") from exc

    status = str(details.get("status", "unknown"))
    active_state, sub_state = _translate_windows_status(status)

    return {
        "name": name,
        "active_state": active_state,
        "sub_state": sub_state,
        "enabled": str(details.get("start_type", "unknown")),
        "description": str(details.get("display_name") or details.get("description") or ""),
    }


def _translate_windows_status(status: str) -> tuple[str, str]:
    if status == "running":
        return "active", "running"
    if status == "stopped":
        return "inactive", "stopped"
    if status in {"start_pending", "continue_pending"}:
        return "activating", status
    if status in {"stop_pending", "pause_pending", "paused"}:
        return "deactivating", status
    return "unknown", status


def get_service_status(name: str) -> dict:
    if backend_name() == "windows":
        return _get_windows_service_status(name)
    return _get_systemd_service_status(name)


def _runtime_directory(runtime_dir: str | Path | None) -> Path:
    if runtime_dir:
        return Path(runtime_dir)
    return Path(__file__).resolve().parent / "data" / "runtime"


def _unavailable_status(name: str, description: str, *, managed: bool = False) -> dict:
    status = {
        "name": name,
        "active_state": "error",
        "sub_state": "unavailable",
        "enabled": "managed" if managed else "unknown",
        "description": description,
    }
    if managed:
        status["kind"] = "managed_app"
    return status


def list_services(
    allowed_services: list[str],
    managed_apps: list[dict] | None = None,
    runtime_dir: str | Path | None = None,
) -> list[dict]:
    service_statuses = []
    for name in allowed_services:
        try:
            service_statuses.append(get_service_status(name))
        except ServiceError as exc:
            service_statuses.append(_unavailable_status(name, str(exc)))

    state_dir = _runtime_directory(runtime_dir)
    for app_config in managed_apps or []:
        if not app_manager.has_manageable_target(app_config, state_dir):
            continue
        try:
            service_statuses.append(app_manager.get_status(app_config, state_dir))
        except app_manager.ManagedAppError as exc:
            service_statuses.append(_unavailable_status(app_config["name"], str(exc), managed=True))
    return service_statuses


def _find_managed_app(name: str, managed_apps: list[dict] | None) -> dict:
    managed_app = next(
        (app_config for app_config in managed_apps or [] if app_config["name"] == name),
        None,
    )
    if managed_app is None:
        raise ServiceError(f"'{name}' is not a Homebru-managed server")
    return managed_app


def get_service_logs(
    name: str,
    managed_apps: list[dict] | None,
    runtime_dir: str | Path | None = None,
    line_count: int = 200,
) -> dict:
    managed_app = _find_managed_app(name, managed_apps)
    state_dir = _runtime_directory(runtime_dir)
    try:
        return {
            "name": name,
            "content": app_manager.read_log_tail(managed_app, line_count),
            "console_available": app_manager.console_input_available(managed_app, state_dir),
        }
    except app_manager.ManagedAppError as exc:
        raise ServiceError(str(exc)) from exc


def send_console_command(
    name: str,
    command: str,
    managed_apps: list[dict] | None,
    runtime_dir: str | Path | None = None,
) -> dict:
    managed_app = _find_managed_app(name, managed_apps)
    try:
        app_manager.send_console_command(
            managed_app,
            command,
            _runtime_directory(runtime_dir),
        )
    except app_manager.ManagedAppError as exc:
        raise ServiceError(str(exc)) from exc
    return {"name": name, "sent": True}


def control_service(
    name: str,
    action: str,
    allowed_services: list[str],
    managed_apps: list[dict] | None = None,
    runtime_dir: str | Path | None = None,
) -> dict:
    if action not in VALID_ACTIONS:
        raise ServiceError(f"invalid action '{action}'")

    managed_app = next((app_config for app_config in managed_apps or [] if app_config["name"] == name), None)
    if managed_app:
        try:
            return app_manager.control(managed_app, action, _runtime_directory(runtime_dir))
        except app_manager.ManagedAppError as exc:
            raise ServiceError(str(exc)) from exc

    if name not in allowed_services:
        raise ServiceError(f"'{name}' is not in the allowed services or managed apps list")

    if backend_name() == "windows":
        _control_windows_service(name, action)
    else:
        _run_systemctl([action, name])
    return get_service_status(name)


def _control_windows_service(name: str, action: str) -> None:
    try:
        service = psutil.win_service_get(name)
        current = service.status()
        if action == "start":
            if current == "running":
                return
            _run_sc(["start", name])
        elif action == "stop":
            if current == "stopped":
                return
            _run_sc(["stop", name])
        else:
            if current != "stopped":
                _run_sc(["stop", name])
                _wait_for_windows_status(service, "stopped")
            _run_sc(["start", name])

        # Windows service transitions are asynchronous. Wait briefly so the
        # response normally reflects the state the user requested.
        desired = "stopped" if action == "stop" else "running"
        _wait_for_windows_status(service, desired)
    except (psutil.Error, OSError) as exc:
        raise ServiceError(f"could not {action} Windows service '{name}': {exc}") from exc


def _wait_for_windows_status(service, desired: str) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if service.status() == desired:
            return
        time.sleep(0.2)
    raise ServiceError(f"timed out waiting for Windows service to become {desired}")
