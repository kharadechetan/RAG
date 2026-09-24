import pytest
from fastapi.testclient import TestClient
import os
import glob
from app.main import app
import time

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

def test_multiple_upload_and_retrieval(client):
    # Create thread
    thread_res = client.post("/threads")
    assert thread_res.status_code == 200
    thread_id = thread_res.json()["thread_id"]

    # Get multi_pdf files
    pdf_files = glob.glob("test_data/multi_pdf/*.pdf")
    assert len(pdf_files) == 10, f"Expected 10 PDFs, got {len(pdf_files)}"

    files_to_upload = [
        ("files", (os.path.basename(f), open(f, "rb"), "application/pdf")) for f in pdf_files
    ]
    
    start_time = time.time()
    res = client.post(
        "/documents/upload",
        data={"thread_id": thread_id},
        files=files_to_upload
    )
    assert res.status_code == 200, res.text
    
    upload_time = time.time() - start_time
    print(f"Total multiple ingestion time: {upload_time:.2f}s")
    
    # Check responses
    res_data = res.json()
    assert len(res_data["documents"]) == 10
    for doc in res_data["documents"]:
        assert doc["status"] == "completed"
        assert doc["chunk_count"] > 0
        assert doc["page_count"] > 0

    # Retrieve and check answers (isolation and citation test)
    questions = [
        ("What is the capital of Atlantis?", "Posidonis"),
        ("When was Project Bluebook closed?", "1969"),
        ("What is the maximum speed of a laden swallow?", "24"),
    ]

    for q, a in questions:
        res_q = client.post(
            "/messages/stream", 
            json={"thread_id": thread_id, "message": q},
        )
        assert res_q.status_code == 200
        
        chunks = []
        for chunk in res_q.iter_bytes():
            if chunk:
                chunks.append(chunk.decode("utf-8"))
        
        full_response = "".join(chunks)
        assert a.lower() in full_response.lower(), f"Expected '{a}' in response, got: {full_response}"

def test_large_pdf_upload(client):
    # Create thread
    thread_res = client.post("/threads")
    thread_id = thread_res.json()["thread_id"]

    large_pdf = "test_data/large_pdf/large_doc.pdf"
    assert os.path.exists(large_pdf)
    
    start_time = time.time()
    res = client.post(
        "/documents/upload",
        data={"thread_id": thread_id},
        files=[("files", (os.path.basename(large_pdf), open(large_pdf, "rb"), "application/pdf"))]
    )
    assert res.status_code == 200, res.text
    upload_time = time.time() - start_time
    
    docs = res.json()["documents"]
    doc = docs[0]
    assert doc["status"] == "completed"
    assert doc["page_count"] == 210
    print(f"Large PDF processing time: {upload_time:.2f}s")
    
    # Retrieve answer
    res_q = client.post(
        "/messages/stream", 
        json={"thread_id": thread_id, "message": "What is the core temperature of the sun?"},
    )
    chunks = []
    for chunk in res_q.iter_bytes():
        if chunk:
            chunks.append(chunk.decode("utf-8"))
    
    full_response = "".join(chunks)
    assert "15 million" in full_response.lower()

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"
