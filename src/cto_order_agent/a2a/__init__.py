"""A2A protocol surface (v1.0.0, JSON-RPC binding)."""

from .agent_card import build_agent_card
from .executor import AgentExecutor, AgentTurn
from .tasks import TaskStore

__all__ = ["AgentExecutor", "AgentTurn", "TaskStore", "build_agent_card"]
