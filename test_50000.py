import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")

headers = {
    "x-api-key": api_key
}

payload = {
    "invoice_id": "INV-50000-TEST-NEW",
    "vendor": "ABC Traders",
    "amount": 50000,
    "gstin": "09ABCDE1234F1Z5",
    "po_id": "PO-50000"
}

response = requests.post(
    "http://127.0.0.1:8000/ingest",
    headers=headers,
    json=payload
)

print("HTTP Status:", response.status_code)
print(response.text)