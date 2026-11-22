
from datetime import datetime, timezone

from app.db import get_connection
from app.rules import validate_gstin_format
from app.policy_kb import retrieve_policy as chroma_retrieve_policy


def gst_check(gstin: str) -> dict:
    """Validate GSTIN format and check vendor status."""

    if not isinstance(gstin, str) or not validate_gstin_format(gstin):
        return {
            "valid": False,
            "reason": "Invalid GSTIN format"
        }

    try:
        normalized_gstin = gstin.strip().upper()

        with get_connection() as conn:
            vendor = conn.execute(
                """
                SELECT gstin, name, active
                FROM vendors
                WHERE gstin = ?
                """,
                (normalized_gstin,)
            ).fetchone()

        if vendor is None:
            return {
                "valid": False,
                "reason": "Unknown GSTIN"
            }

        if vendor["active"] != 1:
            return {
                "valid": False,
                "reason": "Inactive GSTIN"
            }

        return {
            "valid": True,
            "reason": "GSTIN verified",
            "vendor": vendor["name"]
        }

    except Exception:
        return {
            "valid": False,
            "reason": "GST tool error"
        }


def po_lookup(po_id: str, vendor: str, amount: float) -> dict:
    """Check whether PO exists and matches vendor and amount."""

    if not all(isinstance(value, str) and value.strip()
               for value in [po_id, vendor]):
        return {
            "valid": False,
            "reason": "Invalid PO or vendor input"
        }

    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return {
            "valid": False,
            "reason": "Invalid invoice amount"
        }

    try:
        with get_connection() as conn:
            po = conn.execute(
                """
                SELECT po_id, vendor, amount
                FROM purchase_orders
                WHERE po_id = ?
                """,
                (po_id.strip(),)
            ).fetchone()

        if po is None:
            return {
                "valid": False,
                "reason": "PO not found"
            }

        if po["vendor"].strip().casefold() != vendor.strip().casefold():
            return {
                "valid": False,
                "reason": "PO vendor mismatch"
            }

        if abs(float(po["amount"]) - float(amount)) > 0.01:
            return {
                "valid": False,
                "reason": "PO amount mismatch"
            }

        return {
            "valid": True,
            "reason": "PO verified"
        }

    except Exception:
        return {
            "valid": False,
            "reason": "PO lookup error"
        }


def duplicate_check(
    invoice_id: str,
    exclude_ticket_id: str | None = None
) -> dict:
    """
    Check whether an earlier submission exists for this invoice.

    exclude_ticket_id allows the current ticket to be excluded
    when the ticket has already been created during intake.
    """

    if not isinstance(invoice_id, str) or not invoice_id.strip():
        return {
            "duplicate": True,
            "reason": "Invalid invoice ID"
        }

    try:
        with get_connection() as conn:

            if exclude_ticket_id:
                invoice = conn.execute(
                    """
                    SELECT ticket_id, invoice_id
                    FROM tickets
                    WHERE invoice_id = ?
                    AND ticket_id != ?
                    LIMIT 1
                    """,
                    (invoice_id.strip(), exclude_ticket_id)
                ).fetchone()

            else:
                invoice = conn.execute(
                    """
                    SELECT ticket_id, invoice_id
                    FROM tickets
                    WHERE invoice_id = ?
                    LIMIT 1
                    """,
                    (invoice_id.strip(),)
                ).fetchone()

        if invoice is not None:
            return {
                "duplicate": True,
                "reason": "Duplicate invoice",
                "existing_ticket_id": invoice["ticket_id"]
            }

        return {
            "duplicate": False,
            "reason": "Invoice is not a duplicate"
        }

    except Exception:
        return {
            "duplicate": True,
            "reason": "Duplicate check error"
        }


def policy_retrieve(query: str, top_k: int = 3) -> dict:
    """
    Retrieve relevant AP policy sections from ChromaDB.

    Policy retrieval provides context only.
    It does not make invoice approval decisions.
    """

    if not isinstance(query, str) or not query.strip():
        return {
            "success": False,
            "reason": "Policy query cannot be empty",
            "results": []
        }

    if (
        not isinstance(top_k, int)
        or isinstance(top_k, bool)
        or top_k < 1
    ):
        return {
            "success": False,
            "reason": "top_k must be a positive integer",
            "results": []
        }

    try:
        results = chroma_retrieve_policy(
            query=query.strip(),
            top_k=top_k
        )

        if not results:
            return {
                "success": False,
                "reason": "No relevant AP policy found",
                "results": []
            }

        return {
            "success": True,
            "reason": "AP policy retrieved successfully",
            "results": results
        }

    except Exception:
        return {
            "success": False,
            "reason": "Policy retrieval error",
            "results": []
        }


def log_event(
    cid: str,
    invoice_id: str,
    stage: str,
    event: str,
    detail: str = ""
) -> bool:
    """Save an audit event against an invoice correlation ID."""

    required_values = [cid, invoice_id, stage, event]

    if not all(
        isinstance(value, str) and value.strip()
        for value in required_values
    ):
        return False

    if not isinstance(detail, str):
        return False

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO events
                (cid, invoice_id, stage, event, detail, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cid.strip(),
                    invoice_id.strip(),
                    stage.strip(),
                    event.strip(),
                    detail,
                    datetime.now(timezone.utc).isoformat()
                )
            )

            conn.commit()

        return True

    except Exception:
        return False
