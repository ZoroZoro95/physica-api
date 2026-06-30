from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from .auth import AuthUser
from .db import connect, initialize_feedback_schema, placeholder


def create_or_update_ticket(
    *,
    user: AuthUser | None,
    question_text: str,
    request: BaseModel | dict,
    response: BaseModel | dict,
    debug_report_id: str | None = None,
) -> dict[str, Any]:
    _ensure_schema()
    existing = _find_open_ticket(question_text=question_text, user_email=user.email if user else "")
    ticket_id = str(existing.get("ticket_id") or f"fb_{uuid4().hex[:12]}")
    now = _now()
    record = {
        "ticket_id": ticket_id,
        "created_at": existing.get("created_at") or now,
        "updated_at": now,
        "status": "open",
        "user": _user_payload(user),
        "question_text": question_text,
        "debug_report_id": debug_report_id,
        "latest_request": _payload(request),
        "latest_response": _payload(response),
        "attempts": int(existing.get("attempts") or 0),
        "resolved_at": None,
        "resolved_response": None,
        "notification_sent": False,
    }
    if existing:
        _update_ticket(record)
    else:
        _insert_ticket(record)
    return record


def list_tickets(*, user: AuthUser | None = None, include_resolved: bool = True) -> list[dict[str, Any]]:
    _ensure_schema()
    p = placeholder()
    sql = "SELECT * FROM feedback_tickets"
    params: list[Any] = []
    clauses: list[str] = []
    if user:
        clauses.append(f"user_email = {p}")
        params.append(user.email)
    if not include_resolved:
        clauses.append(f"status != {p}")
        params.append("resolved")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at DESC"
    with connect() as conn:
        rows = conn.cursor().execute(sql, params).fetchall()
    return [_ticket_from_row(row) for row in rows]


def resolve_ticket(ticket: dict[str, Any], *, response: BaseModel | dict) -> dict[str, Any]:
    _ensure_schema()
    now = _now()
    record = {
        **ticket,
        "updated_at": now,
        "status": "resolved",
        "attempts": int(ticket.get("attempts") or 0) + 1,
        "resolved_at": now,
        "resolved_response": _payload(response),
        "notification_sent": False,
    }
    _update_ticket(record)
    _append_notification(record)
    return record


def mark_retry_attempt(ticket: dict[str, Any], *, response: BaseModel | dict) -> dict[str, Any]:
    _ensure_schema()
    record = {
        **ticket,
        "updated_at": _now(),
        "attempts": int(ticket.get("attempts") or 0) + 1,
        "latest_response": _payload(response),
    }
    _update_ticket(record)
    return record


def list_notifications(*, user: AuthUser) -> list[dict[str, Any]]:
    _ensure_schema()
    p = placeholder()
    with connect() as conn:
        rows = conn.cursor().execute(
            f"""
            SELECT * FROM feedback_notifications
            WHERE user_email = {p} AND read_at IS NULL
            ORDER BY created_at DESC
            """,
            [user.email],
        ).fetchall()
    return [_notification_from_row(row) for row in rows]


def mark_notifications_read(*, user: AuthUser) -> int:
    _ensure_schema()
    p = placeholder()
    now = _now()
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE feedback_notifications SET read_at = {p} WHERE user_email = {p} AND read_at IS NULL",
            [now, user.email],
        )
        return int(cur.rowcount or 0)


def _insert_ticket(record: dict[str, Any]) -> None:
    p = placeholder()
    user = record.get("user") or {}
    with connect() as conn:
        conn.cursor().execute(
            f"""
            INSERT INTO feedback_tickets (
                ticket_id, created_at, updated_at, status,
                user_sub, user_email, user_name, user_picture,
                question_text, debug_report_id, latest_request, latest_response,
                attempts, resolved_at, resolved_response, notification_sent
            ) VALUES ({", ".join([p] * 16)})
            """,
            [
                record["ticket_id"],
                record["created_at"],
                record["updated_at"],
                record["status"],
                user.get("sub") or "",
                user.get("email") or "",
                user.get("name") or "",
                user.get("picture") or "",
                record.get("question_text") or "",
                record.get("debug_report_id"),
                _json(record.get("latest_request") or {}),
                _json(record.get("latest_response") or {}),
                int(record.get("attempts") or 0),
                record.get("resolved_at"),
                _json(record.get("resolved_response")) if record.get("resolved_response") is not None else None,
                1 if record.get("notification_sent") else 0,
            ],
        )


def _update_ticket(record: dict[str, Any]) -> None:
    p = placeholder()
    user = record.get("user") or {}
    with connect() as conn:
        conn.cursor().execute(
            f"""
            UPDATE feedback_tickets
            SET created_at = {p},
                updated_at = {p},
                status = {p},
                user_sub = {p},
                user_email = {p},
                user_name = {p},
                user_picture = {p},
                question_text = {p},
                debug_report_id = {p},
                latest_request = {p},
                latest_response = {p},
                attempts = {p},
                resolved_at = {p},
                resolved_response = {p},
                notification_sent = {p}
            WHERE ticket_id = {p}
            """,
            [
                record["created_at"],
                record["updated_at"],
                record["status"],
                user.get("sub") or "",
                user.get("email") or "",
                user.get("name") or "",
                user.get("picture") or "",
                record.get("question_text") or "",
                record.get("debug_report_id"),
                _json(record.get("latest_request") or {}),
                _json(record.get("latest_response") or {}),
                int(record.get("attempts") or 0),
                record.get("resolved_at"),
                _json(record.get("resolved_response")) if record.get("resolved_response") is not None else None,
                1 if record.get("notification_sent") else 0,
                record["ticket_id"],
            ],
        )


def _append_notification(ticket: dict[str, Any]) -> None:
    user = ticket.get("user") or {}
    if not user.get("email"):
        return
    resolved = ticket.get("resolved_response") or {}
    p = placeholder()
    notification = {
        "notification_id": f"nt_{uuid4().hex[:12]}",
        "ticket_id": ticket.get("ticket_id"),
        "created_at": _now(),
        "read_at": None,
        "user": user,
        "question_text": ticket.get("question_text"),
        "engine_case": resolved.get("engine_case"),
        "answer": resolved.get("answer"),
        "debug_report_id": ticket.get("debug_report_id"),
    }
    with connect() as conn:
        conn.cursor().execute(
            f"""
            INSERT INTO feedback_notifications (
                notification_id, ticket_id, created_at, read_at,
                user_sub, user_email, user_name, user_picture,
                question_text, engine_case, answer, debug_report_id
            ) VALUES ({", ".join([p] * 12)})
            """,
            [
                notification["notification_id"],
                notification["ticket_id"],
                notification["created_at"],
                notification["read_at"],
                user.get("sub") or "",
                user.get("email") or "",
                user.get("name") or "",
                user.get("picture") or "",
                notification.get("question_text"),
                notification.get("engine_case"),
                notification.get("answer"),
                notification.get("debug_report_id"),
            ],
        )


def _find_open_ticket(*, question_text: str, user_email: str) -> dict[str, Any]:
    normalized = _normalize_question(question_text)
    for ticket in list_tickets(include_resolved=False):
        if _normalize_question(str(ticket.get("question_text") or "")) != normalized:
            continue
        ticket_email = (ticket.get("user") or {}).get("email") or ""
        if user_email and ticket_email != user_email:
            continue
        if not user_email and ticket_email:
            continue
        return ticket
    return {}


def _ticket_from_row(row: Any) -> dict[str, Any]:
    item = _row_dict(row)
    return {
        "ticket_id": item.get("ticket_id"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "status": item.get("status"),
        "user": {
            "sub": item.get("user_sub") or "",
            "email": item.get("user_email") or "",
            "name": item.get("user_name") or "",
            "picture": item.get("user_picture") or "",
        },
        "question_text": item.get("question_text") or "",
        "debug_report_id": item.get("debug_report_id"),
        "latest_request": _parse_json(item.get("latest_request"), {}),
        "latest_response": _parse_json(item.get("latest_response"), {}),
        "attempts": int(item.get("attempts") or 0),
        "resolved_at": item.get("resolved_at"),
        "resolved_response": _parse_json(item.get("resolved_response"), None),
        "notification_sent": bool(item.get("notification_sent")),
    }


def _notification_from_row(row: Any) -> dict[str, Any]:
    item = _row_dict(row)
    return {
        "notification_id": item.get("notification_id"),
        "ticket_id": item.get("ticket_id"),
        "created_at": item.get("created_at"),
        "read_at": item.get("read_at"),
        "user": {
            "sub": item.get("user_sub") or "",
            "email": item.get("user_email") or "",
            "name": item.get("user_name") or "",
            "picture": item.get("user_picture") or "",
        },
        "question_text": item.get("question_text"),
        "engine_case": item.get("engine_case"),
        "answer": item.get("answer"),
        "debug_report_id": item.get("debug_report_id"),
    }


def _payload(value: BaseModel | dict | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _user_payload(user: AuthUser | None) -> dict[str, Any]:
    if not user:
        return {"sub": "", "email": "", "name": "", "picture": ""}
    return {"sub": user.sub, "email": user.email, "name": user.name, "picture": user.picture}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def _normalize_question(question_text: str) -> str:
    return " ".join(question_text.lower().split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema() -> None:
    initialize_feedback_schema()
