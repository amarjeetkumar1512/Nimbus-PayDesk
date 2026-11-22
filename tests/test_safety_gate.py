
import uuid

import pytest

from app.db import get_connection
from app.workflow import process_invoice


RISK_CASES = [
    "high_value_50000",
    "high_value_75000",
    "low_confidence_079",
    "low_confidence_050",
    "invalid_gstin",
    "inactive_gstin",
    "unknown_gstin",
    "gst_tool_error",
    "po_not_found",
    "po_vendor_mismatch",
    "po_amount_mismatch",
    "po_tool_error",
    "duplicate_invoice",
    "duplicate_tool_error",
    "policy_failure",
    "policy_no_results",
    "policy_tool_error",
    "invalid_gst_response",
    "invalid_po_response",
    "invalid_duplicate_response",
    "invalid_policy_response",
    "combined_gst_po_failure",
    "combined_high_value_duplicate",
    "combined_low_confidence_policy_failure",
]


def raise_tool_error(*args, **kwargs):
    raise RuntimeError("Simulated tool failure")


@pytest.mark.parametrize("scenario", RISK_CASES)
def test_risky_invoice_never_reaches_ready_to_pay(scenario):
    amount = 12000
    confidence = 1.0

    gst_checker = lambda gstin: {
        "valid": True,
        "reason": "GSTIN active"
    }

    po_checker = lambda **kwargs: {
        "valid": True,
        "reason": "PO matched"
    }

    duplicate_checker = lambda **kwargs: {
        "duplicate": False,
        "reason": "Not duplicate"
    }

    policy_retriever = lambda **kwargs: {
        "success": True,
        "reason": "Policy retrieved",
        "results": ["Test policy"]
    }

    if scenario == "high_value_50000":
        amount = 50000

    elif scenario == "high_value_75000":
        amount = 75000

    elif scenario == "low_confidence_079":
        confidence = 0.79

    elif scenario == "low_confidence_050":
        confidence = 0.50

    elif scenario == "invalid_gstin":
        gst_checker = lambda gstin: {
            "valid": False,
            "reason": "Invalid GSTIN format"
        }

    elif scenario == "inactive_gstin":
        gst_checker = lambda gstin: {
            "valid": False,
            "reason": "GSTIN inactive"
        }

    elif scenario == "unknown_gstin":
        gst_checker = lambda gstin: {
            "valid": False,
            "reason": "GSTIN not found"
        }

    elif scenario == "gst_tool_error":
        gst_checker = raise_tool_error

    elif scenario == "po_not_found":
        po_checker = lambda **kwargs: {
            "valid": False,
            "reason": "PO not found"
        }

    elif scenario == "po_vendor_mismatch":
        po_checker = lambda **kwargs: {
            "valid": False,
            "reason": "PO vendor mismatch"
        }

    elif scenario == "po_amount_mismatch":
        po_checker = lambda **kwargs: {
            "valid": False,
            "reason": "PO amount mismatch"
        }

    elif scenario == "po_tool_error":
        po_checker = raise_tool_error

    elif scenario == "duplicate_invoice":
        duplicate_checker = lambda **kwargs: {
            "duplicate": True,
            "reason": "Duplicate invoice"
        }

    elif scenario == "duplicate_tool_error":
        duplicate_checker = raise_tool_error

    elif scenario == "policy_failure":
        policy_retriever = lambda **kwargs: {
            "success": False,
            "reason": "Policy retrieval failed",
            "results": []
        }

    elif scenario == "policy_no_results":
        policy_retriever = lambda **kwargs: {
            "success": False,
            "reason": "No policy results found",
            "results": []
        }

    elif scenario == "policy_tool_error":
        policy_retriever = raise_tool_error

    elif scenario == "invalid_gst_response":
        gst_checker = lambda gstin: None

    elif scenario == "invalid_po_response":
        po_checker = lambda **kwargs: None

    elif scenario == "invalid_duplicate_response":
        duplicate_checker = lambda **kwargs: None

    elif scenario == "invalid_policy_response":
        policy_retriever = lambda **kwargs: []

    elif scenario == "combined_gst_po_failure":
        gst_checker = lambda gstin: {
            "valid": False,
            "reason": "GST verification failed"
        }
        po_checker = lambda **kwargs: {
            "valid": False,
            "reason": "PO mismatch"
        }

    elif scenario == "combined_high_value_duplicate":
        amount = 75000
        duplicate_checker = lambda **kwargs: {
            "duplicate": True,
            "reason": "Duplicate invoice"
        }

    elif scenario == "combined_low_confidence_policy_failure":
        confidence = 0.79
        policy_retriever = lambda **kwargs: {
            "success": False,
            "reason": "Policy unavailable",
            "results": []
        }

    result = process_invoice(
        invoice_id=f"T19-{scenario}-{uuid.uuid4().hex[:8]}",
        vendor="Nimbus Test Vendor",
        amount=amount,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-T19-TEST",
        confidence=confidence,
        gst_checker=gst_checker,
        po_checker=po_checker,
        duplicate_checker=duplicate_checker,
        policy_retriever=policy_retriever
    )

    assert result["status"] == "needs_human", (
        f"SAFETY FAILURE: {scenario} reached {result['status']}"
    )

    conn = get_connection()

    try:
        ticket = conn.execute(
            """
            SELECT status, cid
            FROM tickets
            WHERE ticket_id = ?
            """,
            (result["ticket_id"],)
        ).fetchone()

        assert ticket is not None
        assert ticket["status"] == "needs_human"
        assert ticket["cid"] == result["cid"]

        events = conn.execute(
            """
            SELECT cid, stage, event
            FROM events
            WHERE cid = ?
            """,
            (result["cid"],)
        ).fetchall()

        assert len(events) >= 9
        assert all(event["cid"] == result["cid"] for event in events)

        assert any(
            event["event"] == "status_assigned"
            for event in events
        )

    finally:
        conn.close()


def test_clean_invoice_can_reach_ready_to_pay():
    result = process_invoice(
        invoice_id=f"T19-CLEAN-{uuid.uuid4().hex[:8]}",
        vendor="Nimbus Test Vendor",
        amount=12000,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-T19-CLEAN",
        confidence=1.0,
        gst_checker=lambda gstin: {
            "valid": True,
            "reason": "GSTIN active"
        },
        po_checker=lambda **kwargs: {
            "valid": True,
            "reason": "PO matched"
        },
        duplicate_checker=lambda **kwargs: {
            "duplicate": False,
            "reason": "Not duplicate"
        },
        policy_retriever=lambda **kwargs: {
            "success": True,
            "reason": "Policy retrieved",
            "results": ["Test policy"]
        }
    )

    assert result["status"] == "ready_to_pay"
