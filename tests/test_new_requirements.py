import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.documents.schemas import DocumentMetadata
from app.documents.service import DocumentService

document_service = DocumentService()

client = TestClient(app)

def test_metrics_endpoint():
    # If metrics are enabled, the endpoint should be reachable
    if settings.enable_metrics:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"rag_requests" in response.content or b"python_info" in response.content
        
def test_document_status_endpoint():
    # Insert a dummy metadata manually
    doc_id = "test-doc-123"
    thread_id = "test-thread-123"
    meta = DocumentMetadata(
        document_id=doc_id,
        thread_id=thread_id,
        filename="test.pdf",
        page_count=10,
        chunk_count=50,
        status="completed",
        stage="vector_store",
        pages_processed=10,
        chunks_created=50,
        ocr_used=False,
        native_pages=10,
        ocr_pages=0,
        created_at="2026-09-24T00:00:00Z",
        updated_at="2026-09-24T00:00:00Z"
    )
    document_service.metadata_store.save_metadata(meta)
    
    # Hit the status API
    response = client.get(f"/documents/{doc_id}/status?thread_id={thread_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["stage"] == "vector_store"
    assert data["pages_processed"] == 10
    
    # Cleanup
    document_service.metadata_store.delete_metadata(doc_id, thread_id)

def test_status_endpoint_not_found():
    response = client.get("/documents/non-existent/status?thread_id=non-existent")
    assert response.status_code == 404

def test_reranker_toggle():
    from app.graph.nodes import get_reranker
    # Temporarily override setting
    original_setting = settings.enable_reranking
    
    try:
        settings.enable_reranking = False
        reranker = get_reranker()
        assert reranker is None or reranker is False
    finally:
        settings.enable_reranking = original_setting

@pytest.mark.asyncio
async def test_concurrent_ocr_mock():
    # Ensure it's imported without error
    from app.documents.service import DocumentService
    srv = DocumentService()
    assert srv.extractor is not None
    assert srv.ocr_client is not None
