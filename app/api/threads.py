import uuid
from fastapi import APIRouter, HTTPException, status
from app.database.threads import (
    create_thread_metadata,
    list_threads_metadata,
    get_thread_metadata,
    delete_thread_metadata
)
from app.schemas.thread import ThreadResponse, ThreadDeleteResponse
from app.schemas.message import MessageResponse
from app.database.mongodb import db_store
from app.documents.vectorstore.chroma import chroma_store
from app.documents.metadata.store import document_metadata_store
import os
from app.config import settings

router = APIRouter()

@router.post("/threads", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def create_thread():
    thread_id = str(uuid.uuid4())
    metadata = create_thread_metadata(thread_id)
    return ThreadResponse(**metadata)

@router.get("/threads")
async def list_threads():
    threads = list_threads_metadata()
    return {"threads": threads}

@router.get("/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    metadata = get_thread_metadata(thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    config = {"configurable": {"thread_id": thread_id}}
    state = db_store.checkpointer.get(config)
    
    if not state or "messages" not in state["channel_values"]:
        return {"thread_id": thread_id, "messages": []}
        
    messages = state["channel_values"]["messages"]
    
    history = []
    for msg in messages:
        if msg.type in ["human", "ai", "user", "assistant"]:
            role = "user" if msg.type in ["human", "user"] else "assistant"
            history.append(MessageResponse(role=role, content=msg.content))
            
    return {"thread_id": thread_id, "messages": history}

@router.delete("/threads/{thread_id}", response_model=ThreadDeleteResponse)
async def delete_thread(thread_id: str):
    metadata = get_thread_metadata(thread_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Clean up Chroma embeddings for all documents in this thread
    chroma_store.delete_thread_documents(thread_id)

    # Clean up document metadata and physical files for this thread
    for doc in document_metadata_store.get_by_thread(thread_id):
        # Delete physical file
        file_path = os.path.join(settings.uploads_dir, f"{doc.document_id}.pdf")
        if os.path.exists(file_path):
            os.remove(file_path)
            
        document_metadata_store.delete_metadata(doc.document_id, thread_id)

    # Clean up MongoDB (thread metadata + LangGraph checkpoints)
    delete_thread_metadata(thread_id)
    return ThreadDeleteResponse(success=True, thread_id=thread_id)
