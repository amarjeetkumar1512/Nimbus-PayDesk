
from pathlib import Path

from pypdf import PdfReader

from app.extractor import extract_invoice_fields
from app.workflow import (
    process_invoice,
    create_extraction_failure_ticket,
)


PDF_PATH = Path("data/sample_invoices/sample-invoice.pdf")


def read_pdf_text(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    reader = PdfReader(str(pdf_path))

    if reader.is_encrypted:
        raise ValueError("Encrypted PDF cannot be processed.")

    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    invoice_text = "\n".join(pages).strip()

    if not invoice_text:
        raise ValueError(
            "No readable text found. This PDF may require OCR."
        )

    return invoice_text


def main():
    print("Reading PDF invoice...")

    try:
        invoice_text = read_pdf_text(PDF_PATH)

    except Exception as exc:
        print("\nPDF reading failed.")
        print("Reason:", str(exc))
        print("Creating manual review ticket...")

        result = create_extraction_failure_ticket(
            reason=f"PDF reading failed: {exc}",
            source="PDF"
        )

        print("\nManual review ticket created:")
        for key, value in result.items():
            print(f"{key}: {value}")

        return

    print("Extracting invoice fields...")

    try:
        extraction = extract_invoice_fields(invoice_text)

    except Exception as exc:
        extraction = {
            "success": False,
            "invoice_id": None,
            "amount": None,
            "reason": str(exc)
        }

    if not isinstance(extraction, dict):
        extraction = {
            "success": False,
            "invoice_id": None,
            "amount": None,
            "reason": "Invalid extractor response"
        }

    if not extraction.get("success"):
        print("\nExtraction failed.")
        print("Reason:", extraction.get("reason", "Unknown extraction error"))
        print("Creating manual review ticket...")

        result = create_extraction_failure_ticket(
            invoice_id=extraction.get("invoice_id"),
            amount=extraction.get("amount"),
            reason=extraction.get(
                "reason",
                "Required invoice fields could not be extracted."
            ),
            source="PDF"
        )

        print("\nManual review ticket created:")
        for key, value in result.items():
            print(f"{key}: {value}")

        return

    required_fields = (
        "invoice_id",
        "vendor",
        "amount",
        "gstin",
        "po_id",
        "confidence"
    )

    missing_fields = [
        field
        for field in required_fields
        if extraction.get(field) is None
    ]

    if missing_fields:
        reason = (
            "Extractor returned incomplete fields: "
            + ", ".join(missing_fields)
        )

        print("\nExtraction incomplete.")
        print("Reason:", reason)

        result = create_extraction_failure_ticket(
            invoice_id=extraction.get("invoice_id"),
            amount=extraction.get("amount"),
            reason=reason,
            source="PDF"
        )

        print("\nManual review ticket created:")
        for key, value in result.items():
            print(f"{key}: {value}")

        return

    print("\nExtracted invoice fields:")

    for field in required_fields:
        print(f"{field}: {extraction[field]}")

    print("\nSending invoice to shared workflow...")

    result = process_invoice(
        invoice_id=extraction["invoice_id"],
        vendor=extraction["vendor"],
        amount=extraction["amount"],
        gstin=extraction["gstin"],
        po_id=extraction["po_id"],
        confidence=extraction["confidence"]
    )

    print("\nWorkflow result:")

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
