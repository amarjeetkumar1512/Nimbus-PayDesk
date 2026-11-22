
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("API_KEY")

from app.main import app
from app.workflow import create_extraction_failure_ticket


def test_extraction_failure_ticket_can_be_retrieved():
    result = create_extraction_failure_ticket(
        reason="Test extraction failure",
        source="API_TEST"
    )

    with TestClient(app) as client:
        response = client.get(
            f"/tickets/{result['ticket_id']}",
            headers={"x-api-key": API_KEY}
        )

    assert response.status_code == 200

    data = response.json()

    assert data["ticket"]["invoice_id"] is None
    assert data["ticket"]["amount"] is None
    assert data["ticket"]["status"] == "needs_human"
    assert len(data["events"]) == 4
    assert "human review" in data["report"].lower()


def test_extraction_failure_cannot_be_approved():
    result = create_extraction_failure_ticket(
        reason="Test extraction failure",
        source="API_TEST"
    )

    with TestClient(app) as client:
        response = client.post(
            f"/tickets/{result['ticket_id']}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Attempted approval"
            },
            headers={"x-api-key": API_KEY}
        )

        assert response.status_code == 409

        ticket_response = client.get(
            f"/tickets/{result['ticket_id']}",
            headers={"x-api-key": API_KEY}
        )

    assert ticket_response.status_code == 200
    assert ticket_response.json()["ticket"]["status"] == "needs_human"
