import modal
import asyncio
from typing import List

class ModalEmbeddingClient:
    def __init__(self):
        # We use Modal's RPC client instead of HTTP because the service
        # is exposed via @modal.method() rather than @modal.fastapi_endpoint()
        try:
            EmbeddingService = modal.Cls.from_name(
                "rag-embedding-service", 
                "EmbeddingService"
            )
            self.embed_service = EmbeddingService()
        except Exception as e:
            raise RuntimeError(f"Could not connect to Modal EmbeddingService: {e}")

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
            
        try:
            # We use asyncio.to_thread to prevent blocking the event loop
            # since .remote() is synchronous.
            embeddings = await asyncio.to_thread(self.embed_service.embed_documents.remote, texts)
            return embeddings
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}")
