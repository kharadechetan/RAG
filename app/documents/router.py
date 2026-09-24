from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from typing import List
import asyncio
import os
import logging

from app.documents.schemas import (
    DocumentUploadResponse, 
    DocumentListResponse, 
    DocumentDeleteResponse, 
    DocumentStatusResponse, 
    DocumentMultipleUploadResponse
)
from app.documents.service import DocumentService
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

document_service = DocumentService()

# ============= CONSTANTS =============
MAX_FILES_PER_UPLOAD = 10
ALLOWED_EXTENSIONS = {'.pdf'}

from typing import Annotated

# ============= UPLOAD ENDPOINT =============
@router.post("/upload", response_model=DocumentMultipleUploadResponse)
async def upload_document(
    thread_id: Annotated[str, Form(...)],
    files: List[UploadFile] = File(...)
):
    """
    Upload one or multiple PDF documents to a thread.
    
    Args:
        thread_id: Thread/conversation identifier (required)
        files: List of PDF files to upload (required, max 10)
    
    Returns:
        DocumentMultipleUploadResponse with status of all uploaded files
    """
    
    # ===== VALIDATION: thread_id =====
    if not thread_id or not thread_id.strip():
        logger.warning("Upload attempted with empty thread_id")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id cannot be empty"
        )
    
    thread_id = thread_id.strip()
    
    # ===== VALIDATION: files list =====
    if not files or len(files) == 0:
        logger.warning(f"Upload attempt for thread {thread_id} with no files")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided. Please upload at least one file."
        )
    
    if len(files) > MAX_FILES_PER_UPLOAD:
        logger.warning(f"Upload attempt for thread {thread_id} with {len(files)} files (max {MAX_FILES_PER_UPLOAD})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_FILES_PER_UPLOAD} files allowed per upload. Got {len(files)} files."
        )
    
    valid_files = []
    validation_errors = []
    
    # ===== STEP 1: Validate each file =====
    for file in files:
        error_msg = None
        
        # Check filename exists
        if not file.filename or not file.filename.strip():
            error_msg = "Filename is empty"
            validation_errors.append({"filename": "unknown", "error": error_msg})
            logger.warning(f"Thread {thread_id}: Empty filename in upload")
            continue
        
        # Check file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            error_msg = f"Unsupported file format. Only PDF files are allowed. Got: {file_ext}"
            validation_errors.append({"filename": file.filename, "error": error_msg})
            logger.warning(f"Thread {thread_id}: Invalid file type {file_ext} for {file.filename}")
            continue
        
        # Read file bytes
        try:
            file_bytes = await file.read()
        except Exception as e:
            error_msg = f"Failed to read file: {str(e)}"
            validation_errors.append({"filename": file.filename, "error": error_msg})
            logger.error(f"Thread {thread_id}: Error reading file {file.filename}: {e}")
            continue
        
        # Check file is not empty
        if len(file_bytes) == 0:
            error_msg = "File is empty"
            validation_errors.append({"filename": file.filename, "error": error_msg})
            logger.warning(f"Thread {thread_id}: Empty file {file.filename}")
            continue
        
        # Check file size
        file_size_mb = len(file_bytes) / (1024 * 1024)
        if file_size_mb > settings.max_document_size_mb:
            error_msg = f"File size {file_size_mb:.2f}MB exceeds limit of {settings.max_document_size_mb}MB"
            validation_errors.append({"filename": file.filename, "error": error_msg})
            logger.warning(f"Thread {thread_id}: File too large {file.filename} ({file_size_mb:.2f}MB)")
            continue
        
        # All validations passed
        valid_files.append((file.filename, file_bytes))
        logger.info(f"Thread {thread_id}: File {file.filename} validated ({file_size_mb:.2f}MB)")
    
    # ===== VALIDATION: At least one valid file =====
    if not valid_files:
        error_detail = f"No valid files to process. Validation errors: {validation_errors}"
        logger.warning(f"Thread {thread_id}: No valid files after validation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_detail
        )
    
    # ===== STEP 2: Process valid files concurrently =====
    docs_res = []
    
    try:
        logger.info(f"Thread {thread_id}: Processing {len(valid_files)} valid file(s)")
        
        # Create async tasks for all valid files
        tasks = [
            document_service.process_document(file_bytes, filename, thread_id)
            for filename, file_bytes in valid_files
        ]
        
        # Execute all tasks concurrently with gather
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process responses
        for i, res in enumerate(responses):
            filename, _ = valid_files[i]
            
            if isinstance(res, Exception):
                # Failed processing
                error_str = str(res)
                logger.error(f"Thread {thread_id}: Processing failed for {filename}: {error_str}")
                
                docs_res.append(DocumentUploadResponse(
                    document_id="error",
                    thread_id=thread_id,
                    filename=filename,
                    page_count=0,
                    chunk_count=0,
                    status=f"failed: {error_str}",
                    ocr_used=False,
                    native_pages=0,
                    ocr_pages=0
                ))
            else:
                # Successful processing - response should be DocumentUploadResponse
                if isinstance(res, DocumentUploadResponse):
                    docs_res.append(res)
                    logger.info(f"Thread {thread_id}: Successfully processed {filename}")
                else:
                    # Handle unexpected response type
                    logger.error(f"Thread {thread_id}: Unexpected response type for {filename}")
                    docs_res.append(DocumentUploadResponse(
                        document_id="error",
                        thread_id=thread_id,
                        filename=filename,
                        page_count=0,
                        chunk_count=0,
                        status="failed: Unexpected response type from service",
                        ocr_used=False,
                        native_pages=0,
                        ocr_pages=0
                    ))
        
        # Add validation errors as failed responses
        for error in validation_errors:
            docs_res.append(DocumentUploadResponse(
                document_id="error",
                thread_id=thread_id,
                filename=error["filename"],
                page_count=0,
                chunk_count=0,
                status=f"validation_failed: {error['error']}",
                ocr_used=False,
                native_pages=0,
                ocr_pages=0
            ))
        
        logger.info(f"Thread {thread_id}: Upload completed with {len(docs_res)} results")
        return DocumentMultipleUploadResponse(thread_id=thread_id, documents=docs_res)
        
    except Exception as e:
        logger.error(f"Thread {thread_id}: Unexpected error during upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing documents: {str(e)}"
        )


# ============= LIST DOCUMENTS ENDPOINT =============
@router.get("", response_model=DocumentListResponse)
async def list_documents(thread_id: str):
    """
    List all documents for a given thread.
    
    Args:
        thread_id: Thread identifier (required)
    
    Returns:
        DocumentListResponse with list of documents
    """
    
    if not thread_id or not thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id cannot be empty"
        )
    
    try:
        docs = document_service.get_documents(thread_id)
        logger.info(f"Listed {len(docs)} documents for thread {thread_id}")
        return DocumentListResponse(documents=docs)
    except Exception as e:
        logger.error(f"Error listing documents for thread {thread_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving documents"
        )


# ============= DELETE DOCUMENT ENDPOINT =============
@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str, thread_id: str):
    """
    Delete a document from a thread.
    
    Args:
        document_id: Document identifier (required)
        thread_id: Thread identifier (required)
    
    Returns:
        DocumentDeleteResponse with success status
    """
    
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id cannot be empty"
        )
    
    if not thread_id or not thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id cannot be empty"
        )
    
    try:
        success = document_service.delete_document(document_id, thread_id)
        
        if not success:
            logger.warning(f"Document {document_id} not found in thread {thread_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(f"Deleted document {document_id} from thread {thread_id}")
        return DocumentDeleteResponse(
            success=True,
            document_id=document_id,
            thread_id=thread_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting document"
        )


# ============= GET DOCUMENT STATUS ENDPOINT =============
@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str, thread_id: str):
    """
    Get detailed status of a document.
    
    Args:
        document_id: Document identifier (required)
        thread_id: Thread identifier (required)
    
    Returns:
        DocumentStatusResponse with detailed status information
    """
    
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id cannot be empty"
        )
    
    if not thread_id or not thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id cannot be empty"
        )
    
    try:
        doc = document_service.metadata_store.get_by_id(document_id, thread_id)
        
        if not doc:
            logger.warning(f"Document {document_id} not found in thread {thread_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        logger.info(f"Retrieved status for document {document_id}")
        return DocumentStatusResponse(
            document_id=doc.document_id,
            filename=doc.filename,
            status=doc.status,
            stage=doc.stage,
            pages_processed=doc.pages_processed,
            ocr_pages=doc.ocr_pages,
            chunks_created=doc.chunks_created,
            started_at=doc.started_at,
            completed_at=doc.completed_at,
            error=doc.error
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving document status"
        )


# ============= DOWNLOAD DOCUMENT ENDPOINT =============
@router.get("/{document_id}/download")
async def download_document(document_id: str, thread_id: str):
    """
    Download a document file.
    
    Args:
        document_id: Document identifier (required)
        thread_id: Thread identifier (required)
    
    Returns:
        FileResponse with the document file
    """
    
    if not document_id or not document_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="document_id cannot be empty"
        )
    
    if not thread_id or not thread_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="thread_id cannot be empty"
        )
    
    try:
        # Verify document exists and user has access
        doc = document_service.metadata_store.get_by_id(document_id, thread_id)
        
        if not doc:
            logger.warning(f"Download attempted for non-existent document {document_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found or unauthorized access"
            )
        
        # Locate the file on disk
        file_path = None
        allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]
        
        for ext in allowed_extensions:
            potential_path = os.path.join(settings.uploads_dir, f"{document_id}{ext}")
            if os.path.exists(potential_path) and os.path.isfile(potential_path):
                file_path = potential_path
                break
        
        if not file_path:
            logger.error(f"File missing on disk for document {document_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File missing on disk"
            )
        
        # Security: Verify path is within uploads directory
        real_path = os.path.realpath(file_path)
        real_uploads_dir = os.path.realpath(settings.uploads_dir)
        
        if not real_path.startswith(real_uploads_dir):
            logger.error(f"Security: Path traversal attempt for document {document_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        logger.info(f"Downloading document {document_id} from thread {thread_id}")
        
        import mimetypes
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

        return FileResponse(
            file_path,
            filename=doc.filename,
            media_type=content_type,
            content_disposition_type="inline"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading document"
        )