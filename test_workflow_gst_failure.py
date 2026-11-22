
import os
import uuid
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app.main import app

load_dotenv(override=True)

API_KEY = os.getenv("API_KEY", "")


def test_workflow_gst_failure():
    payload = {
        "invoice_id": f"INV-GST-FAIL-{uuid.uuid4().hex[:12]}",
        "vendor": "ABC Traders",
        "amount": 12000,
        "gstin": "09ABCDE1234F1Z5",
        "po_id": "PO-2207"
    }

    headers = {"x-api-key": API_KEY}

    with TestClient(app) as client:
        with patch(
            "app.workflow.gst_check",
            side_effect=Exception("Simulated GST database failure")
        ):
            response = client.post(
                "/ingest",
                json=payload,
                headers=headers
            )

        assert response.status_code == 200

        result = response.json()

        assert result["status"] == "needs_human"
        assert "GST tool error" in result["reason"]

        ticket_id = result["ticket_id"]

        ticket_response = client.get(
            f"/tickets/{ticket_id}",
            headers=headers
        )

        assert ticket_response.status_code == 200

        ticket_data = ticket_response.json()

        gst_events = [
            event
            for event in ticket_data["events"]
            if event["event"] == "gst_check_completed"
        ]

        assert len(gst_events) == 1
        assert "GST tool error" in gst_events[0]["detail"]
        assert ticket_data["ticket"]["status"] == "needs_human"

        print("HTTP STATUS:", response.status_code)
        print("TICKET:", result)
        print("GST AUDIT EVENT:", gst_events[0])
        print("PASS: GST failure safely routed to human review.")
