"""
ChromaDB vector store — LangChain Chroma integration.

Provides:
  - add_chunks(): batch insert during ingestion (with pre-computed embeddings)
  - retrieve(): similarity search filtered by thread_id (and optional document_id)
  - delete_document(): remove all chunks for a document
  - count_document_chunks(): verify deletion
  - as_retriever(): return a LangChain retriever for a specific thread
"""
import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.config import settings
from app.embeddings.factory import get_embeddings


class ChromaVectorStore:
    def __init__(self):
        self._client = chromadb.PersistentClient(
            path=settings.chroma_persist_directory
        )
        self._embedding_fn = get_embeddings()
        self._store = Chroma(
            client=self._client,
            collection_name=settings.chroma_collection,
            embedding_function=self._embedding_fn,
        )
        # Keep a raw collection handle for operations that LangChain Chroma
        # doesn't expose directly (delete-by-where, count-by-where).
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def add_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ):
        """Insert pre-embedded chunks (used during PDF ingestion)."""
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        thread_id: str,
        document_id: str | None = None,
        n_results: int = 5,
    ) -> list[Document]:
        """
        Similarity search that returns LangChain Document objects.
        Always filters by thread_id to enforce session isolation.
        """
        where_filter: dict = {"thread_id": thread_id}
        if document_id:
            where_filter = {
                "$and": [
                    {"thread_id": thread_id},
                    {"document_id": document_id},
                ]
            }

        results = self._store.similarity_search(
            query=query,
            k=n_results,
            filter=where_filter,
        )
        return results

    def as_retriever(self, thread_id: str, k: int | None = None):
        """Return a LangChain retriever scoped to a thread."""
        return self._store.as_retriever(
            search_kwargs={
                "k": k or settings.top_k,
                "filter": {"thread_id": thread_id},
            }
        )

    # ------------------------------------------------------------------
    # Deletion / counting (raw collection for where-clause ops)
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str, thread_id: str):
        self._collection.delete(
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"document_id": document_id},
                ]
            }
        )

    def count_document_chunks(self, document_id: str, thread_id: str) -> int:
        result = self._collection.get(
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"document_id": document_id},
                ]
            },
            include=[],
        )
        return len(result["ids"])

    def delete_thread_documents(self, thread_id: str):
        """Delete ALL chunks belonging to a thread (used on thread deletion)."""
        self._collection.delete(where={"thread_id": thread_id})


chroma_store = ChromaVectorStore()
