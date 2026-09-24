import os
import uuid
import datetime
import json
from typing import List
from app.config import settings

from app.documents.schemas import DocumentMetadata, DocumentUploadResponse
from app.documents.extraction.pdf_extractor import PyMuPDFExtractor
from app.documents.ocr.local_ocr import LocalPaddleOCRClient
from app.documents.preprocessing.cleaner import TextCleaner
from app.documents.preprocessing.language import LanguageDetector
from app.documents.chunking.chunker import Chunker
from app.embeddings.factory import get_embeddings
from app.documents.vectorstore.chroma import chroma_store
from app.documents.metadata.store import document_metadata_store


class DocumentService:
    def __init__(self):
        self.extractor = PyMuPDFExtractor()
        self.ocr_client = LocalPaddleOCRClient()
        self.cleaner = TextCleaner()
        self.chunker = Chunker()
        self.embedding_model = get_embeddings()
        self.chroma = chroma_store
        self.metadata_store = document_metadata_store

    async def process_document(self, file_bytes: bytes, filename: str, thread_id: str) -> DocumentUploadResponse:
        document_id = str(uuid.uuid4())
        
        # Save file to disk
        ext = os.path.splitext(filename)[1].lower()
        file_path = os.path.join(settings.uploads_dir, f"{document_id}{ext}")
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
        # Tracking metrics
        native_pages_count = 0
        ocr_pages_count = 0
        all_chunks = []
        all_metadatas = []
        
        try:
            # 1. Page-by-page extraction or image processing
            is_pdf = filename.lower().endswith(".pdf")
            if is_pdf:
                pages = list(self.extractor.extract_pages(file_bytes))
            else:
                pages = [{
                    "page_number": 1,
                    "text": "",
                    "image_bytes": file_bytes,
                    "blocks": []
                }]
            import asyncio
            sem = asyncio.Semaphore(settings.ocr_max_concurrency)
            
            async def process_page(page_data):
                nonlocal native_pages_count, ocr_pages_count
                page_num = page_data["page_number"]
                native_text = page_data["text"]
                image_bytes = page_data["image_bytes"]
                blocks = page_data["blocks"]
                
                text_to_process = ""
                source_type = "native"
                
                if len(native_text.strip()) < settings.ocr_text_threshold:
                    async with sem:
                        # Add basic timeout/retry logic internally if ModalOCRClient doesn't have it, but for now just call
                        try:
                            # Using an external tool, we might wrap it in wait_for
                            ocr_result = await asyncio.wait_for(self.ocr_client.extract_text_from_bytes(image_bytes), timeout=settings.ocr_timeout_seconds)
                        except asyncio.TimeoutError:
                            ocr_result = {"success": False}
                        except Exception:
                            ocr_result = {"success": False}
                            
                    if ocr_result.get("success"):
                        text_to_process = ocr_result.get("text", "")
                        source_type = "ocr"
                        ocr_pages_count += 1
                        blocks = [] # OCR doesn't provide bbox natively in this setup
                    else:
                        text_to_process = native_text
                        native_pages_count += 1
                else:
                    text_to_process = native_text
                    native_pages_count += 1
                    
                cleaned_text = self.cleaner.clean(text_to_process)
                if not cleaned_text:
                    return []
                    
                page_lang = LanguageDetector.detect_language(cleaned_text)
                chunks = self.chunker.split_text(cleaned_text)
                
                page_chunks_data = []
                for i, chunk in enumerate(chunks):
                    # Bounding Box mapping
                    matched_bboxes = []
                    chunk_lower = chunk.lower()
                    for b in blocks:
                        b_text = b["text"].strip().lower()
                        if len(b_text) > 5 and b_text[:20] in chunk_lower:
                            matched_bboxes.append(b["bbox"])
                            
                    meta = {
                        "document_id": document_id,
                        "thread_id": thread_id,
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_index": i,
                        "source": source_type,
                        "language": page_lang
                    }
                    if matched_bboxes:
                        meta["bounding_boxes"] = json.dumps(matched_bboxes)
                        
                    page_chunks_data.append({
                        "chunk": chunk,
                        "meta": meta
                    })
                return page_chunks_data

            # Run concurrently
            results = await asyncio.gather(*[process_page(p) for p in pages])
            
            # Flatten results and fix chunk indices
            chunk_global_idx = 0
            for page_res in results:
                for c_data in page_res:
                    c_data["meta"]["chunk_index"] = chunk_global_idx
                    chunk_global_idx += 1
                    all_chunks.append(c_data["chunk"])
                    all_metadatas.append(c_data["meta"])

            # 6. Embedding & Vector Storage (Batched and Concurrent)
            chunk_count = len(all_chunks)
            if chunk_count > 0:
                batch_size = settings.embedding_batch_size
                
                def process_batch(b_chunks, b_metadatas):
                    b_ids = [f"{document_id}_{m['page_number']}_{m['chunk_index']}" for m in b_metadatas]
                    b_embeddings = self.embedding_model.embed_documents(b_chunks)
                    self.chroma.add_chunks(
                        ids=b_ids,
                        documents=b_chunks,
                        embeddings=b_embeddings,
                        metadatas=b_metadatas
                    )
                
                # Create batch tasks
                batch_tasks = []
                for i in range(0, chunk_count, batch_size):
                    batch_chunks = all_chunks[i:i + batch_size]
                    batch_metadatas = all_metadatas[i:i + batch_size]
                    batch_tasks.append(asyncio.to_thread(process_batch, batch_chunks, batch_metadatas))
                
                # Execute max 4 batches concurrently to avoid overwhelming the Embedding API or Chroma SQLite lock
                sem_embed = asyncio.Semaphore(4)
                
                async def sem_task(task):
                    async with sem_embed:
                        return await task
                        
                await asyncio.gather(*(sem_task(t) for t in batch_tasks))

            # 7. Metadata Storage
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            doc_meta = DocumentMetadata(
                document_id=document_id,
                thread_id=thread_id,
                filename=filename,
                page_count=native_pages_count + ocr_pages_count,
                chunk_count=chunk_count,
                status="completed",
                ocr_used=(ocr_pages_count > 0),
                native_pages=native_pages_count,
                ocr_pages=ocr_pages_count,
                created_at=now,
                updated_at=now
            )
            self.metadata_store.save_metadata(doc_meta)
            
            return DocumentUploadResponse(
                document_id=document_id,
                thread_id=thread_id,
                filename=filename,
                page_count=doc_meta.page_count,
                chunk_count=doc_meta.chunk_count,
                status="completed",
                ocr_used=doc_meta.ocr_used,
                native_pages=doc_meta.native_pages,
                ocr_pages=doc_meta.ocr_pages
            )
            
        except Exception as e:
            # Cleanup on failure
            self.chroma.delete_document(document_id, thread_id)
            if os.path.exists(file_path):
                os.remove(file_path)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # Save failed metadata
            failed_meta = DocumentMetadata(
                document_id=document_id,
                thread_id=thread_id,
                filename=filename,
                page_count=native_pages_count + ocr_pages_count,
                chunk_count=0,
                status=f"failed: {str(e)}",
                ocr_used=(ocr_pages_count > 0),
                native_pages=native_pages_count,
                ocr_pages=ocr_pages_count,
                created_at=now,
                updated_at=now
            )
            self.metadata_store.save_metadata(failed_meta)
            raise e

    def get_documents(self, thread_id: str) -> List[DocumentMetadata]:
        return self.metadata_store.get_by_thread(thread_id)

    def delete_document(self, document_id: str, thread_id: str) -> bool:
        # 1. Validate existence and ownership
        doc_meta = self.metadata_store.get_by_id(document_id, thread_id)
        if not doc_meta:
            return False
            
        # 2. Delete from Chroma (removes embeddings too)
        self.chroma.delete_document(document_id, thread_id)
        
        # 3. Verify Chroma deletion
        remaining_chunks = self.chroma.count_document_chunks(document_id, thread_id)
        if remaining_chunks > 0:
            raise RuntimeError(f"Failed to fully delete document from Chroma. {remaining_chunks} chunks remain.")
            
        # 4. Delete the physical file
        # We need to find the file with the right extension
        for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
            file_path = os.path.join(settings.uploads_dir, f"{document_id}{ext}")
            if os.path.exists(file_path):
                os.remove(file_path)
                break
            
        # 5. Remove document metadata
        return self.metadata_store.delete_metadata(document_id, thread_id)
