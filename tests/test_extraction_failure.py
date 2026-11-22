
import pytest

import app.db as db
import app.workflow as workflow

from app.workflow import create_extraction_failure_ticket


@pytest.fixture
def test_database(tmp_path, monkeypatch):
    database_path = tmp_path / "test_nimbus.db"

    monkeypatch.setattr(db, "DB_PATH", database_path)

    db.init_db()

    return database_path


def test_extraction_failure_creates_needs_human_ticket(test_database):
    result = create_extraction_failure_ticket(
        reason="Test extraction failure",
        source="PDF_TEST"
    )

    assert result["ticket_id"]
    assert result["cid"]
    assert result["invoice_id"] is None
    assert result["amount"] is None
    assert result["status"] == "needs_human"

    conn = db.get_connection()

    try:
        ticket = conn.execute(
            "SELECT * FROM tickets WHERE ticket_id = ?",
            (result["ticket_id"],)
        ).fetchone()

        assert ticket is not None
        assert ticket["invoice_id"] is None
        assert ticket["amount"] is None
        assert ticket["status"] == "needs_human"

        events = conn.execute(
            """
            SELECT stage, event, invoice_id
            FROM events
            WHERE cid = ?
            ORDER BY id
            """,
            (result["cid"],)
        ).fetchall()

        assert len(events) == 4

        assert [event["event"] for event in events] == [
            "invoice_received",
            "extraction_failed",
            "status_assigned",
            "decision_report_generated",
        ]

        assert all(event["invoice_id"] is None for event in events)

    finally:
        conn.close()


def test_extraction_failure_audit_error_rolls_back_ticket(
    test_database,
    monkeypatch
):
    original_insert_event = workflow.insert_event

    def failing_insert_event(
        conn,
        cid,
        invoice_id,
        stage,
        event,
        detail=""
    ):
        if event == "extraction_failed":
            raise RuntimeError("Simulated audit failure")

        return original_insert_event(
            conn,
            cid,
            invoice_id,
            stage,
            event,
            detail
        )

    monkeypatch.setattr(
        workflow,
        "insert_event",
        failing_insert_event
    )

    with pytest.raises(RuntimeError):
        create_extraction_failure_ticket(
            reason="Test audit failure",
            source="PDF_TEST"
        )

    conn = db.get_connection()

    try:
        ticket_count = conn.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]

        event_count = conn.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0]

        assert ticket_count == 0
        assert event_count == 0

    finally:
        conn.close()
