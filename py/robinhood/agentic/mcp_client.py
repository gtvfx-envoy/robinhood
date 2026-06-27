"""Standalone MCP client helpers for Agentic broker integrations."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


class McpClientUnavailable(RuntimeError):
    """Raised when the optional MCP SDK is not available."""


class StreamableHttpMcpToolClient:
    """Synchronous wrapper around an MCP Streamable HTTP tool client.

    This class intentionally stays small. OAuth/token provisioning should happen
    outside the trading strategy and pass a bearer token or headers here.
    """

    def __init__(
        self,
        url: str,
        bearer_token: str | None = None,
        bearer_token_env_var: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        if not url:
            raise ValueError("MCP url is required")
        self.url = url
        self.bearer_token = bearer_token
        self.bearer_token_env_var = bearer_token_env_var
        self.headers = dict(headers or {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return a decoded Python payload."""

        return asyncio.run(self._call_tool_async(name, arguments))

    async def _call_tool_async(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise McpClientUnavailable(
                "The optional 'mcp' package is required for Streamable HTTP MCP access. "
                "Install it with: python -m pip install 'mcp>=1.27,<2'"
            ) from exc

        headers = self._headers()
        async with streamablehttp_client(self.url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return decode_mcp_tool_result(result)

    def _headers(self) -> dict[str, str]:
        headers = dict(self.headers)
        token = self.bearer_token
        if not token and self.bearer_token_env_var:
            token = os.environ.get(self.bearer_token_env_var)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers


def decode_mcp_tool_result(result: Any) -> Any:
    """Decode common MCP SDK tool result shapes."""

    if hasattr(result, "structured_content") and result.structured_content is not None:
        return result.structured_content
    if hasattr(result, "structuredContent") and result.structuredContent is not None:
        return result.structuredContent
    if hasattr(result, "content"):
        return _decode_content(result.content)
    return result


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
