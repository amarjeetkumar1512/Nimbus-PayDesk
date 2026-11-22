
from app.rules import (
    validate_gstin_format,
    requires_human_approval,
    requires_confidence_review
)

print("GSTIN:", validate_gstin_format("09ABCDE1234F1Z5"))

print("Amount 75000:", requires_human_approval(75000))
print("Amount 49999:", requires_human_approval(49999))

print("Confidence 0.79:", requires_confidence_review(0.79))
print("Confidence 0.80:", requires_confidence_review(0.80))
