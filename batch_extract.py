import os
import json
import base64
import csv
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()
client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))

INPUT_FOLDER = "invoices"
OUTPUT_CSV = "all_invoices.csv"

def normalize_date(date_str):
    """Convert any date string to YYYY-MM-DD. Returns None if unparseable."""
    if not date_str or str(date_str).lower() in ("null", "none", ""):
        return None
    date_str = str(date_str).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    if re.match(r"^\d{1,2}\.\d{1,2}\.\d{4}$", date_str):
        parts = date_str.split(".")
        day, month, year = parts[0], parts[1], parts[2]
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", date_str):
        month, day, year = date_str.split("/")
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    for fmt in ["%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

os.makedirs(INPUT_FOLDER, exist_ok=True)

pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".pdf")]
if not pdf_files:
    print(f"❌ No PDFs found in ./{INPUT_FOLDER}/")
    exit(1)

print(f"📁 Found {len(pdf_files)} PDF(s)\n")

all_records = []
failed = []

for pdf_name in pdf_files:
    print(f"🔍 Processing: {pdf_name}...")
    file_path = os.path.join(INPUT_FOLDER, pdf_name)
    
    try:
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        
        ocr = client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": f"data:application/pdf;base64,{b64}"}
        )
        raw_text = "\n\n".join([p.markdown for p in ocr.pages])
        print(f"   ✅ OCR done ({len(raw_text)} chars)")
        
        time.sleep(2)
        
        chat = client.chat.complete(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": """Extract invoice/receipt data as JSON.
Fields: vendor_name, vendor_address, invoice_number, invoice_date, due_date, total_amount (number), currency (3-letter code), line_items (array: description, quantity, unit_price, total_price).
Use null for missing fields. Return ONLY raw JSON."""},
                {"role": "user", "content": f"Document:\n\n{raw_text}"}
            ],
            response_format={"type": "json_object"}
        )
        
        data = json.loads(chat.choices[0].message.content)
        data["source_file"] = pdf_name
        all_records.append(data)
        print(f"   ✅ {data.get('vendor_name', 'Unknown')} — {data.get('currency', '???')} {data.get('total_amount', 'N/A')}")
        
        time.sleep(2)
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        failed.append(pdf_name)

csv_rows = []
for record in all_records:
    base = {
        "source_file": record.get("source_file", ""),
        "vendor_name": record.get("vendor_name", ""),
        "vendor_address": record.get("vendor_address", ""),
        "invoice_number": record.get("invoice_number", ""),
        "invoice_date": normalize_date(record.get("invoice_date", "")),
        "due_date": normalize_date(record.get("due_date", "")),
        "total_amount": record.get("total_amount", ""),
        "currency": record.get("currency", ""),
    }
    items = record.get("line_items", [])
    if items:
        for item in items:
            row = {**base, **item}
            csv_rows.append(row)
    else:
        csv_rows.append(base)

if csv_rows:
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:  # BOM for Excel
        writer = csv.DictWriter(f, fieldnames=[
            "source_file", "vendor_name", "vendor_address", "invoice_number",
            "invoice_date", "due_date", "total_amount", "currency",
            "description", "quantity", "unit_price", "total_price"
        ])
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\n💾 Master CSV: {OUTPUT_CSV} ({len(csv_rows)} rows)")

if failed:
    print(f"\n⚠️  Failed ({len(failed)}): {', '.join(failed)}")

print(f"\n🎉 {len(all_records)}/{len(pdf_files)} succeeded.")