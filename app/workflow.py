
import json
import math
import uuid
from datetime import datetime, timezone

from app.db import get_connection
from app.tools import (
    gst_check,
    po_lookup,
    duplicate_check,
    policy_retrieve,
)
from app.router import route_invoice


class AuditLoggingError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_transaction(operation):
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")
        result = operation(conn)
        conn.commit()
        return result

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def insert_event(conn, cid, invoice_id, stage, event, detail=""):
    conn.execute(
        """
        INSERT INTO events (
            cid,
            invoice_id,
            stage,
            event,
            detail,
            ts
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            cid,
            invoice_id,
            stage,
            event,
            detail,
            utc_now()
        )
    )


def record_event(cid, invoice_id, stage, event, detail=""):
    try:
        run_transaction(
            lambda conn: insert_event(
                conn,
                cid,
                invoice_id,
                stage,
                event,
                detail
            )
        )
    except Exception as exc:
        raise AuditLoggingError(
            f"Audit event could not be saved: {stage}/{event}"
        ) from exc


def invoice_reference(invoice_id):
    if isinstance(invoice_id, str) and invoice_id.strip():
        return invoice_id.strip()

    return "unidentified invoice"


def generate_decision_report(status, reason, invoice_id):
    reference = invoice_reference(invoice_id)

    if status == "ready_to_pay":
        if reason.startswith("High-value invoice approved by "):
            return (
                f"Invoice {reference} was approved by a human reviewer "
                f"and is now Ready to Pay. {reason}"
            )

        return (
            f"Invoice {reference} passed the automated validation "
            f"checks and is Ready to Pay. {reason}"
        )

    return (
        f"Invoice {reference} requires human review. "
        f"Reason: {reason}"
    )


def mark_ticket_needs_human(ticket_id, cid, invoice_id, reason):
    def recover_ticket(conn):
        cursor = conn.execute(
            """
            UPDATE tickets
            SET status = ?, reason = ?
            WHERE ticket_id = ?
            """,
            ("needs_human", reason, ticket_id)
        )

        if cursor.rowcount != 1:
            raise RuntimeError("Ticket could not be recovered.")

        insert_event(
            conn,
            cid,
            invoice_id,
            "EXCEPTION_ROUTER",
            "processing_failed",
            reason
        )

    try:
        run_transaction(recover_ticket)
    except Exception as exc:
        raise AuditLoggingError(
            "Ticket recovery and failure audit could not be completed."
        ) from exc


def validate_invoice_inputs(
    invoice_id,
    vendor,
    amount,
    gstin,
    po_id,
    confidence
):
    fields = {
        "invoice_id": invoice_id,
        "vendor": vendor,
        "gstin": gstin,
        "po_id": po_id
    }

    for name, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{name} must be a non-empty string."
            )

    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("Invoice amount must be numeric.")

    try:
        valid_amount = (
            math.isfinite(float(amount))
            and amount > 0
        )
    except (ValueError, TypeError, OverflowError):
        valid_amount = False

    if not valid_amount:
        raise ValueError(
            "Invoice amount must be a finite positive number."
        )

    if isinstance(confidence, bool) or not isinstance(
        confidence, (int, float)
    ):
        raise ValueError("Invoice confidence must be numeric.")

    try:
        valid_confidence = (
            math.isfinite(float(confidence))
            and 0 <= confidence <= 1
        )
    except (ValueError, TypeError, OverflowError):
        valid_confidence = False

    if not valid_confidence:
        raise ValueError(
            "Invoice confidence must be between 0 and 1."
        )


def create_extraction_failure_ticket(
    invoice_id=None,
    amount=None,
    reason="Invoice extraction failed.",
    source="PDF"
):
    """
    Create a fail-closed ticket when invoice extraction fails.

    Unknown invoice ID and amount are stored as NULL.
    No missing invoice data is guessed.
    """

    if invoice_id is not None:
        if not isinstance(invoice_id, str):
            invoice_id = None
        else:
            invoice_id = invoice_id.strip() or None

    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        amount = None
    else:
        try:
            if not math.isfinite(float(amount)) or amount <= 0:
                amount = None
        except (ValueError, TypeError, OverflowError):
            amount = None

    if not isinstance(reason, str) or not reason.strip():
        reason = "Invoice extraction failed."

    if not isinstance(source, str) or not source.strip():
        source = "Unknown"

    ticket_id = str(uuid.uuid4())
    cid = "cid-" + str(uuid.uuid4())

    status = "needs_human"
    reason = (
        f"Extraction failed: {reason.strip()}. "
        "Manual review required."
    )

    report = generate_decision_report(
        status,
        reason,
        invoice_id
    )

    def create_failed_ticket(conn):
        conn.execute(
            """
            INSERT INTO tickets (
                ticket_id,
                invoice_id,
                cid,
                status,
                reason,
                amount,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                invoice_id,
                cid,
                status,
                reason,
                amount,
                utc_now()
            )
        )

        insert_event(
            conn,
            cid,
            invoice_id,
            "INTAKE",
            "invoice_received",
            f"{source} invoice received. Ticket created: {ticket_id}"
        )

        insert_event(
            conn,
            cid,
            invoice_id,
            "EXTRACTOR",
            "extraction_failed",
            reason
        )

        insert_event(
            conn,
            cid,
            invoice_id,
            "EXCEPTION_ROUTER",
            "status_assigned",
            f"Final status: {status}; Reason: {reason}"
        )

        insert_event(
            conn,
            cid,
            invoice_id,
            "REPORTER",
            "decision_report_generated",
            report
        )

    try:
        run_transaction(create_failed_ticket)
    except Exception as exc:
        raise RuntimeError(
            "Extraction failure ticket and audit events "
            "could not be saved."
        ) from exc

    return {
        "ticket_id": ticket_id,
        "cid": cid,
        "invoice_id": invoice_id,
        "amount": amount,
        "status": status,
        "reason": reason,
        "report": report
    }


def process_invoice(
    invoice_id,
    vendor,
    amount,
    gstin,
    po_id,
    confidence,
    gst_checker=None,
    po_checker=None,
    duplicate_checker=None,
    policy_retriever=None,
):
    if gst_checker is None:
        gst_checker = gst_check

    if po_checker is None:
        po_checker = po_lookup

    if duplicate_checker is None:
        duplicate_checker = duplicate_check

    if policy_retriever is None:
        policy_retriever = policy_retrieve

    validate_invoice_inputs(
        invoice_id,
        vendor,
        amount,
        gstin,
        po_id,
        confidence
    )

    invoice_id = invoice_id.strip()
    vendor = vendor.strip()
    gstin = gstin.strip().upper()
    po_id = po_id.strip()

    ticket_id = str(uuid.uuid4())
    cid = "cid-" + str(uuid.uuid4())

    ticket_created = False

    try:
        def create_ticket(conn):
            conn.execute(
                """
                INSERT INTO tickets (
                    ticket_id,
                    invoice_id,
                    cid,
                    status,
                    reason,
                    amount,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    invoice_id,
                    cid,
                    "needs_human",
                    "Processing",
                    amount,
                    utc_now()
                )
            )

            insert_event(
                conn,
                cid,
                invoice_id,
                "INTAKE",
                "invoice_received",
                f"Ticket created: {ticket_id}"
            )

        run_transaction(create_ticket)
        ticket_created = True

        record_event(
            cid,
            invoice_id,
            "EXTRACTOR",
            "extraction_completed",
            json.dumps({
                "confidence": confidence,
                "source": "invoice_processing"
            })
        )

        try:
            gst_result = gst_checker(gstin)

            if not isinstance(gst_result, dict):
                gst_result = {
                    "valid": False,
                    "reason": "Invalid GST tool response"
                }

        except Exception:
            gst_result = {
                "valid": False,
                "reason": "GST tool error"
            }

        record_event(
            cid,
            invoice_id,
            "POLICY_CHECKER",
            "gst_check_completed",
            json.dumps(gst_result, default=str)
        )

        try:
            po_result = po_checker(
                po_id=po_id,
                vendor=vendor,
                amount=amount
            )

            if not isinstance(po_result, dict):
                po_result = {
                    "valid": False,
                    "reason": "Invalid PO tool response"
                }

        except Exception:
            po_result = {
                "valid": False,
                "reason": "PO lookup error"
            }

        record_event(
            cid,
            invoice_id,
            "POLICY_CHECKER",
            "po_check_completed",
            json.dumps(po_result, default=str)
        )

        try:
            duplicate_result = duplicate_checker(
                invoice_id=invoice_id,
                exclude_ticket_id=ticket_id
            )

            if not isinstance(duplicate_result, dict):
                duplicate_result = {
                    "duplicate": True,
                    "reason": "Invalid duplicate check response"
                }

        except Exception:
            duplicate_result = {
                "duplicate": True,
                "reason": "Duplicate check error"
            }

        record_event(
            cid,
            invoice_id,
            "POLICY_CHECKER",
            "duplicate_check_completed",
            json.dumps(duplicate_result, default=str)
        )

        try:
            policy_result = policy_retriever(
                query=(
                    f"AP invoice payment policy for vendor {vendor}, "
                    f"amount {amount}, GSTIN verification and "
                    f"purchase order {po_id}"
                )
            )

            if not isinstance(policy_result, dict):
                policy_result = {
                    "success": False,
                    "reason": "Invalid policy retrieval response",
                    "results": []
                }

        except Exception:
            policy_result = {
                "success": False,
                "reason": "Policy retrieval error",
                "results": []
            }

        policy_detail = {
            "success": policy_result.get("success", False),
            "reason": policy_result.get("reason", "")
        }

        record_event(
            cid,
            invoice_id,
            "POLICY_CHECKER",
            "policy_retrieval_completed",
            json.dumps(policy_detail, default=str)
        )

        try:
            decision = route_invoice(
                amount=amount,
                confidence=confidence,
                gst_result=gst_result,
                po_result=po_result,
                duplicate_result=duplicate_result,
                policy_result=policy_result
            )

            if not isinstance(decision, dict):
                raise ValueError("Invalid router response.")

            status = decision.get("status")
            reason = decision.get("reason")

            if status not in ("ready_to_pay", "needs_human"):
                raise ValueError("Router returned an unknown status.")

            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("Router returned an invalid reason.")

        except Exception:
            status = "needs_human"
            reason = "Exception router error"

        decision_detail = (
            f"Status: {status}; Reason: {reason}"
        )

        report = generate_decision_report(
            status,
            reason,
            invoice_id
        )

        def finalize_invoice(conn):
            insert_event(
                conn,
                cid,
                invoice_id,
                "EXCEPTION_ROUTER",
                "decision_completed",
                decision_detail
            )

            cursor = conn.execute(
                """
                UPDATE tickets
                SET status = ?, reason = ?
                WHERE ticket_id = ?
                """,
                (status, reason, ticket_id)
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "Ticket status could not be updated."
                )

            insert_event(
                conn,
                cid,
                invoice_id,
                "EXCEPTION_ROUTER",
                "status_assigned",
                f"Final status: {status}; Reason: {reason}"
            )

            insert_event(
                conn,
                cid,
                invoice_id,
                "REPORTER",
                "decision_report_generated",
                report
            )

        run_transaction(finalize_invoice)

        return {
            "ticket_id": ticket_id,
            "cid": cid,
            "invoice_id": invoice_id,
            "status": status,
            "reason": reason,
            "confidence": confidence,
            "report": report
        }

    except Exception as exc:
        if ticket_created:
            try:
                mark_ticket_needs_human(
                    ticket_id,
                    cid,
                    invoice_id,
                    "Workflow or audit logging failure. Manual review required."
                )
            except Exception as recovery_error:
                raise RuntimeError(
                    "Workflow failed and fail-closed ticket recovery "
                    "also failed. Database inspection is required."
                ) from recovery_error

        raise RuntimeError(
            "Invoice processing did not complete successfully. "
            "Check the ticket and audit records."
        ) from exc
