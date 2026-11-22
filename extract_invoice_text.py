
from pathlib import Path
from pypdf import PdfReader


PDF_PATH = Path("data/sample_invoices/sample-invoice.pdf")
OUTPUT_PATH = Path("data/sample_invoices/extracted_invoice.txt")


def extract_invoice_text():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"Invoice PDF not found: {PDF_PATH}")

    reader = PdfReader(str(PDF_PATH))

    if reader.is_encrypted:
        raise ValueError("The invoice PDF is encrypted.")

    extracted_pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        extracted_pages.append(
            f"\n--- PAGE {page_number} ---\n{text}"
        )

    full_text = "\n".join(extracted_pages).strip()

    if not full_text:
        raise ValueError(
            "No readable text found. This PDF may require OCR."
        )

    OUTPUT_PATH.write_text(full_text, encoding="utf-8")

    print("PDF extraction successful.")
    print("Pages:", len(reader.pages))
    print("Extracted characters:", len(full_text))
    print("Saved to:", OUTPUT_PATH)
    print("\nExtracted invoice text preview:\n")
    print(full_text[:3000])


if __name__ == "__main__":
    extract_invoice_text()
