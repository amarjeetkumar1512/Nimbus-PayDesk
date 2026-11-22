
from app.router import route_invoice


GST_OK = {"valid": True}
PO_OK = {"valid": True}
NO_DUPLICATE = {"duplicate": False}
POLICY_OK = {"success": True}


# ==========================================
# EXISTING BUSINESS RULE TESTS
# ==========================================

def test_amount_exactly_50000():
    result = route_invoice(
        50000, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_amount_49999():
    result = route_invoice(
        49999, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "ready_to_pay"


def test_confidence_exactly_080():
    result = route_invoice(
        12000, 0.80, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "ready_to_pay"


def test_confidence_below_080():
    result = route_invoice(
        12000, 0.79, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_duplicate_invoice():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK,
        {"duplicate": True}
    )
    assert result["status"] == "needs_human"


def test_po_mismatch():
    result = route_invoice(
        12000, 1.0, GST_OK,
        {"valid": False, "reason": "PO mismatch"},
        NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_gst_tool_error():
    result = route_invoice(
        12000, 1.0,
        {"valid": False, "reason": "GST tool error"},
        PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_clean_invoice():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "ready_to_pay"


# ==========================================
# ADDITIONAL SAFETY TESTS
# ==========================================

def test_invalid_confidence():
    result = route_invoice(
        12000, 1.5, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_negative_confidence():
    result = route_invoice(
        12000, -0.1, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_missing_gst_response():
    result = route_invoice(
        12000, 1.0, None, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_missing_po_response():
    result = route_invoice(
        12000, 1.0, GST_OK, None, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_missing_duplicate_response():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK, None
    )
    assert result["status"] == "needs_human"


def test_policy_retrieval_failure():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK, NO_DUPLICATE,
        {"success": False, "reason": "ChromaDB unavailable"}
    )
    assert result["status"] == "needs_human"


def test_invalid_amount():
    result = route_invoice(
        -100, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_missing_tool_success_flag():
    result = route_invoice(
        12000, 1.0,
        {}, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_duplicate_check_error():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK,
        {"duplicate": True, "reason": "Duplicate check error"}
    )
    assert result["status"] == "needs_human"


def test_boolean_amount_rejected():
    result = route_invoice(
        True, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_boolean_confidence_rejected():
    result = route_invoice(
        12000, True, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "needs_human"


def test_policy_result_optional_for_existing_callers():
    result = route_invoice(
        12000, 1.0, GST_OK, PO_OK, NO_DUPLICATE
    )
    assert result["status"] == "ready_to_pay"
