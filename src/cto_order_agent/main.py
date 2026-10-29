"""Process entrypoint: A2A app and MCP app in one container, one port."""

from __future__ import annotations

import os
from typing import Any

import uvicorn
from starlette.responses import JSONResponse
from starlette.routing import Route

from .a2a.executor import AgentExecutor
from .a2a.server import create_app as create_a2a_app
from .config import Settings
from .datasource.mock.adapter import MockDataSource
from .mcp_server.server import create_mcp_server
from .narrative.composer import Composer
from .observability.logging import configure_logging

PORT = int(os.environ.get("PORT", os.environ.get("A2A_PORT", "8080")))


def build_data_source(settings: Settings) -> Any:
    if settings.data_source == "odata":
        from .datasource.odata.client import ODataDataSource

        return ODataDataSource(settings)
    return MockDataSource.from_dir(settings.fixtures_dir)


def build_executor(settings: Settings, data_source: Any) -> AgentExecutor:
    return AgentExecutor(
        data_source=data_source,
        settings=settings,
        composer=Composer(settings),
        clock=settings.process_clock,
    )


def create_root_app(settings: Settings, executor: AgentExecutor, data_source: Any) -> Any:
    """A2A on every path except /mcp, which is the private tool surface."""
    a2a_app = create_a2a_app(executor)
    mcp_app = create_mcp_server(data_source).streamable_http_app()

    async def healthz(request: Any) -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "config": settings.redacted(), "tasks": len(executor.store)}
        )

    a2a_app.router.routes.insert(0, Route("/healthz", healthz))

    async def dispatch(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "lifespan":
            await mcp_app(scope, receive, send)
            return
        if scope.get("type") == "http" and str(scope.get("path", "")).startswith("/mcp"):
            await mcp_app(scope, receive, send)
            return
        await a2a_app(scope, receive, send)

    return dispatch


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    data_source = build_data_source(settings)
    executor = build_executor(settings, data_source)
    app = create_root_app(settings, executor, data_source)
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()


__all__ = ["build_data_source", "build_executor", "create_root_app", "main"]
