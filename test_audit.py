
import sqlite3

from app.tools import log_event

result = log_event(
    cid="cid-001",
    invoice_id="INV-1001",
    stage="INTAKE",
    event="INVOICE_RECEIVED",
    detail="Invoice received successfully"
)

print("Audit Event Saved:", result)

conn = sqlite3.connect("data/nimbus.db")

rows = conn.execute("""
    SELECT cid, invoice_id, stage, event, detail
    FROM events
    WHERE cid = ?
""", ("cid-001",)).fetchall()

print("\nAudit Records:")

for row in rows:
    print(row)

conn.close()
