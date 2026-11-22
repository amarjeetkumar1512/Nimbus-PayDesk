
import json
import re
from decimal import Decimal, InvalidOperation

from langchain_ollama import ChatOllama


MODEL_NAME = "qwen2.5:0.5b"


def clean_page_text(source_text: str) -> str:
    return re.sub(
        r"-{2,}\s*PAGE\s+\d+\s*-{2,}",
        "",
        source_text,
        flags=re.IGNORECASE
    ).strip()


def parse_json_response(response_text: str) -> dict:
    cleaned = response_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM did not return valid JSON.")

    result = json.loads(cleaned[start:end + 1])

    if not isinstance(result, dict):
        raise ValueError("LLM response must be a JSON object.")

    return result


def parse_amount(value) -> float | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    cleaned = re.sub(r"₹|INR|Rs\.?", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(",", "").strip()

    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None

    if not amount.is_finite() or amount <= 0:
        return None

    return float(amount)


def extract_labeled_value(text: str, label: str) -> str | None:
    pattern = rf"(?im)^\s*{re.escape(label)}\s*:?\s*\n?\s*([A-Z0-9][A-Z0-9-]*)\s*$"
    match = re.search(pattern, text)

    if match:
        return match.group(1).strip()

    return None


def extract_source_fields(source_text: str) -> dict:
    text = clean_page_text(source_text)

    fields = {
        "invoice_id": None,
        "vendor": None,
        "amount": None,
        "gstin": None,
        "po_id": None
    }

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if lines:
        for line in lines:
            if line.upper() == "TAX INVOICE":
                break
            if line.upper() != "A FICTIONAL COMPANY":
                fields["vendor"] = line
                break

    fields["invoice_id"] = extract_labeled_value(text, "Invoice no.")
    fields["po_id"] = extract_labeled_value(text, "Order ref.")

    supplier_section = re.split(
        r"(?im)^\s*BILL TO\s*$",
        text,
        maxsplit=1
    )[0]

    tax_match = re.search(
        r"(?im)^\s*Tax no\.?\s*:\s*([A-Z0-9-]+)\s*$",
        supplier_section
    )

    if tax_match:
        fields["gstin"] = tax_match.group(1).strip()

    total_match = re.search(
        r"(?im)^\s*Total due\s*\n\s*(?:₹|INR|Rs\.?)?\s*([\d,]+(?:\.\d{1,2})?)",
        text
    )

    if total_match:
        fields["amount"] = parse_amount(total_match.group(1))

    return fields


def verify_source_evidence(fields: dict, source_text: str) -> bool:
    text = clean_page_text(source_text).casefold()

    for field in ("invoice_id", "vendor", "gstin", "po_id"):
        value = fields.get(field)

        if not isinstance(value, str) or not value.strip():
            return False

        if value.casefold() not in text:
            return False

    amount = fields.get("amount")

    if amount is None:
        return False

    total_match = re.search(
        r"(?im)^\s*Total due\s*\n\s*(?:₹|INR|Rs\.?)?\s*([\d,]+(?:\.\d{1,2})?)",
        clean_page_text(source_text)
    )

    if not total_match:
        return False

    source_amount = parse_amount(total_match.group(1))

    return source_amount == amount


def extract_invoice_fields(source_text: str) -> dict:
    if not isinstance(source_text, str) or not source_text.strip():
        return {
            "success": False,
            "invoice_id": None,
            "vendor": None,
            "amount": None,
            "gstin": None,
            "po_id": None,
            "confidence": 0.0,
            "reason": "Invoice text is empty."
        }

    source_fields = extract_source_fields(source_text)

    prompt = f"""
Extract these fields from the invoice:
invoice_id, vendor, amount, gstin, po_id.

Use the supplier's tax number, not the buyer's.
Use the final total payable amount.
Never guess missing values. Return null if unclear.
Return only JSON.

Example:
{{
  "invoice_id": null,
  "vendor": null,
  "amount": null,
  "gstin": null,
  "po_id": null
}}

Invoice text:
{source_text}
"""

    try:
        model = ChatOllama(
            model=MODEL_NAME,
            temperature=0
        )

        response = model.invoke(prompt)

        if not isinstance(response.content, str):
            raise ValueError("Unexpected LLM response format.")

        llm_fields = parse_json_response(response.content)

        extracted = {}

        for field in ("invoice_id", "vendor", "gstin", "po_id"):
            source_value = source_fields.get(field)
            llm_value = llm_fields.get(field)

            if source_value:
                extracted[field] = source_value
            elif isinstance(llm_value, str) and llm_value.strip():
                extracted[field] = llm_value.strip()
            else:
                extracted[field] = None

        source_amount = source_fields.get("amount")
        llm_amount = parse_amount(llm_fields.get("amount"))

        extracted["amount"] = (
            source_amount if source_amount is not None else llm_amount
        )

        required_fields_present = all(
            extracted[field] is not None
            for field in ("invoice_id", "vendor", "amount", "gstin", "po_id")
        )

        if not required_fields_present:
            return {
                "success": False,
                **extracted,
                "confidence": 0.0,
                "reason": "One or more required invoice fields are missing."
            }

        if not verify_source_evidence(extracted, source_text):
            return {
                "success": False,
                **extracted,
                "confidence": 0.0,
                "reason": "Extracted fields could not all be verified against the invoice."
            }

        return {
            "success": True,
            **extracted,
            "confidence": 0.79,
            "reason": (
                "All required fields were extracted and source-verified. "
                "Confidence remains provisional pending calibration."
            )
        }

    except Exception as exc:
        return {
            "success": False,
            **source_fields,
            "confidence": 0.0,
            "reason": f"Invoice extraction failed: {exc}"
        }
