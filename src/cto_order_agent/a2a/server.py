"""A2A JSON-RPC surface over Starlette (binding: JSONRPC, v1.0.0)."""

from __future__ import annotations

import uuid
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from .agent_card import build_agent_card
from .executor import AgentExecutor
from .tasks import StoredTask


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _task_payload(task_id: str, context_id: str, text: str, state: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "contextId": context_id,
        "status": {"state": state},
        "artifacts": [
            {
                "artifactId": f"artifact-{task_id}",
                "parts": [{"kind": "text", "text": text}],
            }
        ],
        "kind": "task",
    }


def _extract_text(payload: dict[str, Any]) -> str:
    params = payload.get("params") or {}
    message = params.get("message") or {}
    parts = message.get("parts") or []
    for part in parts:
        if part.get("kind") in (None, "text") and isinstance(part.get("text"), str):
            return str(part["text"])
    return ""


def create_app(executor: AgentExecutor, card: dict[str, Any] | None = None) -> Starlette:
    agent_card = card or build_agent_card()
    store = executor.store

    async def agent_card_endpoint(request: Request) -> JSONResponse:
        return JSONResponse(agent_card)

    async def healthz(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "tasks": len(store)})

    async def root(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "name": agent_card["name"],
                "protocolVersion": "1.0.0",
                "binding": "JSONRPC",
                "endpoint": "/a2a",
                "agentCard": "/.well-known/agent-card.json",
            }
        )

    async def a2a(request: Request) -> Any:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001
            return JSONResponse(_error(None, -32700, "parse error"))

        request_id = payload.get("id")
        method = payload.get("method")
        if method not in ("message/send", "message/stream"):
            return JSONResponse(_error(request_id, -32601, f"unsupported method {method}"))

        text = _extract_text(payload)
        params = payload.get("params") or {}
        message = params.get("message") or {}
        context_id = message.get("contextId") or str(uuid.uuid4())
        task_id = params.get("taskId") or str(uuid.uuid4())

        turn = await executor.handle_turn(text, context_id, task_id)
        task = StoredTask(
            task_id=task_id,
            context_id=context_id,
            state=turn.state,
            artifacts=_task_payload(task_id, context_id, turn.message, turn.state)["artifacts"],
            history=[{"role": "user", "text": text}, {"role": "agent", "text": turn.message}],
        )
        store.put(task)
        result = {"task": _task_payload(task_id, context_id, turn.message, turn.state)}

        if method == "message/stream":
            import json

            payload_event = {"jsonrpc": "2.0", "id": request_id, "result": result}

            async def events() -> Any:
                yield f"data: {json.dumps(payload_event)}\n\n"

            return StreamingResponse(events(), media_type="text/event-stream")

        return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def get_task(request: Request) -> Any:
        task_id = request.path_params["task_id"]
        task = store.get(task_id)
        if task is None:
            return JSONResponse(_error(task_id, -32001, "task not found"), status_code=404)
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": task_id,
                "result": {
                    "task": _task_payload(
                        task.task_id,
                        task.context_id,
                        task.history[-1]["text"] if task.history else "",
                        task.state,
                    )
                },
            }
        )

    routes = [
        Route("/", root),
        Route("/healthz", healthz),
        Route("/.well-known/agent-card.json", agent_card_endpoint),
        Route("/a2a", a2a, methods=["POST"]),
        Route("/a2a/tasks/{task_id}", get_task),
    ]
    return Starlette(routes=routes)


__all__ = ["create_app"]
