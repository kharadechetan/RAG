import httpx
import json
from fpdf import FPDF
import time

API_URL = "http://localhost:8000"

def generate_pdf(filename, text, pages=1):
    pdf = FPDF()
    for _ in range(pages):
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt=text)
    pdf.output(filename)

def run_tests():
    print("Testing TC-001 / TC-002: Health")
    try:
        r = httpx.get(f"{API_URL}/health")
        print(f"Health: {r.status_code}")
    except Exception as e:
        print(f"Health error: {e}")
        
    print("\nCreating thread...")
    r = httpx.post(f"{API_URL}/threads")
    if r.status_code != 201:
        print(f"Thread creation failed: {r.text}")
        return
    thread_id = r.json()["thread_id"]
    print(f"Thread: {thread_id}")
    
    print("\nGenerating and uploading PDF...")
    generate_pdf("test_doc.pdf", "The company revenue in 2024 was $5 million.", pages=2)
    with open("test_doc.pdf", "rb") as f:
        r = httpx.post(f"{API_URL}/documents/upload", data={"thread_id": thread_id}, files={"files": f}, timeout=None)
        print(f"Upload: {r.status_code} {r.text}")

    print("\nTesting Query...")
    with httpx.stream("POST", f"{API_URL}/messages/stream", json={"thread_id": thread_id, "message": "What is the revenue?"}, timeout=None) as r:
        for chunk in r.iter_text():
            print(chunk, end="", flush=True)
    print("\n")

if __name__ == "__main__":
    run_tests()
