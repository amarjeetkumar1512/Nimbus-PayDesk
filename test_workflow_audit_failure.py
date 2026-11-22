
from unittest.mock import patch

import pytest

from app.db import get_connection
from app.workflow import process_invoice


def test_reporter_audit_failure_fails_closed():
    original_insert_event = __import__(
        "app.workflow",
        fromlist=["insert_event"]
    ).insert_event

    def failing_insert_event(
        conn,
        cid,
        invoice_id,
        stage,
        event,
        detail=""
    ):
        if stage == "REPORTER":
            raise RuntimeError("Simulated reporter audit failure.")

        return original_insert_event(
            conn,
            cid,
            invoice_id,
            stage,
            event,
            detail
        )

    with patch(
        "app.workflow.insert_event",
        side_effect=failing_insert_event
    ):
        with pytest.raises(RuntimeError):
            process_invoice(
                invoice_id="INV-AUDIT-FAIL-001",
                vendor="ABC Traders",
                amount=12000,
                gstin="09ABCDE1234F1Z5",
                po_id="PO-2207",
                confidence=1.0
            )

    conn = get_connection()

    try:
        ticket = conn.execute(
            """
            SELECT ticket_id, cid, status, reason
            FROM tickets
            WHERE invoice_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            ("INV-AUDIT-FAIL-001",)
        ).fetchone()

        assert ticket is not None
        assert ticket["status"] == "needs_human"
        assert "failure" in ticket["reason"].lower()

        events = conn.execute(
            """
            SELECT stage, event
            FROM events
            WHERE cid = ?
            ORDER BY id
            """,
            (ticket["cid"],)
        ).fetchall()

        event_names = [
            (event["stage"], event["event"])
            for event in events
        ]

        assert ("REPORTER", "decision_report_generated") not in event_names

        print("TICKET:", dict(ticket))
        print("EVENTS:", event_names)
        print("PASS: Reporter audit failure did not leave invoice Ready to Pay.")

    finally:
        conn.close()
