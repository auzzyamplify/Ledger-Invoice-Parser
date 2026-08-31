import os
import base64
from dotenv import load_dotenv
from mistralai.client import Mistral

# Load API key from .env file
load_dotenv()

api_key = os.environ.get("MISTRAL_API_KEY")
if not api_key:
    raise ValueError("MISTRAL_API_KEY not found. Make sure your .env file is set up.")

client = Mistral(api_key=api_key)

# --- STEP 1: Read the PDF and encode as base64 ---
file_path = "invoice.pdf"

if not os.path.exists(file_path):
    print(f"❌ File not found: {file_path}")
    print("   → Put a PDF named 'invoice.pdf' in this folder and run again.")
    exit(1)

print(f"📄 Reading {file_path}...")

with open(file_path, "rb") as f:
    pdf_bytes = f.read()

base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
document_url = f"data:application/pdf;base64,{base64_pdf}"

print(f"✅ Encoded {len(pdf_bytes):,} bytes. Sending to Mistral OCR...")

# --- STEP 2: Run OCR directly (no upload needed) ---
ocr_response = client.ocr.process(
    model="mistral-ocr-latest",
    document={
        "type": "document_url",
        "document_url": document_url
    }
)

# --- STEP 3: Print the result ---
print("\n" + "="*60)
print("EXTRACTED TEXT (Markdown format):")
print("="*60 + "\n")

for page in ocr_response.pages:
    print(page.markdown)
    print("\n---\n")

# --- STEP 4: Save to a file ---
output_path = "extracted_text.md"
with open(output_path, "w", encoding="utf-8") as out:
    for page in ocr_response.pages:
        out.write(page.markdown + "\n\n")

print(f"💾 Saved to: {output_path}")
print(f"\n🎉 Done! Processed {len(ocr_response.pages)} page(s).")