"""Standalone MCP client helpers for Agentic broker integrations."""

from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


class McpClientUnavailable(RuntimeError):
    """Raised when the optional MCP SDK is not available."""


class StreamableHttpMcpToolClient:
    """Synchronous wrapper around an MCP Streamable HTTP tool client.

    This class intentionally stays small. Authentication is handled by either a
    caller-provided bearer token or a file-backed OAuth flow.
    """

    def __init__(
        self,
        url: str,
        bearer_token: str | None = None,
        bearer_token_env_var: str | None = None,
        oauth_token_store_path: str | Path | None = None,
        oauth_callback_port: int = 8765,
        oauth_scope: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        if not url:
            raise ValueError("MCP url is required")
        self.url = url
        self.bearer_token = bearer_token
        self.bearer_token_env_var = bearer_token_env_var
        self.oauth_token_store_path = Path(oauth_token_store_path) if oauth_token_store_path else None
        self.oauth_callback_port = oauth_callback_port
        self.oauth_scope = oauth_scope
        self.headers = dict(headers or {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return a decoded Python payload."""

        return asyncio.run(self._call_tool_async(name, arguments))

    def list_tools(self) -> list[dict[str, Any]]:
        """List MCP tools exposed by the server."""

        return asyncio.run(self._list_tools_async())

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise McpClientUnavailable(
                "The optional 'mcp' package is required for Streamable HTTP MCP access. "
                "Install it with: python -m pip install 'mcp>=1.27,<2'"
            ) from exc

        auth = self._oauth_auth()
        headers = self._headers()
        async with streamablehttp_client(
            self.url,
            headers=headers,
            auth=auth,
            terminate_on_close=False,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return decode_mcp_tool_result(result)

    async def _list_tools_async(self) -> list[dict[str, Any]]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise McpClientUnavailable(
                "The optional 'mcp' package is required for Streamable HTTP MCP access. "
                "Install it with: python -m pip install 'mcp>=1.27,<2'"
            ) from exc

        auth = self._oauth_auth()
        headers = self._headers()
        async with streamablehttp_client(
            self.url,
            headers=headers,
            auth=auth,
            terminate_on_close=False,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return decode_mcp_tools_result(result)

    def _headers(self) -> dict[str, str]:
        headers = dict(self.headers)
        token = self._bearer_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _bearer_token(self) -> str | None:
        token = self.bearer_token
        if not token and self.bearer_token_env_var:
            token = os.environ.get(self.bearer_token_env_var)
        return token

    def _oauth_auth(self) -> Any:
        if self._bearer_token():
            return None
        if not self.oauth_token_store_path:
            return None

        try:
            from mcp.client.auth import OAuthClientProvider
            from mcp.shared.auth import OAuthClientMetadata
        except ImportError as exc:
            raise McpClientUnavailable(
                "The optional 'mcp' package is required for MCP OAuth. "
                "Install it with: python -m pip install 'mcp>=1.27,<2'"
            ) from exc

        callback = LocalOAuthCallback(self.oauth_callback_port)
        metadata = OAuthClientMetadata(
            redirect_uris=[callback.redirect_uri],
            token_endpoint_auth_method="none",
            scope=self.oauth_scope,
            client_name="robinhood-agentic-bot",
        )
        return OAuthClientProvider(
            self.url,
            metadata,
            JsonTokenStorage(self.oauth_token_store_path),
            redirect_handler=callback.redirect_handler,
            callback_handler=callback.callback_handler,
        )


class JsonTokenStorage:
    """File-backed MCP OAuth token storage."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def get_tokens(self):
        payload = self._read()
        tokens = payload.get("tokens")
        if not tokens:
            return None
        from mcp.shared.auth import OAuthToken

        return OAuthToken.model_validate(tokens)

    async def set_tokens(self, tokens) -> None:
        payload = self._read()
        payload["tokens"] = tokens.model_dump(mode="json")
        self._write(payload)

    async def get_client_info(self):
        payload = self._read()
        client_info = payload.get("client_info")
        if not client_info:
            return None
        from mcp.shared.auth import OAuthClientInformationFull

        return OAuthClientInformationFull.model_validate(client_info)

    async def set_client_info(self, client_info) -> None:
        payload = self._read()
        payload["client_info"] = client_info.model_dump(mode="json")
        self._write(payload)

    def has_tokens(self) -> bool:
        return bool(self._read().get("tokens"))

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class LocalOAuthCallback:
    """Local browser callback helper for OAuth authorization code flow."""

    port: int = 8765
    path: str = "/callback"

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port}{self.path}"

    async def redirect_handler(self, authorization_url: str) -> None:
        self._server = _OAuthCallbackServer(self.port, self.path)
        self._server.start()
        print(f"Open this URL to authorize Robinhood MCP access:\n{authorization_url}")
        webbrowser.open(authorization_url)

    async def callback_handler(self) -> tuple[str, str | None]:
        if not hasattr(self, "_server"):
            self._server = _OAuthCallbackServer(self.port, self.path)
            self._server.start()
        try:
            return await asyncio.to_thread(self._server.wait_for_code)
        finally:
            self._server.stop()


class _OAuthCallbackServer:
    def __init__(self, port: int, path: str):
        self.port = port
        self.path = path
        self.result_queue: queue.Queue[tuple[str, str | None]] = queue.Queue(maxsize=1)
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != server_ref.path:
                    self.send_response(404)
                    self.end_headers()
                    return

                params = parse_qs(parsed.query)
                code = params.get("code", [""])[0]
                state = params.get("state", [None])[0]
                server_ref.result_queue.put((code, state))
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Authorization complete. You can close this tab.")

            def log_message(self, format, *args):
                return

        self.httpd = HTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def wait_for_code(self, timeout: float = 300.0) -> tuple[str, str | None]:
        return self.result_queue.get(timeout=timeout)

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def decode_mcp_tool_result(result: Any) -> Any:
    """Decode common MCP SDK tool result shapes."""

    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        return result.structuredContent
    if hasattr(result, "content"):
        return _decode_content(result.content)
    return result


def decode_mcp_tools_result(result: Any) -> list[dict[str, Any]]:
    """Decode common MCP SDK list-tools result shapes."""

    tools = getattr(result, "tools", result)
    if tools is None:
        return []
    decoded = []
    for tool in tools:
        if hasattr(tool, "model_dump"):
            payload = tool.model_dump(mode="json")
        elif isinstance(tool, dict):
            payload = dict(tool)
        else:
            payload = {
                "name": getattr(tool, "name", ""),
                "description": getattr(tool, "description", ""),
                "inputSchema": getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None),
            }
        decoded.append(
            {
                "name": str(payload.get("name") or ""),
                "description": str(payload.get("description") or ""),
                "input_schema": payload.get("inputSchema") or payload.get("input_schema") or {},
            }
        )
    return decoded


def _decode_content(content: Any) -> Any:
    if content is None:
        return {}
    if isinstance(content, list):
        decoded = [_decode_content_item(item) for item in content]
        if len(decoded) == 1:
            return decoded[0]
        return decoded
    return _decode_content_item(content)


def _decode_content_item(item: Any) -> Any:
    text = None
    if isinstance(item, dict):
        text = item.get("text")
    elif hasattr(item, "text"):
        text = item.text

    if text is None:
        return item

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
