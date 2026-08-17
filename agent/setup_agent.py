from __future__ import annotations

import argparse
import getpass
import os
import re
import shlex
import subprocess
import sys
import venv
from pathlib import Path

try:
    from . import config as agent_config
except ImportError:  # Support running this file directly.
    import config as agent_config


AGENT_DIR = Path(__file__).resolve().parent
TEMPLATE_ROOT = AGENT_DIR / "templates"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-.").lower()
    if not slug:
        raise ValueError("server name must contain a letter or number")
    return slug


def venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _python_script_command(interpreter: Path, script: Path, *arguments: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-bundled-script", str(script), *arguments]
    return [str(interpreter), str(script), *arguments]


def install_requirements(environment: Path, requirements: Path, *, quiet: bool = False) -> None:
    if not venv_python(environment).exists():
        print(f"Creating virtual environment: {environment}")
        venv.EnvBuilder(with_pip=True).create(environment)
    print(f"Installing: {requirements}")
    result = subprocess.run(
        [str(venv_python(environment)), "-m", "pip", "install", "-r", str(requirements)],
        capture_output=quiet,
        text=quiet,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "pip install failed").strip()
        raise RuntimeError(detail[-2000:])


def _validate_template_destination(project_dir: Path, marker: Path, template_name: str) -> None:
    if not project_dir.exists():
        return
    existing_files = [item for item in project_dir.iterdir() if item.name != ".gitkeep"]
    if existing_files and not marker.exists():
        raise FileExistsError(f"folder is not empty and was not created by Homebru: {project_dir}")
    if marker.exists() and marker.read_text(encoding="utf-8").strip() != template_name:
        raise FileExistsError(f"folder belongs to a different Homebru template: {project_dir}")


def _render_template(content: str, replacements: dict[str, str]) -> str:
    for placeholder, replacement in replacements.items():
        content = content.replace(placeholder, replacement)
    return content


def _copy_template_files(source_root: Path, project_dir: Path, replacements: dict[str, str]) -> None:
    for source_file in source_root.rglob("*"):
        if not source_file.is_file() or "__pycache__" in source_file.parts:
            continue
        destination = project_dir / source_file.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            continue
        content = source_file.read_text(encoding="utf-8")
        destination.write_text(_render_template(content, replacements), encoding="utf-8")


def _prepare_template(
    template_name: str,
    project_dir: Path,
    replacements: dict[str, str],
) -> Path:
    project_dir = project_dir.resolve()
    marker = project_dir / ".homebrew-template"
    _validate_template_destination(project_dir, marker, template_name)
    project_dir.mkdir(parents=True, exist_ok=True)

    source_root = TEMPLATE_ROOT / template_name.replace("-", "_")
    if not source_root.is_dir():
        raise ValueError(f"unknown server template: {template_name}")
    _copy_template_files(source_root, project_dir, replacements)
    marker.write_text(f"{template_name}\n", encoding="utf-8")
    return project_dir


def _managed_app_config(
    name: str,
    project_dir: Path,
    command: list[str],
    description: str,
    *,
    environment_file: Path | None = None,
) -> dict:
    app_config = {
        "name": name,
        "command": command,
        "cwd": str(project_dir),
        "log_file": str(project_dir / "homebrew.log"),
        "description": description,
    }
    if environment_file:
        app_config["env_file"] = str(environment_file)
    return app_config


def _validate_port(port: int) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("server port must be between 1 and 65535")


def _write_private_value(path: Path, key: str, value: str) -> None:
    path.write_text(f"{key}={value}\n", encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def create_discord_bot(name: str, project_dir: Path, discord_token: str, install: bool) -> dict:
    name = slugify(name)
    project_dir = _prepare_template("discord-bot", project_dir, {"{{BOT_NAME}}": name})

    token_value = discord_token.strip() or "paste-your-discord-token-here"
    env_path = project_dir / ".env"
    if discord_token.strip() or not env_path.exists():
        _write_private_value(env_path, "DISCORD_TOKEN", token_value)
    elif os.name != "nt":
        env_path.chmod(0o600)

    bot_environment = project_dir / ".venv"
    if install:
        install_requirements(bot_environment, project_dir / "requirements.txt")

    return _managed_app_config(
        name,
        project_dir,
        _python_script_command(venv_python(bot_environment), project_dir / "bot.py"),
        f"Discord bot ({name})",
        environment_file=env_path,
    )


def create_minecraft_server(name: str, project_dir: Path, memory_mb: int = 2048) -> dict:
    name = slugify(name)
    if not 512 <= memory_mb <= 65536:
        raise ValueError("Minecraft memory must be between 512 and 65536 MB")
    project_dir = _prepare_template("minecraft-java", project_dir, {"{{SERVER_NAME}}": name})
    return _managed_app_config(
        name,
        project_dir,
        ["java", f"-Xms{memory_mb}M", f"-Xmx{memory_mb}M", "-jar", "server.jar", "nogui"],
        f"Minecraft Java server ({name})",
    )


def create_python_http_server(name: str, project_dir: Path, port: int = 8000) -> dict:
    name = slugify(name)
    _validate_port(port)
    project_dir = _prepare_template("python-http", project_dir, {"{{SERVER_NAME}}": name, "{{PORT}}": str(port)})
    return _managed_app_config(
        name,
        project_dir,
        _python_script_command(
            venv_python(AGENT_DIR / ".venv"),
            project_dir / "server.py",
            "--port",
            str(port),
        ),
        f"Python web server ({name})",
    )


def create_node_http_server(name: str, project_dir: Path, port: int = 3000) -> dict:
    name = slugify(name)
    _validate_port(port)
    project_dir = _prepare_template("node-http", project_dir, {"{{SERVER_NAME}}": name, "{{PORT}}": str(port)})
    env_path = project_dir / ".env"
    if not env_path.exists():
        _write_private_value(env_path, "PORT", str(port))
    return _managed_app_config(
        name,
        project_dir,
        ["node", str(project_dir / "server.js")],
        f"Node.js web server ({name})",
        environment_file=env_path,
    )


def create_custom_server(name: str, project_dir: Path, command: str, description: str = "") -> dict:
    name = slugify(name)
    project_dir = project_dir.expanduser().resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    try:
        command_parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"invalid start command: {exc}") from exc
    if not command_parts:
        raise ValueError("start command is required")
    return _managed_app_config(
        name,
        project_dir,
        command_parts,
        description.strip() or f"Custom server ({name})",
    )


def register_app(app_config: dict) -> dict:
    config = agent_config.load_config(announce_token=False)
    app_name = app_config["name"]
    if app_name in config["allowed_services"]:
        raise ValueError(f"'{app_name}' is already registered as an operating-system service")
    config["managed_apps"] = [item for item in config["managed_apps"] if item["name"] != app_name]
    config["managed_apps"].append(app_config)
    agent_config.save_config(config)
    return config


def _prompt_with_default(default: str, label: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up the Homebru agent and a server template")
    parser.add_argument("template", nargs="?", default="discord-bot", choices=["discord-bot"])
    parser.add_argument("--name", help="name shown in Homebru")
    parser.add_argument("--directory", type=Path, help="folder for the new server")
    parser.add_argument("--discord-token", help="Discord token; prompting is safer")
    parser.add_argument("--skip-install", action="store_true", help="create files without installing dependencies")
    parser.add_argument("--non-interactive", action="store_true", help="use defaults and do not prompt")
    return parser


def _collect_setup_values(args: argparse.Namespace) -> tuple[str, Path, str]:
    name = args.name or (
        "discord-bot" if args.non_interactive else _prompt_with_default("discord-bot", "Server name")
    )
    default_directory = AGENT_DIR / "servers" / slugify(name)
    project_dir = args.directory or (
        default_directory
        if args.non_interactive
        else Path(_prompt_with_default(str(default_directory), "Server folder"))
    )
    discord_token = args.discord_token
    if discord_token is None and not args.non_interactive:
        discord_token = getpass.getpass("Discord bot token (leave blank to add it later): ")
    return name, project_dir, discord_token or ""


def _print_setup_result(
    args: argparse.Namespace,
    app_config: dict,
    config: dict,
    discord_token: str,
) -> None:
    project_dir = Path(app_config["cwd"])
    print("\nSetup complete.")
    print(f"Server: {app_config['name']}")
    print(f"Files:  {app_config['cwd']}")
    print(f"Config: {agent_config.CONFIG_PATH}")
    print(f"Token:  {config['token']}")
    if args.skip_install:
        agent_python = venv_python(AGENT_DIR / ".venv")
        bot_python = venv_python(project_dir / ".venv")
        print("\nInstall dependencies:")
        print(f'  "{sys.executable}" -m venv "{AGENT_DIR / ".venv"}"')
        print(f'  "{agent_python}" -m pip install -r "{AGENT_DIR / "requirements.txt"}"')
        print(f'  "{sys.executable}" -m venv "{project_dir / ".venv"}"')
        print(f'  "{bot_python}" -m pip install -r "{project_dir / "requirements.txt"}"')
    print("\nStart the agent:")
    print(f'  "{sys.executable}" "{AGENT_DIR / "run_agent.py"}"')
    print("\nThen open the Homebru terminal client and use the token shown above.")
    if not discord_token.strip():
        print(f'Before starting the bot, put its Discord token in "{project_dir / ".env"}".')


def main() -> None:
    if sys.version_info < (3, 10):
        print("Homebru requires Python 3.10 or newer.", file=sys.stderr)
        raise SystemExit(1)
    args = build_parser().parse_args()
    print("Homebru setup\n")
    name, project_dir, discord_token = _collect_setup_values(args)

    try:
        app_config = create_discord_bot(name, project_dir, discord_token, install=not args.skip_install)
        config = register_app(app_config)
        if not args.skip_install:
            install_requirements(AGENT_DIR / ".venv", AGENT_DIR / "requirements.txt")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    _print_setup_result(args, app_config, config, discord_token)


if __name__ == "__main__":
    main()
