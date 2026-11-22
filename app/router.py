
import math

from app.rules import (
    requires_human_approval,
    requires_confidence_review
)


def route_invoice(
    amount: float,
    confidence: float,
    gst_result: dict,
    po_result: dict,
    duplicate_result: dict,
    policy_result: dict | None = None
) -> dict:
    """
    Apply deterministic Nimbus PayDesk business rules.

    All unknown, invalid, or failed conditions fail closed.
    Policy retrieval provides context; it never approves an invoice.
    """

    reasons = []

    # 1. Validate invoice amount
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(amount)
        or amount <= 0
    ):
        reasons.append("Invalid invoice amount")

    # 2. Validate extraction confidence
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        reasons.append("Invalid extraction confidence")

    # 3. Validate tool response structures
    tool_results = {
        "GST": gst_result,
        "PO": po_result,
        "Duplicate": duplicate_result
    }

    for tool_name, result in tool_results.items():
        if not isinstance(result, dict):
            reasons.append(f"{tool_name} tool error: invalid response")

    # 4. High-value invoice rule
    if (
        isinstance(amount, (int, float))
        and not isinstance(amount, bool)
        and math.isfinite(amount)
        and amount > 0
    ):
        if requires_human_approval(amount):
            reasons.append("amount>=50000")

    # 5. Confidence rule
    if (
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and math.isfinite(confidence)
        and 0 <= confidence <= 1
    ):
        if requires_confidence_review(confidence):
            reasons.append("confidence<0.80")

    # 6. GST verification
    if isinstance(gst_result, dict):
        if gst_result.get("valid") is not True:
            reasons.append(
                gst_result.get("reason") or "GST verification failed"
            )

    # 7. Purchase order verification
    if isinstance(po_result, dict):
        if po_result.get("valid") is not True:
            reasons.append(
                po_result.get("reason") or "PO verification failed"
            )

    # 8. Duplicate verification
    if isinstance(duplicate_result, dict):
        if duplicate_result.get("duplicate") is not False:
            reasons.append(
                duplicate_result.get("reason") or "Duplicate check failed"
            )

    # 9. AP policy retrieval tool failure
    # Policy content does not make the approval decision.
    if policy_result is not None:
        if (
            not isinstance(policy_result, dict)
            or policy_result.get("success") is not True
        ):
            reasons.append("AP policy retrieval failed")

    # 10. Final deterministic decision
    if reasons:
        return {
            "status": "needs_human",
            "reason": "; ".join(dict.fromkeys(reasons))
        }

    return {
        "status": "ready_to_pay",
        "reason": "All policy and validation checks passed"
    }
