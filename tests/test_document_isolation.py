import pytest
from app.documents.schemas import DocumentMetadata
from app.documents.service import DocumentService
from app.documents.vectorstore.chroma import chroma_store
import uuid

@pytest.fixture
def document_service():
    return DocumentService()

@pytest.mark.asyncio
async def test_document_isolation(document_service):
    thread_a = f"thread-a-{uuid.uuid4()}"
    thread_b = f"thread-b-{uuid.uuid4()}"
    
    # 1. Simulate Upload via Service
    dummy_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 21 >>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    
    res_a1 = await document_service.process_pdf(dummy_pdf, "docA1.pdf", thread_a)
    res_a2 = await document_service.process_pdf(dummy_pdf, "docA2.pdf", thread_a)
    res_b1 = await document_service.process_pdf(dummy_pdf, "docB1.pdf", thread_b)

    # 2. Test Listing Isolation
    docs_a = document_service.get_documents(thread_a)
    assert len(docs_a) == 2
    assert all(d.thread_id == thread_a for d in docs_a)

    docs_b = document_service.get_documents(thread_b)
    assert len(docs_b) == 1
    assert docs_b[0].thread_id == thread_b
    assert docs_b[0].document_id == res_b1.document_id

    # 3. Test Cross-Thread Deletion (Fail)
    deleted = document_service.delete_document(res_a1.document_id, thread_b)
    assert deleted is False # Thread B cannot delete Thread A's doc
    
    # Verify it still exists in Chroma for Thread A
    chunks = chroma_store.count_document_chunks(res_a1.document_id, thread_a)
    assert chunks > 0

    # 4. Test Correct Deletion
    deleted = document_service.delete_document(res_a1.document_id, thread_a)
    assert deleted is True

    # Verify it is gone from Chroma
    chunks = chroma_store.count_document_chunks(res_a1.document_id, thread_a)
    assert chunks == 0

    # Verify metadata is gone
    docs_a_after = document_service.get_documents(thread_a)
    assert len(docs_a_after) == 1
    assert docs_a_after[0].document_id == res_a2.document_id
    
    # 5. Clean up others
    document_service.delete_document(res_a2.document_id, thread_a)
    document_service.delete_document(res_b1.document_id, thread_b)
