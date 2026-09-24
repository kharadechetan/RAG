import os
import requests
import time
import uuid

API_URL = "http://127.0.0.1:8000"

def test_health():
    try:
        r = requests.get(f"{API_URL}/health")
        print(f"Health status: {r.status_code}")
        print(f"Health response: {r.text}")
    except Exception as e:
        print(f"Health failed: {e}")

def test_upload(filepath="test_doc.pdf"):
    if not os.path.exists(filepath):
        print(f"File {filepath} not found for upload test.")
        return None
    thread_id = str(uuid.uuid4())
    print(f"Testing upload for {filepath} with thread {thread_id}")
    with open(filepath, "rb") as f:
        r = requests.post(f"{API_URL}/documents/upload", files={"file": f}, data={"thread_id": thread_id})
    print(f"Upload status: {r.status_code}")
    print(f"Upload response: {r.text}")
    return thread_id

if __name__ == "__main__":
    test_health()
    print("Testing upload of test_doc.pdf (if exists)")
    thread_id = test_upload()
    if thread_id:
        print("Wait a bit for processing...")
        time.sleep(3)
        print("Testing Thread Isolation (sending message to thread)")
        r = requests.post(f"{API_URL}/messages/stream", json={"thread_id": thread_id, "message": "What is in the document?"}, stream=True)
        print("Stream response:")
        print(r.status_code)
        # Just grab the last chunks
        lines = [line for line in r.iter_lines() if line]
        for l in lines[-5:]:
            print(l)
