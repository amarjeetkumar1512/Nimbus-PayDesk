
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("API_KEY")

from app.main import app


def unique_invoice_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def invoice_payload(prefix, amount, gstin="09ABCDE1234F1Z5", po_id="PO-2207",
                    vendor="ABC Traders"):
    return {
        "invoice_id": unique_invoice_id(prefix),
        "vendor": vendor,
        "amount": amount,
        "gstin": gstin,
        "po_id": po_id
    }


def test_api_key_configuration():
    assert API_KEY, "API_KEY is missing from the .env configuration."


def test_ingest_without_api_key():
    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json=invoice_payload("API-NO-KEY", 12000)
        )

    assert response.status_code == 401


def test_ingest_with_wrong_api_key():
    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json=invoice_payload("API-WRONG-KEY", 12000),
            headers={"x-api-key": "invalid-test-key"}
        )

    assert response.status_code == 401


def test_ingest_missing_amount():
    payload = invoice_payload("API-MISSING-AMOUNT", 12000)
    payload.pop("amount")

    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json=payload,
            headers={"x-api-key": API_KEY}
        )

    assert response.status_code == 422


def test_clean_invoice_ingest_and_ticket_audit():
    with TestClient(app) as client:
        response = client.post(
            "/ingest",
            json=invoice_payload("API-CLEAN", 12000),
            headers={"x-api-key": API_KEY}
        )

        assert response.status_code == 200

        result = response.json()

        assert result["status"] == "ready_to_pay"
        assert result["ticket_id"]
        assert result["cid"]
        assert result["report"]

        ticket_response = client.get(
            f"/tickets/{result['ticket_id']}",
            headers={"x-api-key": API_KEY}
        )

        assert ticket_response.status_code == 200

        ticket_data = ticket_response.json()

        assert ticket_data["ticket"]["status"] == "ready_to_pay"
        assert ticket_data["ticket"]["cid"] == result["cid"]
        assert len(ticket_data["events"]) >= 9

        assert all(
            event["stage"]
            and event["event"]
            and event["ts"]
            for event in ticket_data["events"]
)


def test_ticket_not_found():
    unknown_ticket_id = str(uuid.uuid4())

    with TestClient(app) as client:
        response = client.get(
            f"/tickets/{unknown_ticket_id}",
            headers={"x-api-key": API_KEY}
        )

    assert response.status_code == 404


def test_high_value_human_approval_and_duplicate_stamp():
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest",
            json=invoice_payload(
                "API-HIGH-APPROVE",
                75000,
                po_id="PO-75000"
            ),
            headers={"x-api-key": API_KEY}
        )

        assert ingest_response.status_code == 200

        result = ingest_response.json()

        assert result["status"] == "needs_human"
        ticket_id = result["ticket_id"]

        stamp_response = client.post(
            f"/tickets/{ticket_id}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Verified manually"
            },
            headers={"x-api-key": API_KEY}
        )

        assert stamp_response.status_code == 200

        stamp_data = stamp_response.json()

        assert stamp_data["status"] == "ready_to_pay"
        assert stamp_data["reviewer"] == "AP Lead"

        second_stamp = client.post(
            f"/tickets/{ticket_id}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Second approval attempt"
            },
            headers={"x-api-key": API_KEY}
        )

        assert second_stamp.status_code == 409

        ticket_response = client.get(
            f"/tickets/{ticket_id}",
            headers={"x-api-key": API_KEY}
        )

        assert ticket_response.status_code == 200

        ticket_data = ticket_response.json()

        assert ticket_data["ticket"]["status"] == "ready_to_pay"

        events = ticket_data["events"]

        assert any(
            event["event"] == "human_stamp"
            for event in events
        )

        assert any(
            event["event"] == "status_changed"
            for event in events
        )


def test_human_rejection():
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest",
            json=invoice_payload(
                "API-HIGH-REJECT",
                75000,
                po_id="PO-75000"
            ),
            headers={"x-api-key": API_KEY}
        )

        assert ingest_response.status_code == 200

        ticket_id = ingest_response.json()["ticket_id"]

        stamp_response = client.post(
            f"/tickets/{ticket_id}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "reject",
                "comment": "Supporting document missing"
            },
            headers={"x-api-key": API_KEY}
        )

        assert stamp_response.status_code == 200

        result = stamp_response.json()

        assert result["status"] == "needs_human"
        assert result["decision"] == "reject"
        assert "AP Lead" in result["reason"]

        ticket_response = client.get(
            f"/tickets/{ticket_id}",
            headers={"x-api-key": API_KEY}
        )

        assert ticket_response.status_code == 200

        events = ticket_response.json()["events"]

        assert any(
            event["event"] == "human_stamp"
            for event in events
        )


def test_approval_cannot_override_inactive_gstin():
    with TestClient(app) as client:
        ingest_response = client.post(
            "/ingest",
            json=invoice_payload(
                "API-INACTIVE-APPROVAL",
                12000,
                gstin="09ABCDE1234F1Z6",
                po_id="PO-INACTIVE-12000",
                vendor="Inactive Traders"
            ),
            headers={"x-api-key": API_KEY}
        )

        assert ingest_response.status_code == 200

        result = ingest_response.json()

        assert result["status"] == "needs_human"

        stamp_response = client.post(
            f"/tickets/{result['ticket_id']}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Attempted approval"
            },
            headers={"x-api-key": API_KEY}
        )

        assert stamp_response.status_code == 409
