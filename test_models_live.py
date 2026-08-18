import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

models_to_test = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest"
]

for m in models_to_test:
    try:
        resp = client.models.generate_content(
            model=m,
            contents="Hello! Output 'OK'"
        )
        print(f"[+] SUCCESS: {m} -> {resp.text.strip()}")
        break
    except Exception as e:
        print(f"[-] FAILED: {m} -> {e}")
