# Nimbus PayDesk
## Invoice Automation with Human-in-the-Loop Controls

Nimbus PayDesk is an invoice-processing prototype designed to automate invoice validation and routing while maintaining human oversight for risky transactions.

**Core principle:** The AI reads and explains. Plain, testable code decides.

## Project Objectives

- Automate invoice intake and processing.
- Validate GSTIN and purchase order details.
- Detect duplicate invoices.
- Retrieve relevant accounts payable policies.
- Route risky invoices for human review.
- Maintain traceable audit events using correlation IDs.
- Generate human-readable decision reports.

## Technology Stack

- Python 3.11
- FastAPI
- Pydantic
- SQLite
- ChromaDB
- LangChain
- Ollama
- Pytest

## Architecture

The application follows a sequential processing workflow:

1. **INTAKE** – Accepts and validates invoice information.
2. **EXTRACTOR** – Extracts structured invoice information.
3. **POLICY CHECKER** – Runs GSTIN, purchase order, duplicate and policy checks.
4. **EXCEPTION ROUTER** – Applies deterministic business rules.
5. **REPORTER** – Generates a decision explanation.

## Business Rules

- Invoice amount greater than or equal to ₹50,000 requires human approval.
- Invalid, inactive or unknown GSTIN requires human review.
- Missing or mismatched purchase orders require human review.
- Duplicate invoices require human review.
- Extraction confidence below 0.80 requires human review.
- Tool failures must fail closed.
- Every status change must have an audit event.
- The prototype does not execute bank transfers or NEFT payments.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/ingest` | Submit an invoice |
| GET | `/tickets/{ticket_id}` | Retrieve ticket, status and audit events |
| POST | `/tickets/{ticket_id}/stamp` | Human approval or rejection |

API authentication uses the `x-api-key` header.

## Project Structure

```text
Nimbus PayDesk/
├── app/
│   ├── db.py
│   ├── extractor.py
│   ├── main.py
│   ├── policy_kb.py
│   ├── router.py
│   ├── rules.py
│   ├── schemas.py
│   ├── seed.py
│   ├── tools.py
│   └── workflow.py
├── data/
├── tests/
├── process_pdf_invoice.py
├── extract_invoice_text.py
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

## Setup

Activate the virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Configure the required environment variables in `.env`. Do not commit secrets or API keys.

## Run the Application

```powershell
uvicorn app.main:app --reload
```

Open API documentation:

http://127.0.0.1:8000/docs

## Run Tests

```powershell
python -m pytest -v
```

**Latest recorded test result:** 70 passed, 2 deprecation warnings.

## Safety and Human Oversight

The application routes risky invoices to `needs_human`. Human approval is restricted by the implemented business rules. Tool and audit failures are handled using fail-closed behavior.

The automated safety suite includes 24 simulated risky scenarios. These tests provide controlled test evidence and do not represent a production-scale risk measurement.

## Known Limitations

- Invoice extraction is currently tailored to the supplied specimen invoice format.
- Scanned PDF OCR is not implemented.
- Extraction confidence is provisional and not statistically calibrated.
- The `/ingest` API accepts structured invoice data; the PDF extraction utility is a separate workflow.
- n8n integration and production deployment should only be considered complete after their implementation and verification.
- No actual bank or NEFT payment is executed.

## Project Status

This is an academic capstone prototype. The latest full automated regression run completed with 70 passing tests and 2 deprecation warnings.

Further validation is required before production use.
