from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from . import __version__
from .config import ConfigError, ServerConfig, default_config_path, load_config
from .tui import HomebruApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebru",
        description="Manage your own Windows or Linux server from a terminal-native interface.",
    )
    parser.add_argument("--host", help="agent hostname or IP address")
    parser.add_argument("--port", type=int, help="agent port (default: 8420)")
    parser.add_argument("--token", help="agent authentication token")
    parser.add_argument("--https", action="store_true", help="connect using HTTPS")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="connection config path")
    parser.add_argument("--no-save", action="store_true", help="do not save connection changes")
    agent_mode = parser.add_mutually_exclusive_group()
    agent_mode.add_argument("--agent", action="store_true", help="run the Homebru server agent")
    agent_mode.add_argument(
        "--show-agent-token",
        action="store_true",
        help="print the local agent token and exit",
    )
    agent_mode.add_argument(
        "--show-agent-config",
        action="store_true",
        help="print the local agent configuration path and exit",
    )
    parser.add_argument("--version", action="version", version=f"Homebru {__version__}")
    return parser


def _run_bundled_script() -> bool:
    if not getattr(sys, "frozen", False) or sys.argv[1:2] != ["--run-bundled-script"]:
        return False
    if len(sys.argv) < 3:
        raise SystemExit("homebru: bundled script path is required")
    script_path = Path(sys.argv[2]).resolve()
    sys.argv = [str(script_path), *sys.argv[3:]]
    runpy.run_path(str(script_path), run_name="__main__")
    return True


def _run_agent_mode(args: argparse.Namespace) -> bool:
    if args.show_agent_token:
        from agent.config import load_config

        print(load_config(announce_token=False)["token"])
        return True
    if args.show_agent_config:
        from agent.config import CONFIG_PATH

        print(CONFIG_PATH)
        return True
    if args.agent:
        from agent.main import run

        sys.argv = [sys.argv[0]]
        run()
        return True
    return False


def resolve_config(args: argparse.Namespace) -> ServerConfig | None:
    saved_config = load_config(args.config)
    if not any((args.host, args.port, args.token, args.https)):
        return saved_config
    if not args.host and not saved_config:
        raise ConfigError("--host is required when no saved connection exists")
    if not args.token and not saved_config:
        raise ConfigError("--token is required when no saved connection exists")
    return ServerConfig(
        host=args.host or saved_config.host,
        port=args.port or saved_config.port,
        token=args.token or saved_config.token,
        scheme="https" if args.https else (saved_config.scheme if saved_config else "http"),
        refresh_interval=saved_config.refresh_interval if saved_config else 2.0,
        request_timeout=saved_config.request_timeout if saved_config else 5.0,
    )


def main() -> None:
    if _run_bundled_script():
        return
    parser = build_parser()
    args = parser.parse_args()
    if _run_agent_mode(args):
        return
    try:
        config = resolve_config(args)
    except ConfigError as exc:
        parser.error(str(exc))
        return
    try:
        HomebruApp(config, args.config, save_connection=not args.no_save).run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # keep terminal startup failures concise
        print(f"homebru: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
