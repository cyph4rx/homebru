#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path


MINIMUM_PYTHON = (3, 10)
PROJECT_ROOT = Path(__file__).resolve().parent


def _installer_environment() -> Path:
    if os.name == "nt":
        data_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_root / "homebru" / "installer" / "pipx"


def _environment_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run_command(*parts: str | Path, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    command = [str(part) for part in parts]
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def _ensure_pipx() -> Path:
    environment = _installer_environment()
    python = _environment_python(environment)
    if not python.is_file():
        print(f"Creating installer environment: {environment}")
        venv.EnvBuilder(with_pip=True).create(environment)

    check = subprocess.run(
        [str(python), "-m", "pipx", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if check.returncode != 0:
        print("Installing the isolated command installer...")
        _run_command(python, "-m", "pip", "install", "pipx")
    return python


def _pipx_bin_directory(pipx_python: Path) -> Path:
    result = _run_command(
        pipx_python,
        "-m",
        "pipx",
        "environment",
        "--value",
        "PIPX_BIN_DIR",
        capture_output=True,
    )
    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("pipx did not report its command directory")
    return Path(output_lines[-1])


def install() -> None:
    pipx_python = _ensure_pipx()
    _run_command(pipx_python, "-m", "pipx", "ensurepath")
    _run_command(
        pipx_python,
        "-m",
        "pipx",
        "install",
        "--force",
        "--editable",
        PROJECT_ROOT,
    )

    command_name = "homebru.exe" if os.name == "nt" else "homebru"
    homebru_command = _pipx_bin_directory(pipx_python) / command_name
    if not homebru_command.is_file():
        raise RuntimeError(f"the Homebru command was not created at {homebru_command}")
    _run_command(homebru_command, "--version")

    print("\nHomebru is installed.")
    print("Close and reopen your terminal once, then run: homebru")


def uninstall() -> None:
    pipx_python = _ensure_pipx()
    _run_command(pipx_python, "-m", "pipx", "uninstall", "homebru")
    print("Homebru was removed from your command line.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the Homebru command for the current user")
    parser.add_argument("--uninstall", action="store_true", help="remove the global Homebru command")
    args = parser.parse_args()

    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(map(str, MINIMUM_PYTHON))
        current = ".".join(map(str, sys.version_info[:3]))
        parser.error(f"Homebru requires Python {required} or newer; found {current}")

    try:
        uninstall() if args.uninstall else install()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Homebru installation failed: {exc}\n")


if __name__ == "__main__":
    main()
