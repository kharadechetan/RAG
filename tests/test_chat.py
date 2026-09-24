import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

def test_streaming(client):
    # Create a thread
    thread_res = client.post("/threads")
    thread_id = thread_res.json()["thread_id"]

    # Stream a message
    response = client.post(
        "/messages/stream", 
        json={"thread_id": thread_id, "message": "Hi, just say 'pong'."},
        stream=True
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-cache"

    chunks = []
    for chunk in response.iter_bytes():
        if chunk:
            chunks.append(chunk.decode("utf-8"))
    
    # We should have received text
    full_response = "".join(chunks)
    assert len(full_response) > 0
    # And there should be a history
    hist = client.get(f"/threads/{thread_id}/history").json()
    assert len(hist["messages"]) > 0
