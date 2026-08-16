from __future__ import annotations

import argparse
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
    parser.add_argument("--version", action="version", version=f"Homebru {__version__}")
    return parser


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
    parser = build_parser()
    args = parser.parse_args()
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
