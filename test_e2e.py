import os
import time
import requests

BASE_URL = "http://127.0.0.1:8000"
THREAD_ID = "test-thread-123"

def create_thread():
    print("Creating thread...")
    url = f"{BASE_URL}/threads"
    resp = requests.post(url)
    if resp.status_code == 201:
        thread_id = resp.json().get("thread_id")
        print(f"Thread created: {thread_id}")
        return thread_id
    else:
        print(f"Failed to create thread: {resp.text}")
        return None

def test_upload(filepath, thread_id):
    print(f"Uploading {filepath}...")
    url = f"{BASE_URL}/documents/upload"
    with open(filepath, "rb") as f:
        files = {"files": (os.path.basename(filepath), f, "application/pdf")}
        data = {"thread_id": thread_id}
        
        t0 = time.time()
        resp = requests.post(url, files=files, data=data)
        t1 = time.time()
        
    print(f"Upload Status: {resp.status_code}")
    if resp.status_code == 200:
        docs = resp.json().get("documents", [])
        if docs:
            doc_id = docs[0].get("document_id")
            print(f"Document ID: {doc_id} - Time: {t1-t0:.2f}s")
            return doc_id
    else:
        print(f"Response: {resp.text}")
    return None

def test_query(question, thread_id):
    print(f"\nQuerying: {question}")
    url = f"{BASE_URL}/messages/stream"
    payload = {
        "thread_id": thread_id,
        "message": question
    }
    t0 = time.time()
    resp = requests.post(url, json=payload, stream=True)
    t1 = time.time()
    
    print(f"Query Status: {resp.status_code} - Time: {t1-t0:.2f}s")
    if resp.status_code == 200:
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            print(chunk, end="")
        print("\n")
    else:
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    thread_id = create_thread()
    if thread_id:
        pdf_path = r"b:\navgurukul\chatbot\test_data\small_test.pdf"
        doc_id = test_upload(pdf_path, thread_id)
        if doc_id:
            test_query("What is this document about? Tell me a summary.", thread_id)
