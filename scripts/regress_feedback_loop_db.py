#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.auth import AuthUser
from core.feedback_loop import (
    create_or_update_ticket,
    list_notifications,
    list_tickets,
    mark_notifications_read,
    mark_retry_attempt,
    resolve_ticket,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'feedback.sqlite'}"
        user = AuthUser(sub="user-1", email="student@example.com", name="Student")
        other = AuthUser(sub="user-2", email="other@example.com", name="Other")
        request = {"question_text_solver": "unsupported projectile prompt"}
        failed_response = {"status": "failed", "reason": "unsupported"}
        passed_response = {"status": "passed", "engine_case": "level_ground_range", "answer": "10 m"}

        ticket = create_or_update_ticket(
            user=user,
            question_text="Unsupported projectile prompt",
            request=request,
            response=failed_response,
            debug_report_id="debug-1",
        )
        assert ticket["status"] == "open"
        assert ticket["attempts"] == 0

        duplicate = create_or_update_ticket(
            user=user,
            question_text="  Unsupported   projectile prompt ",
            request=request,
            response=failed_response,
            debug_report_id="debug-2",
        )
        assert duplicate["ticket_id"] == ticket["ticket_id"]

        assert len(list_tickets(user=user)) == 1
        assert len(list_tickets(user=other)) == 0

        retried = mark_retry_attempt(duplicate, response=failed_response)
        assert retried["attempts"] == 1
        assert list_tickets(user=user, include_resolved=False)[0]["attempts"] == 1

        resolved = resolve_ticket(retried, response=passed_response)
        assert resolved["status"] == "resolved"
        assert len(list_tickets(user=user, include_resolved=False)) == 0
        assert list_tickets(user=user)[0]["resolved_response"]["answer"] == "10 m"

        notifications = list_notifications(user=user)
        assert len(notifications) == 1
        assert notifications[0]["answer"] == "10 m"
        assert mark_notifications_read(user=user) == 1
        assert list_notifications(user=user) == []

    print("PASS feedback loop DB regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
