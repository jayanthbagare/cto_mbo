"""MCP tool surface: five read-only tools, one per SAP OData API."""

from .server import create_mcp_server
from .tools import TOOL_NAMES, build_tool_specs

__all__ = ["TOOL_NAMES", "build_tool_specs", "create_mcp_server"]
