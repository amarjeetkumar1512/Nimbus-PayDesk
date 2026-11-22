
import re

# Institute-defined business thresholds
HIGH_VALUE_THRESHOLD = 50000
MIN_CONFIDENCE = 0.80

# GSTIN format validation
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
)


def validate_gstin_format(gstin: str) -> bool:
    """Check GSTIN format."""
    if not isinstance(gstin, str):
        return False

    return bool(GSTIN_PATTERN.fullmatch(gstin.strip().upper()))


def requires_human_approval(amount: float) -> bool:
    """Invoices of Rs. 50,000 or more require human approval."""
    return amount >= HIGH_VALUE_THRESHOLD


def requires_confidence_review(confidence: float) -> bool:
    """Confidence below 0.80 requires human review."""
    return confidence < MIN_CONFIDENCE
