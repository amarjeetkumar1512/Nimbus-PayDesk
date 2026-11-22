
from app.schemas import InvoiceIn, InvoicePacket

invoice = InvoiceIn(
    invoice_id="INV-1001",
    vendor="ABC Traders",
    amount=12000,
    gstin="09ABCDE1234F1Z5",
    po_id="PO-2207"
)

print("Invoice Input Validation Successful!")
print(invoice.model_dump())

packet = InvoicePacket(
    cid="cid-001",
    invoice_id=invoice.invoice_id,
    vendor=invoice.vendor,
    amount=invoice.amount,
    gstin=invoice.gstin,
    po_id=invoice.po_id,
    confidence=1.0,
    status="ready_to_pay"
)

print("\nInvoice Packet Validation Successful!")
print(packet.model_dump())
