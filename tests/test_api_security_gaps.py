
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("API_KEY")

from app.main import app


def test_get_ticket_without_api_key():
    with TestClient(app) as client:
        response = client.get(
            f"/tickets/{uuid.uuid4()}"
        )

    assert response.status_code == 401


def test_get_ticket_with_wrong_api_key():
    with TestClient(app) as client:
        response = client.get(
            f"/tickets/{uuid.uuid4()}",
            headers={"x-api-key": "invalid-test-key"}
        )

    assert response.status_code == 401


def test_stamp_without_api_key():
    with TestClient(app) as client:
        response = client.post(
            f"/tickets/{uuid.uuid4()}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Test"
            }
        )

    assert response.status_code == 401


def test_stamp_with_wrong_api_key():
    with TestClient(app) as client:
        response = client.post(
            f"/tickets/{uuid.uuid4()}/stamp",
            json={
                "reviewer": "AP Lead",
                "decision": "approve",
                "comment": "Test"
            },
            headers={"x-api-key": "invalid-test-key"}
        )

    assert response.status_code == 401


def test_stamp_without_reviewer_is_rejected():
    with TestClient(app) as client:
        response = client.post(
            f"/tickets/{uuid.uuid4()}/stamp",
            json={
                "reviewer": " ",
                "decision": "approve",
                "comment": "Test"
            },
            headers={"x-api-key": API_KEY}
        )

    assert response.status_code == 422
