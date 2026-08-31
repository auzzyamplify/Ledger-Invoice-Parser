import os
import json
import base64
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()
api_key = os.environ.get("MISTRAL_API_KEY")
client = Mistral(api_key=api_key)

file_path = "invoice.pdf"

if not os.path.exists(file_path):
    print(f"❌ File not found: {file_path}")
    exit(1)

print(f"📄 Reading {file_path}...")

with open(file_path, "rb") as f:
    pdf_bytes = f.read()

base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
document_url = f"data:application/pdf;base64,{base64_pdf}"

# --- STEP 1: OCR the PDF ---
print("🔍 Running OCR...")
ocr_response = client.ocr.process(
    model="mistral-ocr-latest",
    document={"type": "document_url", "document_url": document_url}
)

raw_text = "\n\n".join([page.markdown for page in ocr_response.pages])
print(f"✅ OCR complete. {len(raw_text)} characters extracted.")

# --- STEP 2: Extract structured data with an LLM ---
print("🧠 Extracting structured invoice data...")

system_prompt = """You are an expert invoice parser. Extract the following fields from the invoice text and return ONLY a valid JSON object. No markdown, no explanation, just raw JSON.

Required fields:
- vendor_name (string)
- vendor_address (string, or null if not found)
- invoice_number (string)
- invoice_date (YYYY-MM-DD format, or null)
- due_date (YYYY-MM-DD format, or null)
- total_amount (number, no currency symbols)
- currency (3-letter code like USD, EUR, GBP, or null)
- line_items (array of objects, each with: description, quantity, unit_price, total_price)

If a field is missing, use null. If line items are unclear, do your best."""
    
chat_response = client.chat.complete(
    model="mistral-small-latest",  # was mistral-large-latest
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Parse this invoice text into JSON:\n\n{raw_text}"}
    ],
    response_format={"type": "json_object"}
)

structured_data = json.loads(chat_response.choices[0].message.content)

# --- STEP 3: Display and save ---
print("\n" + "="*60)
print("EXTRACTED STRUCTURED DATA:")
print("="*60)
print(json.dumps(structured_data, indent=2))

# Save as JSON
with open("invoice_data.json", "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=2)

# Save as CSV (just line items for now)
import csv
if structured_data.get("line_items"):
    with open("invoice_line_items.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["description", "quantity", "unit_price", "total_price"])
        writer.writeheader()
        writer.writerows(structured_data["line_items"])
    print(f"\n💾 Line items saved to: invoice_line_items.csv")

print(f"💾 Full data saved to: invoice_data.json")
print("\n🎉 Done. You now have structured invoice data.")