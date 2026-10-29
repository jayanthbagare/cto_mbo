"""Agent discovery card. Built from typed models so it cannot drift by hand."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION = "1.0.0"
AGENT_URL = "https://cto-order-agent.example.com/a2a"

SKILLS: list[dict[str, Any]] = [
    {
        "id": "unified-order-view",
        "name": "Unified Order View",
        "description": (
            "Retrieves a sales order with all linked production orders, confirmations, and "
            "material availability and presents them as one consolidated view."
        ),
        "tags": ["sales-order", "production-order", "consolidation"],
        "examples": [
            "Show me the status of sales order 0000012345",
            "What production orders are linked to 0000012345?",
            "What about the second production order?",
        ],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain", "application/json"],
    },
    {
        "id": "exception-detection",
        "name": "Exception Detection",
        "description": (
            "Identifies production orders with schedule slip, missing confirmation, quantity "
            "shortfall, material shortage, or status inconsistency, and ranks at-risk orders "
            "by severity."
        ),
        "tags": ["exceptions", "risk", "triage"],
        "examples": [
            "Which orders are at risk?",
            "Does order 0000012345 have any exceptions?",
        ],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain", "application/json"],
    },
    {
        "id": "risk-explanation",
        "name": "Risk Explanation",
        "description": (
            "Explains why an order is at risk, labelling every claim as a confirmed fact or an "
            "inferred risk and citing the source record and value behind it."
        ),
        "tags": ["explanation", "evidence", "auditability"],
        "examples": [
            "Why is order 0000012345 at risk?",
            "Where does that confirmed date come from?",
        ],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain", "application/json"],
    },
    {
        "id": "planner-recommendations",
        "name": "Planner Recommendations",
        "description": (
            "Recommends concrete, ranked next actions with an owning role for each detected "
            "exception. Read-only: the agent never changes order data."
        ),
        "tags": ["recommendations", "next-actions"],
        "examples": [
            "What should I do about order 0000012345?",
            "What is the most urgent thing to check today?",
        ],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain", "application/json"],
    },
    {
        "id": "customer-status-summary",
        "name": "Customer Status Summary",
        "description": (
            "Produces a short, jargon-free status summary suitable for a customer service "
            "representative, separating confirmed dates from estimates."
        ),
        "tags": ["customer-service", "summary"],
        "examples": [
            "Give me a customer-ready update for 0000012345",
            "Write a summary I can send to the customer",
        ],
        "inputModes": ["text/plain"],
        "outputModes": ["text/plain"],
    },
]


class AgentSkillDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    tags: list[str]
    examples: list[str]
    inputModes: list[str]
    outputModes: list[str]


class AgentCapabilitiesDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    streaming: bool
    pushNotifications: bool
    stateTransitionHistory: bool
    extensions: list[str]


class AgentInterfaceDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    protocolBinding: str
    protocolVersion: str


class AgentProviderDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization: str
    url: str


class AgentCardDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    version: str
    provider: AgentProviderDoc
    supportedInterfaces: list[AgentInterfaceDoc]
    capabilities: AgentCapabilitiesDoc
    defaultInputModes: list[str]
    defaultOutputModes: list[str]
    skills: list[AgentSkillDoc]
    securitySchemes: dict[str, Any]
    security: list[dict[str, list[str]]]


def build_agent_card() -> dict[str, Any]:
    card = AgentCardDoc(
        name="MTO/CTO Order Intelligence Agent",
        description=(
            "Read-only assistant for production planners and fulfillment teams. Consolidates "
            "SAP S/4HANA sales orders and their linked production orders into a single view, "
            "flags production exceptions, explains risk with source evidence, and recommends "
            "next actions."
        ),
        version="1.0.0",
        provider=AgentProviderDoc(
            organization="cto_mbo", url="https://example.com/cto-mbo"
        ),
        supportedInterfaces=[
            AgentInterfaceDoc(
                url=AGENT_URL,
                protocolBinding="JSONRPC",
                protocolVersion=PROTOCOL_VERSION,
            )
        ],
        capabilities=AgentCapabilitiesDoc(
            streaming=True,
            pushNotifications=False,
            stateTransitionHistory=True,
            extensions=[],
        ),
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain", "application/json"],
        skills=[AgentSkillDoc.model_validate(skill) for skill in SKILLS],
        securitySchemes={
            "oauth2": {
                "type": "oauth2",
                "description": "BTP destination-backed OAuth 2.0 client credentials.",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": (
                            "https://example.authentication.sap.hana.ondemand.com/oauth/token"
                        ),
                        "scopes": {
                            "order.read": "Read sales order and production order data"
                        },
                    }
                },
            }
        },
        security=[{"oauth2": ["order.read"]}],
    )
    return card.model_dump(mode="json")


__all__ = ["AGENT_URL", "PROTOCOL_VERSION", "SKILLS", "build_agent_card"]
