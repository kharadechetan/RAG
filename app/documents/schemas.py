from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DocumentUploadResponse(BaseModel):
    document_id: str
    thread_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str
    ocr_used: bool
    native_pages: int
    ocr_pages: int

class DocumentMetadata(BaseModel):
    document_id: str
    thread_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str
    stage: str = "pending"
    pages_processed: int = 0
    chunks_created: int = 0
    ocr_used: bool
    native_pages: int
    ocr_pages: int
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

class DocumentListResponse(BaseModel):
    documents: List[DocumentMetadata]

class DocumentDeleteResponse(BaseModel):
    success: bool
    document_id: str
    thread_id: str

class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    stage: str
    pages_processed: int
    ocr_pages: int
    chunks_created: int
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]

class DocumentMultipleUploadResponse(BaseModel):
    thread_id: str
    documents: List[DocumentUploadResponse]
