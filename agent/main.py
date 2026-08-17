import argparse
import asyncio
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from . import services, stats
    from .config import CONFIG_PATH, load_config
except ImportError:  # Support running this file directly.
    import services
    import stats
    from config import CONFIG_PATH, load_config

startup_config = load_config()
RUNTIME_DIR = CONFIG_PATH.parent / "runtime"

app = FastAPI(title="Home Server Agent")
if startup_config["cors_origins"]:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=startup_config["cors_origins"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization"],
    )


def _load_authorized_config(authorization: str | None) -> dict[str, Any]:
    current_config = load_config(announce_token=False)
    expected = f"Bearer {current_config['token']}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid or missing token")
    return current_config


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service_backend": services.backend_name()}


@app.get("/stats")
def read_stats(authorization: str | None = Header(default=None)) -> dict:
    _load_authorized_config(authorization)
    return stats.get_all_stats()


@app.get("/services")
def read_services(authorization: str | None = Header(default=None)) -> list[dict]:
    current_config = _load_authorized_config(authorization)
    return services.list_services(
        current_config["allowed_services"],
        current_config["managed_apps"],
        RUNTIME_DIR,
    )


@app.get("/services/{name}/logs")
def read_service_logs(
    name: str,
    lines: int = 200,
    authorization: str | None = Header(default=None),
) -> dict:
    current_config = _load_authorized_config(authorization)
    try:
        return services.get_service_logs(
            name,
            current_config["managed_apps"],
            RUNTIME_DIR,
            lines,
        )
    except services.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/services/{name}/console")
def write_service_console(
    name: str,
    payload: dict[str, Any],
    authorization: str | None = Header(default=None),
) -> dict:
    current_config = _load_authorized_config(authorization)
    command = payload.get("command")
    if not isinstance(command, str):
        raise HTTPException(status_code=400, detail="console command must be a string")
    try:
        return services.send_console_command(
            name,
            command,
            current_config["managed_apps"],
            RUNTIME_DIR,
        )
    except services.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/services/{name}/{action}")
def act_on_service(name: str, action: str, authorization: str | None = Header(default=None)) -> dict:
    current_config = _load_authorized_config(authorization)
    try:
        return services.control_service(
            name,
            action,
            current_config["allowed_services"],
            current_config["managed_apps"],
            RUNTIME_DIR,
        )
    except services.ServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/stats")
async def ws_stats(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if token != load_config(announce_token=False)["token"]:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    try:
        while True:
            await websocket.send_json(await asyncio.to_thread(stats.get_all_stats))
            await asyncio.sleep(2)
    except (WebSocketDisconnect, RuntimeError):
        pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Homebru server agent")
    parser.add_argument("--show-token", action="store_true", help="print the configured agent token and exit")
    parser.add_argument("--show-config", action="store_true", help="print the agent config path and exit")
    return parser


def run() -> None:
    import uvicorn

    args = _build_parser().parse_args()
    if args.show_token:
        print(startup_config["token"])
        return
    if args.show_config:
        print(CONFIG_PATH)
        return
    uvicorn.run(app, host="0.0.0.0", port=startup_config["port"])


if __name__ == "__main__":
    run()
