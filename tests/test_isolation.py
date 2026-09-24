import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

def test_thread_isolation(client):
    # Create two distinct threads
    thread_a = client.post("/threads").json()["thread_id"]
    thread_b = client.post("/threads").json()["thread_id"]

    # Thread A sets context
    res_a1 = client.post(
        "/messages/stream", 
        json={"thread_id": thread_a, "message": "My name is John."},
    )
    for _ in res_a1.iter_bytes():
        pass # Consume stream

    # Thread B asks for name
    res_b1 = client.post(
        "/messages/stream", 
        json={"thread_id": thread_b, "message": "What is my name?"},
    )
    b_response = ""
    for chunk in res_b1.iter_bytes():
        if chunk:
            b_response += chunk.decode("utf-8")
    
    # B should NOT know the name
    assert "John" not in b_response

    # Thread A asks for name
    res_a2 = client.post(
        "/messages/stream", 
        json={"thread_id": thread_a, "message": "What is my name?"},
    )
    a_response = ""
    for chunk in res_a2.iter_bytes():
        if chunk:
            a_response += chunk.decode("utf-8")
    
    # A SHOULD know the name
    assert "John" in a_response
