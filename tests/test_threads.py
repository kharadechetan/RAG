import pytest
from fastapi.testclient import TestClient
from app.main import app

# We use TestClient as a context manager so lifespan events run
@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client

def test_create_thread(client):
    response = client.post("/threads")
    assert response.status_code == 201
    data = response.json()
    assert "thread_id" in data
    assert "created_at" in data
    assert "updated_at" in data

def test_list_threads(client):
    client.post("/threads")
    response = client.get("/threads")
    assert response.status_code == 200
    data = response.json()
    assert "threads" in data
    assert len(data["threads"]) >= 1

def test_delete_thread(client):
    # Create thread
    response = client.post("/threads")
    thread_id = response.json()["thread_id"]

    # Delete thread
    delete_res = client.delete(f"/threads/{thread_id}")
    assert delete_res.status_code == 200
    assert delete_res.json()["success"] is True

    # Get history should return 404
    hist_res = client.get(f"/threads/{thread_id}/history")
    assert hist_res.status_code == 404
