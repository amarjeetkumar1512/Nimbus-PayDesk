
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class InvoiceIn(BaseModel):
    """Structured invoice submission payload."""

    model_config = ConfigDict(str_strip_whitespace=True)

    invoice_id: str = Field(min_length=1)
    vendor: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    gstin: str = Field(min_length=1)
    po_id: str = Field(min_length=1)


class InvoicePacket(BaseModel):
    """Invoice data used by the processing workflow."""

    cid: str
    invoice_id: str
    vendor: str
    amount: float
    gstin: str
    po_id: str
    confidence: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list)
    status: Literal["ready_to_pay", "needs_human"]
    reason: str = ""


class StampIn(BaseModel):
    """Named human reviewer decision."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reviewer: str = Field(min_length=1)
    decision: Literal["approve", "reject"]
    comment: str = ""


class TicketResponse(BaseModel):
    """Ticket information returned by the API."""

    ticket_id: str
    cid: str
    invoice_id: str | None = None
    status: Literal["ready_to_pay", "needs_human"]
    reason: str
    amount: float | None = None


class IngestResponse(BaseModel):
    """Invoice intake response."""

    ticket_id: str
    cid: str
    status: Literal["ready_to_pay", "needs_human"]
    reason: str


class StampResponse(BaseModel):
    """Human review response."""

    ticket_id: str
    cid: str
    status: Literal["ready_to_pay", "needs_human"]
    reviewer: str
    decision: Literal["approve", "reject"]
    reason: str
