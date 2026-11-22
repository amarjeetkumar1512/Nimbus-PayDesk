
from app.router import route_invoice

valid_gst = {"valid": True}
valid_po = {"valid": True}
not_duplicate = {"duplicate": False}

# Test 1: Clean invoice
print("TEST 1 - CLEAN:")
print(route_invoice(
    12000, 1.0, valid_gst, valid_po, not_duplicate
))

# Test 2: High-value invoice
print("\nTEST 2 - HIGH VALUE:")
print(route_invoice(
    75000, 1.0, valid_gst, valid_po, not_duplicate
))

# Test 3: Low confidence
print("\nTEST 3 - LOW CONFIDENCE:")
print(route_invoice(
    12000, 0.79, valid_gst, valid_po, not_duplicate
))

# Test 4: Invalid GSTIN
print("\nTEST 4 - INVALID GSTIN:")
print(route_invoice(
    12000, 1.0,
    {"valid": False, "reason": "Unknown GSTIN"},
    valid_po,
    not_duplicate
))
