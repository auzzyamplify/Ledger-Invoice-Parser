import os
import json
import base64
import io
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from mistralai.client import Mistral
import streamlit as st

load_dotenv()
api_key = st.secrets.get("MISTRAL_API_KEY") or os.environ.get("MISTRAL_API_KEY")
if not api_key:
    st.error("MISTRAL_API_KEY not found. Add it to Streamlit secrets.")
    st.stop()
client = Mistral(api_key=api_key)

st.set_page_config(page_title="Invoice Parser", layout="wide")
st.title("📄 Invoice Parser")
st.markdown("Drag and drop PDF invoices. Get structured data in seconds.")

def normalize_date(date_str):
    if not date_str or str(date_str).lower() in ("null", "none", ""):
        return None
    date_str = str(date_str).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    if re.match(r"^\d{1,2}\.\d{1,2}\.\d{4}$", date_str):
        day, month, year = date_str.split(".")
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

def process_single_invoice(pdf_bytes, filename):
    """Process one invoice: OCR + extraction."""
    try:
        b64 = base64.b64encode(pdf_bytes).decode("utf-8")
        
        ocr = client.ocr.process(
            model="mistral-ocr-latest",
            document={"type": "document_url", "document_url": f"data:application/pdf;base64,{b64}"}
        )
        raw_text = "\n\n".join([p.markdown for p in ocr.pages])
        
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
        data["source_file"] = filename
        return {"status": "success", "data": data}
        
    except Exception as e:
        return {"status": "error", "filename": filename, "error": str(e)}

# File uploader
uploaded_files = st.file_uploader("Upload PDF invoices", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    all_records = []
    errors = []
    
    # Progress bar
    progress_text = st.empty()
    progress_bar = st.progress(0)
    progress_text.text(f"Processing 0/{len(uploaded_files)} invoices...")
    
    # Process all invoices in parallel using threads
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all jobs
        future_to_file = {
            executor.submit(process_single_invoice, uf.read(), uf.name): uf.name 
            for uf in uploaded_files
        }
        
        completed = 0
        for future in as_completed(future_to_file):
            filename = future_to_file[future]
            result = future.result()
            completed += 1
            
            progress_bar.progress(completed / len(uploaded_files))
            progress_text.text(f"Processing {completed}/{len(uploaded_files)} invoices...")
            
            if result["status"] == "success":
                all_records.append(result["data"])
                st.success(f"✅ {result['data'].get('vendor_name', 'Unknown')} — {result['data'].get('currency', '???')} {result['data'].get('total_amount', 'N/A')}")
            else:
                errors.append(result)
                st.error(f"❌ {filename}: {result['error']}")
    
    progress_text.empty()
    progress_bar.empty()
    
    # Show results
    if all_records:
        import pandas as pd
        
        csv_rows = []
        for record in all_records:
            base = {
                "source_file": record.get("source_file", ""),
                "vendor_name": record.get("vendor_name", ""),
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
        
        df = pd.DataFrame(csv_rows)
        
        st.subheader("Extracted Data")
        st.dataframe(df, use_container_width=True)
        
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 Download CSV",
            data=csv_buffer.getvalue(),
            file_name="parsed_invoices.csv",
            mime="text/csv"
        )
        
        with st.expander("View Raw JSON"):
            for record in all_records:
                st.json(record)
    
    if errors:
        st.warning(f"{len(errors)} invoice(s) failed to process.")