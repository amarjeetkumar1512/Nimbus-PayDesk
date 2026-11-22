
from app.tools import gst_check, po_lookup, duplicate_check

print("GST CHECK:")
print(gst_check("09ABCDE1234F1Z5"))

print("\nPO CHECK:")
print(po_lookup("PO-2207", "ABC Traders", 12000))

print("\nDUPLICATE CHECK:")
print(duplicate_check("INV-1001"))
