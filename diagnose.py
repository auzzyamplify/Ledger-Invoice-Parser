import os
import base64
import time
from dotenv import load_dotenv
from mistralai.client import Mistral

load_dotenv()
client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))

print("=" * 50)
print("TEST 1: List available models")
print("=" * 50)
try:
    models = client.models.list()
    model_ids = [m.id for m in models.data]
    print(f"✅ Success. You have access to {len(model_ids)} models.")
    for m in ["mistral-ocr-latest", "mistral-large-latest", "mistral-small-latest"]:
        status = "✅" if m in model_ids else "❌"
        print(f"   {status} {m}")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "=" * 50)
print("TEST 2: OCR a tiny PDF")
print("=" * 50)
try:
    # Create a minimal test: a 1-page blank PDF encoded as base64
    # This is a valid minimal PDF structure
    minimal_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000214 00000 n \ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n308\n%%EOF"
    
    b64 = base64.b64encode(minimal_pdf).decode("utf-8")
    ocr = client.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "document_url", "document_url": f"data:application/pdf;base64,{b64}"}
    )
    print(f"✅ OCR works. Extracted {len(ocr.pages)} page(s).")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "=" * 50)
print("TEST 3: Chat completion (cheap model)")
print("=" * 50)
try:
    chat = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=10
    )
    print(f"✅ Small model works. Response: {chat.choices[0].message.content}")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "=" * 50)
print("TEST 4: Chat completion (large model)")
print("=" * 50)
time.sleep(2)  # Respect rate limit
try:
    chat = client.chat.complete(
        model="mistral-large-latest",
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=10
    )
    print(f"✅ Large model works. Response: {chat.choices[0].message.content}")
except Exception as e:
    print(f"❌ Failed: {e}")

print("\n" + "=" * 50)
print("TEST 5: Chat with JSON mode")
print("=" * 50)
time.sleep(2)
try:
    chat = client.chat.complete(
        model="mistral-small-latest",
        messages=[{"role": "user", "content": "Return JSON: {'status': 'ok'}"}],
        response_format={"type": "json_object"},
        max_tokens=50
    )
    print(f"✅ JSON mode works. Response: {chat.choices[0].message.content}")
except Exception as e:
    print(f"❌ Failed: {e}")