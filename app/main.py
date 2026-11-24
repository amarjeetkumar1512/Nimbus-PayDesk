
import os
import json
import secrets
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_connection, init_db
from app.schemas import InvoiceIn, StampIn
from app.workflow import process_invoice, generate_decision_report


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(BASE_DIR, ".env"))

API_KEY = os.getenv("API_KEY")

app = FastAPI(
    title="Nimbus PayDesk",
    description="Invoice Automation with Human-in-the-Loop Controls",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.on_event("startup")
def startup_event():
    init_db()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def verify_api_key(x_api_key: str = Header(default=None)):
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured."
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key."
        )

    return True


def build_ticket_report(ticket):
    status = ticket["status"]
    reason = ticket["reason"] or ""
    invoice_id = ticket["invoice_id"]

    if status == "ready_to_pay" and reason.startswith(
        "High-value invoice approved by "
    ):
        return (
            f"Invoice {invoice_id} was approved by a human reviewer "
            f"and is now Ready to Pay. {reason}"
        )

    return generate_decision_report(
        status,
        reason,
        invoice_id
    )


def build_ticket_response(conn, ticket):
    ticket_data = dict(ticket)

    events = conn.execute(
        """
        SELECT stage, event, detail, ts
        FROM events
        WHERE cid = ?
        ORDER BY id ASC
        """,
        (ticket_data["cid"],)
    ).fetchall()

    return {
        "ticket": ticket_data,
        "events": [dict(event) for event in events],
        "report": build_ticket_report(ticket_data)
    }


@app.get("/")
def home():
    return {
        "application": "Nimbus PayDesk",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/ingest", dependencies=[Depends(verify_api_key)])
def ingest_invoice(invoice: InvoiceIn):
    try:
        result = process_invoice(
            invoice_id=invoice.invoice_id,
            vendor=invoice.vendor,
            amount=invoice.amount,
            gstin=invoice.gstin,
            po_id=invoice.po_id,
            confidence=1.0
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Invoice processing failed. "
                "Check the ticket and audit records."
            )
        ) from exc

    return {
        "ticket_id": result["ticket_id"],
        "cid": result["cid"],
        "status": result["status"],
        "reason": result["reason"],
        "report": result["report"]
    }


@app.get(
    "/tickets",
    dependencies=[Depends(verify_api_key)]
)
def get_all_tickets():
    conn = get_connection()

    try:
        tickets = conn.execute(
            """
            SELECT *
            FROM tickets
            ORDER BY created_at DESC
            """
        ).fetchall()

        ticket_data = [
            build_ticket_response(conn, ticket)
            for ticket in tickets
        ]

        return {
            "total": len(ticket_data),
            "tickets": ticket_data
        }

    finally:
        conn.close()


@app.get(
    "/tickets/{ticket_id}",
    dependencies=[Depends(verify_api_key)]
)
def get_ticket(ticket_id: str):
    conn = get_connection()

    try:
        ticket = conn.execute(
            """
            SELECT *
            FROM tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,)
        ).fetchone()

        if ticket is None:
            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )

        return build_ticket_response(conn, ticket)

    finally:
        conn.close()


@app.post(
    "/tickets/{ticket_id}/stamp",
    dependencies=[Depends(verify_api_key)]
)
def stamp_ticket(ticket_id: str, stamp: StampIn):
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        ticket = conn.execute(
            """
            SELECT *
            FROM tickets
            WHERE ticket_id = ?
            """,
            (ticket_id,)
        ).fetchone()

        if ticket is None:
            conn.rollback()
            raise HTTPException(
                status_code=404,
                detail="Ticket not found."
            )

        current_status = ticket["status"]
        current_reason = ticket["reason"] or ""

        if current_status != "needs_human":
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail=(
                    "This ticket is already resolved. "
                    "Further stamping is not allowed."
                )
            )

        previous_stamp = conn.execute(
            """
            SELECT id
            FROM events
            WHERE cid = ?
              AND stage = 'HUMAN_REVIEW'
              AND event = 'human_stamp'
            LIMIT 1
            """,
            (ticket["cid"],)
        ).fetchone()

        if previous_stamp is not None:
            conn.rollback()
            raise HTTPException(
                status_code=409,
                detail="This ticket has already been reviewed."
            )

        reasons = [
            item.strip()
            for item in current_reason.split(";")
            if item.strip()
        ]

        if stamp.decision == "approve":
            if reasons != ["amount>=50000"]:
                conn.rollback()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Approval denied. Human approval cannot override "
                        "GST, PO, duplicate, extraction or other "
                        "validation failures."
                    )
                )

            new_status = "ready_to_pay"
            new_reason = (
                f"High-value invoice approved by {stamp.reviewer}."
            )

        else:
            new_status = "needs_human"
            new_reason = (
                f"Human reviewer rejected: {stamp.reviewer}. "
                f"{stamp.comment}".strip()
            )

        conn.execute(
            """
            UPDATE tickets
            SET status = ?, reason = ?
            WHERE ticket_id = ?
            """,
            (new_status, new_reason, ticket_id)
        )

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
                ticket["cid"],
                ticket["invoice_id"],
                "HUMAN_REVIEW",
                "human_stamp",
                json.dumps({
                    "reviewer": stamp.reviewer,
                    "decision": stamp.decision,
                    "comment": stamp.comment,
                    "previous_status": current_status,
                    "new_status": new_status
                }),
                utc_now()
            )
        )

        if current_status != new_status:
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
                    ticket["cid"],
                    ticket["invoice_id"],
                    "HUMAN_REVIEW",
                    "status_changed",
                    f"{current_status} -> {new_status}",
                    utc_now()
                )
            )

        conn.commit()

        return {
            "ticket_id": ticket_id,
            "cid": ticket["cid"],
            "status": new_status,
            "reviewer": stamp.reviewer,
            "decision": stamp.decision,
            "reason": new_reason
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Human decision could not be saved."
        ) from exc

    finally:
        conn.close()
