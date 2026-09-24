from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
import os

from app.config import settings
from app.database.mongodb import db_store
from app.api.threads import router as threads_router
from app.api.messages import router as messages_router

# Now include documents router
from app.documents.router import router as documents_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db_store.client = MongoClient(settings.mongodb_uri)
    db_store.db = db_store.client[settings.mongodb_database]
    db_store.checkpointer = MongoDBSaver(db_store.client)
    
    # Ensure data dirs exist
    os.makedirs(os.path.dirname(settings.document_metadata_path), exist_ok=True)
    
    # Pre-load Reranker model (if enabled) so it doesn't delay the first question
    if settings.enable_reranking:
        from app.graph.nodes import get_reranker
        print(f"Pre-loading Reranker model: {settings.rerank_model}...")
        get_reranker()
        
    yield
    
    # Shutdown
    if db_store.client:
        db_store.client.close()

app = FastAPI(
    title="RAG Chatbot API",
    version="1.0.0",
    lifespan=lifespan
)

from prometheus_fastapi_instrumentator import Instrumentator
if settings.enable_metrics:
    Instrumentator().instrument(app).expose(app, include_in_schema=False, tags=["metrics"])

app.include_router(threads_router)
app.include_router(messages_router)
app.include_router(documents_router)

from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="RAG Chatbot API",
        version="1.0.0",
        routes=app.routes,
    )
    
    # Fix for Swagger UI failing to render multiple file uploads in OpenAPI 3.1
    # 1. Check components
    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})
    for component in schemas.values():
        properties = component.get("properties", {})
        for prop in properties.values():
            if prop.get("type") == "array" and "items" in prop:
                items = prop["items"]
                if items.get("contentMediaType") == "application/octet-stream":
                    items.pop("contentMediaType", None)
                    items["format"] = "binary"
                    
    # 2. Check inline paths
    for path in openapi_schema.get("paths", {}).values():
        for method in path.values():
            if "requestBody" in method:
                schema = method["requestBody"].get("content", {}).get("multipart/form-data", {}).get("schema", {})
                properties = schema.get("properties", {})
                for prop in properties.values():
                    if prop.get("type") == "array" and "items" in prop:
                        items = prop["items"]
                        if items.get("contentMediaType") == "application/octet-stream":
                            items.pop("contentMediaType", None)
                            items["format"] = "binary"
                    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

@app.get("/health", tags=["Health"])
async def health_check():
    db_status = "connected" if db_store.client else "disconnected"
    return {
        "status": "healthy",
        "chroma": "connected", # assuming healthy if running
        "mongodb": db_status
    }

# Ensure uploads directory exists
os.makedirs(settings.uploads_dir, exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
