
import uuid

from app.workflow import process_invoice


def unique_invoice_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def test_real_tools_clean_invoice():
    result = process_invoice(
        invoice_id=unique_invoice_id("REAL-CLEAN"),
        vendor="ABC Traders",
        amount=12000,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-2207",
        confidence=1.0
    )

    assert result["status"] == "ready_to_pay"


def test_real_tools_inactive_gstin():
    result = process_invoice(
        invoice_id=unique_invoice_id("REAL-INACTIVE"),
        vendor="Inactive Traders",
        amount=12000,
        gstin="09ABCDE1234F1Z6",
        po_id="PO-INACTIVE-12000",
        confidence=1.0
    )

    assert result["status"] == "needs_human"


def test_real_tools_po_amount_mismatch():
    result = process_invoice(
        invoice_id=unique_invoice_id("REAL-PO-MISMATCH"),
        vendor="ABC Traders",
        amount=12000,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-MISMATCH-12000",
        confidence=1.0
    )

    assert result["status"] == "needs_human"


def test_real_tools_duplicate_invoice():
    invoice_id = unique_invoice_id("REAL-DUPLICATE")

    first_result = process_invoice(
        invoice_id=invoice_id,
        vendor="ABC Traders",
        amount=12000,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-2207",
        confidence=1.0
    )

    second_result = process_invoice(
        invoice_id=invoice_id,
        vendor="ABC Traders",
        amount=12000,
        gstin="09ABCDE1234F1Z5",
        po_id="PO-2207",
        confidence=1.0
    )

    assert first_result["status"] == "ready_to_pay"
    assert second_result["status"] == "needs_human"
    assert "Duplicate" in second_result["reason"] or (
        "duplicate" in second_result["reason"].lower()
    )
