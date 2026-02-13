"""Pharmacy agent tools — stubbed implementations for dostupnost-leku.cz support.

All tools return realistic mock data. Real API integration comes later
when API docs are available.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent.tools import Tool, ToolRegistry

logger = logging.getLogger(__name__)


def search_drugs(query: str, limit: int = 5) -> dict[str, Any]:
    """Search for drug availability on dostupnost-leku.cz (stubbed)."""
    logger.info("search_drugs called: query=%r, limit=%d", query, limit)
    return {
        "results": [
            {
                "name": f"{query} 100mg",
                "availability": "available",
                "pharmacies_in_stock": 3,
                "price_range": "120-180 CZK",
                "requires_prescription": True,
            },
            {
                "name": f"{query} 200mg",
                "availability": "limited",
                "pharmacies_in_stock": 1,
                "price_range": "220-280 CZK",
                "requires_prescription": True,
            },
        ],
        "total_found": 2,
        "source": "dostupnost-leku.cz (stub)",
    }


def manage_reservation(
    action: str,
    drug_name: str,
    pharmacy_id: str | None = None,
    patient_name: str | None = None,
    reservation_id: str | None = None,
) -> dict[str, Any]:
    """Create, check, or cancel drug reservations (stubbed)."""
    logger.info(
        "manage_reservation called: action=%r, drug=%r, pharmacy=%r",
        action,
        drug_name,
        pharmacy_id,
    )
    if action == "create":
        return {
            "status": "created",
            "reservation_id": "RES-2024-STUB-001",
            "drug_name": drug_name,
            "pharmacy": pharmacy_id or "Lékárna U Zlatého lva",
            "pickup_by": "2024-12-20",
            "note": "Reservation is valid for 3 business days.",
        }
    elif action == "check":
        return {
            "status": "active",
            "reservation_id": reservation_id or "RES-2024-STUB-001",
            "drug_name": drug_name,
            "pickup_by": "2024-12-20",
        }
    elif action == "cancel":
        return {
            "status": "cancelled",
            "reservation_id": reservation_id or "RES-2024-STUB-001",
        }
    return {"error": f"Unknown action: {action}"}


def web_search(query: str) -> dict[str, Any]:
    """Search the web for drug-related information (stubbed)."""
    logger.info("web_search called: query=%r", query)
    return {
        "results": [
            {
                "title": f"Informace o léku: {query}",
                "snippet": f"{query} je lék používaný k léčbě běžných onemocnění. "
                "Před použitím si přečtěte příbalový leták.",
                "url": f"https://example.com/drugs/{query.lower().replace(' ', '-')}",
            },
        ],
        "source": "web_search (stub)",
    }


def send_reply(
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Auto-send a reply to the patient (stubbed — returns success without sending)."""
    logger.info("send_reply called: to=%r, subject=%r", to, subject)
    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "message_id": "STUB-MSG-001",
        "note": "Stub: message not actually sent",
    }


def create_draft(
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Create a draft for human review (stubbed)."""
    logger.info("create_draft called: to=%r, subject=%r", to, subject)
    return {
        "status": "draft_created",
        "to": to,
        "subject": subject,
        "draft_id": "STUB-DRAFT-001",
        "note": "Stub: draft not actually created in Gmail",
    }


def escalate(
    reason: str,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Flag a message for human review (stubbed)."""
    logger.info("escalate called: reason=%r", reason)
    return {
        "status": "escalated",
        "reason": reason,
        "note": "Stub: no label applied, logged only",
    }


# ── Tool definitions ────────────────────────────────────────────────────────


PHARMACY_TOOLS: list[Tool] = [
    Tool(
        name="search_drugs",
        description="Search for drug availability on dostupnost-leku.cz. Returns availability status, prices, and pharmacy stock counts.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Drug name or active ingredient to search for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=search_drugs,
    ),
    Tool(
        name="manage_reservation",
        description="Create, check, or cancel drug reservations at a pharmacy.",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "check", "cancel"],
                    "description": "Action to perform",
                },
                "drug_name": {
                    "type": "string",
                    "description": "Name of the drug",
                },
                "pharmacy_id": {
                    "type": "string",
                    "description": "Pharmacy identifier (for create)",
                },
                "patient_name": {
                    "type": "string",
                    "description": "Patient name (for create)",
                },
                "reservation_id": {
                    "type": "string",
                    "description": "Reservation ID (for check/cancel)",
                },
            },
            "required": ["action", "drug_name"],
        },
        handler=manage_reservation,
    ),
    Tool(
        name="web_search",
        description="Search the web for drug-related information, side effects, interactions, or general pharmaceutical knowledge.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
            },
            "required": ["query"],
        },
        handler=web_search,
    ),
    Tool(
        name="send_reply",
        description="Auto-send a reply to the patient. Use this for straightforward drug availability queries where you are confident in the answer.",
        parameters={
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text",
                },
                "thread_id": {
                    "type": "string",
                    "description": "Gmail thread ID to reply to",
                },
            },
            "required": ["to", "subject", "body"],
        },
        handler=send_reply,
    ),
    Tool(
        name="create_draft",
        description="Create a draft email for human review. Use this for reservations, complaints, complex queries, or anything you are unsure about.",
        parameters={
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                },
                "body": {
                    "type": "string",
                    "description": "Email body text",
                },
                "thread_id": {
                    "type": "string",
                    "description": "Gmail thread ID",
                },
            },
            "required": ["to", "subject", "body"],
        },
        handler=create_draft,
    ),
    Tool(
        name="escalate",
        description="Flag a message for human review. Use this for medical advice requests, complaints, or anything outside the scope of drug availability support.",
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation",
                },
                "thread_id": {
                    "type": "string",
                    "description": "Gmail thread ID",
                },
            },
            "required": ["reason"],
        },
        handler=escalate,
    ),
]


def register_pharmacy_tools(registry: ToolRegistry) -> None:
    """Register all pharmacy tools with the given registry."""
    for tool in PHARMACY_TOOLS:
        registry.register(tool)
