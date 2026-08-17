from __future__ import annotations

from typing import Any, Literal
from urllib.parse import quote

import httpx

from .config import ServerConfig

ServiceAction = Literal["start", "stop", "restart"]


class AgentError(RuntimeError):
    """A friendly error returned when the server agent cannot complete a request."""


class AgentClient:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={"Authorization": f"Bearer {config.token}"},
            timeout=config.request_timeout,
        )

    async def __aenter__(self) -> "AgentClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, json_body: Any = None) -> Any:
        try:
            response = await self._client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise AgentError(f"{self.config.host} did not respond in time") from exc
        except httpx.RequestError as exc:
            raise AgentError(f"cannot reach {self.config.base_url}: {exc}") from exc

        if response.is_success:
            try:
                return response.json()
            except ValueError as exc:
                raise AgentError("the agent returned an invalid response") from exc

        detail = None
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail")
        except ValueError:
            pass
        if response.status_code == 401:
            detail = "authentication failed; check the server token"
        raise AgentError(str(detail or f"agent request failed ({response.status_code})"))

    async def get_stats(self) -> dict[str, Any]:
        result = await self._request("GET", "/stats")
        if not isinstance(result, dict):
            raise AgentError("the agent returned malformed statistics")
        return result

    async def get_services(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/services")
        if not isinstance(result, list):
            raise AgentError("the agent returned a malformed service list")
        return result

    async def control_service(self, name: str, action: ServiceAction) -> dict[str, Any]:
        encoded_name = quote(name, safe="")
        result = await self._request("POST", f"/services/{encoded_name}/{action}")
        if not isinstance(result, dict):
            raise AgentError("the agent returned a malformed service status")
        return result

    async def get_service_logs(self, name: str, line_count: int = 200) -> dict[str, Any]:
        encoded_name = quote(name, safe="")
        result = await self._request(
            "GET",
            f"/services/{encoded_name}/logs?lines={line_count}",
        )
        if not isinstance(result, dict) or not isinstance(result.get("content"), str):
            raise AgentError("the agent returned malformed server logs")
        return result

    async def send_console_command(self, name: str, command: str) -> None:
        encoded_name = quote(name, safe="")
        result = await self._request(
            "POST",
            f"/services/{encoded_name}/console",
            json_body={"command": command},
        )
        if not isinstance(result, dict) or result.get("sent") is not True:
            raise AgentError("the agent did not accept the console command")
