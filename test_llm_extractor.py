
import json
import re
from pathlib import Path

from langchain_ollama import ChatOllama


INVOICE_PATH = Path(
    "data/sample_invoices/extracted_invoice.txt"
)

MODEL_NAME = "qwen2.5:0.5b"

REQUIRED_FIELDS = [
    "vendor",
    "invoice_id",
    "invoice_date",
    "due_date",
    "po_id",
    "vendor_tax_id",
    "subtotal",
    "gst_amount",
    "total_amount",
    "currency",
]

EXPECTED_TEXT_FIELDS = {
    "vendor": "Larkfield Stationers",
    "invoice_id": "INV-2026-0142",
    "invoice_date": "18 September 2026",
    "due_date": "18 October 2026",
    "po_id": "PO-77310",
    "vendor_tax_id": "SPECIMEN-TAX-0001",
}

EXPECTED_AMOUNT_FIELDS = {
    "subtotal": 14702.00,
    "gst_amount": 2646.36,
    "total_amount": 17348.36,
}


def parse_amount(value):
    """Convert formatted INR amounts into numeric values."""

    if value is None or isinstance(value, bool):
        raise ValueError("Invalid amount")

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        cleaned = (
            value.replace("₹", "")
            .replace(",", "")
            .replace("INR", "")
            .strip()
        )

        if not cleaned:
            raise ValueError("Amount is empty")

        return float(cleaned)

    raise ValueError("Unsupported amount format")


def extract_amount_after_label(text, label):
    """Extract an amount appearing after a specified label."""

    pattern = (
        re.escape(label)
        + r"\s*₹?\s*([0-9,]+\.\d{2})"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def extract_from_source(source_text):
    """
    Extract fields from the selected sample invoice.
    This parser is specific to the specimen layout.
    """

    lines = [
        line.strip()
        for line in source_text.splitlines()
        if line.strip()
        and not re.fullmatch(
            r"-{2,}\s*PAGE\s+\d+\s*-{2,}",
            line.strip(),
            flags=re.IGNORECASE
        )
    ]

    source_data = {
        field: None for field in REQUIRED_FIELDS
    }

    # Ignore page markers and identify the seller name.
    if lines:
        source_data["vendor"] = lines[0]

    # First Tax no. belongs to the seller in this specimen.
    tax_matches = re.findall(
        r"Tax no\.:\s*([A-Z0-9-]+)",
        source_text,
        flags=re.IGNORECASE
    )

    if tax_matches:
        source_data["vendor_tax_id"] = tax_matches[0]

    # Extract invoice number.
    match = re.search(
        r"Invoice no\.?\s*([\s\S]*?)Invoice date",
        source_text,
        flags=re.IGNORECASE
    )

    if match:
        values = [
            line.strip()
            for line in match.group(1).splitlines()
            if line.strip()
        ]

        if values:
            source_data["invoice_id"] = values[0]

    # Extract invoice date.
    match = re.search(
        r"Invoice date\s*([\s\S]*?)Due date",
        source_text,
        flags=re.IGNORECASE
    )

    if match:
        values = [
            line.strip()
            for line in match.group(1).splitlines()
            if line.strip()
        ]

        if values:
            source_data["invoice_date"] = values[0]

    # Extract due date.
    match = re.search(
        r"Due date\s*([\s\S]*?)Order ref\.",
        source_text,
        flags=re.IGNORECASE
    )

    if match:
        values = [
            line.strip()
            for line in match.group(1).splitlines()
            if line.strip()
        ]

        if values:
            source_data["due_date"] = values[0]

    # Extract PO ID only from Order ref.
    match = re.search(
        r"Order ref\.\s*([A-Z0-9-]+)",
        source_text,
        flags=re.IGNORECASE
    )

    if match:
        source_data["po_id"] = match.group(1).strip()

    source_data["subtotal"] = extract_amount_after_label(
        source_text,
        "Subtotal"
    )

    source_data["gst_amount"] = extract_amount_after_label(
        source_text,
        "GST at 18%"
    )

    source_data["total_amount"] = extract_amount_after_label(
        source_text,
        "Total due"
    )

    source_data["currency"] = "INR"

    return source_data


def parse_llm_response(raw_response):
    """Parse JSON returned by Ollama."""

    if not isinstance(raw_response, str):
        raise ValueError("LLM response is not text")

    cleaned = raw_response.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found")

    data = json.loads(cleaned[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")

    return data


def extract_with_llm(invoice_text):
    """Extract invoice fields using Ollama."""

    llm = ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        num_predict=400,
        client_kwargs={
            "timeout": 120
        }
    )

    prompt = f"""
You are an invoice data extraction system.

Extract the following information from the invoice.

Rules:

1. Vendor means the seller issuing the invoice.
2. Invoice ID comes from Invoice no.
3. PO ID comes only from Order ref., Purchase Order,
   or PO Number.
4. Never use a bank account number as a PO ID.
5. Vendor tax ID belongs to the seller, not buyer.
6. Keep subtotal, GST and total separate.
7. Do not guess missing values.
8. Use null if a value is unavailable.
9. Return only valid JSON.

Required JSON:

{{
    "vendor": null,
    "invoice_id": null,
    "invoice_date": null,
    "due_date": null,
    "po_id": null,
    "vendor_tax_id": null,
    "subtotal": null,
    "gst_amount": null,
    "total_amount": null,
    "currency": "INR"
}}

INVOICE TEXT:

{invoice_text}
"""

    response = llm.invoke(prompt)

    return response.content


def merge_extractions(llm_data, source_data):
    """Prefer source-labelled values over LLM values."""

    final_data = {}

    for field in REQUIRED_FIELDS:
        source_value = source_data.get(field)
        llm_value = llm_data.get(field)

        if source_value is not None:
            final_data[field] = source_value
        else:
            final_data[field] = llm_value

    return final_data


def validate_extraction(data):
    """Validate fields and amount arithmetic."""

    errors = []

    if not isinstance(data, dict):
        return ["Invalid extraction object"]

    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None:
            errors.append(f"{field}: missing value")

    for field, expected in EXPECTED_TEXT_FIELDS.items():
        actual = data.get(field)

        if not isinstance(actual, str):
            errors.append(
                f"{field}: missing or invalid value"
            )
        elif actual.strip() != expected:
            errors.append(
                f"{field}: expected '{expected}', got '{actual}'"
            )

    parsed_amounts = {}

    for field, expected in EXPECTED_AMOUNT_FIELDS.items():
        try:
            actual = parse_amount(data.get(field))
            parsed_amounts[field] = actual

            if abs(actual - expected) > 0.01:
                errors.append(
                    f"{field}: expected {expected:.2f}, "
                    f"got {actual:.2f}"
                )

        except (TypeError, ValueError):
            errors.append(
                f"{field}: missing or non-numeric value"
            )

    if data.get("currency") != "INR":
        errors.append("Invalid currency")

    if len(parsed_amounts) == 3:
        calculated_total = (
            parsed_amounts["subtotal"]
            + parsed_amounts["gst_amount"]
        )

        if abs(
            calculated_total - parsed_amounts["total_amount"]
        ) > 0.01:
            errors.append(
                "Subtotal + GST does not equal total amount"
            )

    return errors


def main():

    print("=" * 65)
    print("NIMBUS PAYDESK - INVOICE EXTRACTION TEST")
    print("=" * 65)

    confidence = 0.0
    status = "needs_human"

    try:
        if not INVOICE_PATH.exists():
            raise FileNotFoundError(
                f"File not found: {INVOICE_PATH}"
            )

        invoice_text = INVOICE_PATH.read_text(
            encoding="utf-8"
        )

        if not invoice_text.strip():
            raise ValueError("Invoice text is empty")

        print("\nInvoice text loaded successfully.")
        print("\nSending invoice to Ollama...")

        raw_response = extract_with_llm(invoice_text)

        print("\nRaw LLM response:\n")
        print(raw_response)

        llm_data = parse_llm_response(raw_response)

        print("\nParsed LLM JSON:\n")
        print(
            json.dumps(
                llm_data,
                indent=4,
                ensure_ascii=False
            )
        )

        source_data = extract_from_source(invoice_text)

        print("\nSource-based extraction:\n")
        print(
            json.dumps(
                source_data,
                indent=4,
                ensure_ascii=False
            )
        )

        final_data = merge_extractions(
            llm_data,
            source_data
        )

        print("\nFinal merged extraction:\n")
        print(
            json.dumps(
                final_data,
                indent=4,
                ensure_ascii=False
            )
        )

        errors = validate_extraction(final_data)

        print("\n" + "=" * 65)
        print("SOURCE VALIDATION RESULT")
        print("=" * 65)

        if errors:
            print("\nVALIDATION FAILED:")

            for error in errors:
                print("-", error)

            confidence = 0.0
            status = "needs_human"

        else:
            print("\nAll validation checks passed.")

            confidence = 1.0
            status = "validated"

    except Exception as error:
        print(f"\nEXTRACTION ERROR: {error}")

        confidence = 0.0
        status = "needs_human"

    finally:
        print("\n" + "=" * 65)
        print("FINAL EXTRACTION RESULT")
        print("=" * 65)

        print(f"Confidence: {confidence}")
        print(f"Status: {status}")

        if status == "validated":
            print("Extraction validation completed successfully.")
        else:
            print("Human review is required.")

        print("=" * 65)


if __name__ == "__main__":
    main()
