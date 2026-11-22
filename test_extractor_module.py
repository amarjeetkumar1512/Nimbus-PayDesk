
from pathlib import Path

from app.extractor import extract_invoice_fields


TEXT_PATH = Path("data/sample_invoices/extracted_invoice.txt")


def main():
    if not TEXT_PATH.exists():
        raise FileNotFoundError(f"Invoice text not found: {TEXT_PATH}")

    invoice_text = TEXT_PATH.read_text(encoding="utf-8")

    print("Testing reusable invoice extractor...")

    result = extract_invoice_fields(invoice_text)

    print("\nExtraction Result:")
    for key, value in result.items():
        print(f"{key}: {value}")

    if result["success"]:
        print("\nPASS: All required fields were extracted and source-verified.")
    else:
        print("\nREVIEW REQUIRED: Extraction was incomplete or could not be verified.")


if __name__ == "__main__":
    main()
