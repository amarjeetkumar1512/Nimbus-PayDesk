import requests
import os
from dotenv import load_dotenv

load_dotenv()

headers = {
    "x-api-key": os.getenv("API_KEY")
}

payload = {
    "invoice_id": "INV-PO-MISMATCH-001",
    "vendor": "ABC Traders",
    "amount": 12000,
    "gstin": "09ABCDE1234F1Z5",
    "po_id": "PO-MISMATCH-12000"
}

response = requests.post(
    "http://127.0.0.1:8000/ingest",
    headers=headers,
    json=payload
)

print("HTTP Status:", response.status_code)
print(response.text)