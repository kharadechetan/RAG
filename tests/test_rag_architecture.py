"""
Tests for the refactored RAG chatbot.
Covers: embeddings, chroma, retrieval isolation, LLM factory, citations, graph.
"""
import os
import uuid
import pytest

# Ensure settings load before any app import
os.environ.setdefault("OPENAI_API_KEY", "test-key")


# =========================================================================
# 1. Embeddings factory
# =========================================================================

class TestEmbeddingsFactory:
    def test_get_embeddings_returns_openai(self):
        from app.embeddings.factory import get_embeddings
        emb = get_embeddings()
        assert emb.model == "text-embedding-3-small"

    def test_get_embeddings_missing_key(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.openai_api_key", "")
        from app.embeddings.factory import get_embeddings
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            get_embeddings()


# =========================================================================
# 2. LLM factory
# =========================================================================

class TestLLMFactory:
    def test_get_chat_model_openai(self):
        from app.llm.factory import get_chat_model
        model = get_chat_model()
        assert model.model_name == "gpt-4o-mini"

    def test_get_chat_model_missing_key(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.openai_api_key", "")
        from app.llm.factory import get_chat_model
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            get_chat_model()

    def test_unsupported_provider(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.llm_provider", "unsupported")
        from app.llm.factory import get_chat_model
        with pytest.raises(ValueError, match="Unsupported"):
            get_chat_model()


# =========================================================================
# 3. Chroma isolation — documents should not leak across threads
# =========================================================================

class TestChromaIsolation:
    def test_thread_isolation(self):
        """Chunks added for thread_a should not appear in thread_b queries."""
        from app.documents.vectorstore.chroma import ChromaVectorStore
        import chromadb

        # Use a temp in-memory-like collection to avoid polluting real data
        store = ChromaVectorStore.__new__(ChromaVectorStore)
        client = chromadb.Client()  # ephemeral
        col_name = f"test_{uuid.uuid4().hex[:8]}"
        store._client = client
        store._collection = client.get_or_create_collection(name=col_name)

        thread_a = f"thread-a-{uuid.uuid4()}"
        thread_b = f"thread-b-{uuid.uuid4()}"

        # Add chunks for thread A
        store.add_chunks(
            ids=["a1", "a2"],
            documents=["Alpha content", "Beta content"],
            embeddings=[[0.1] * 10, [0.2] * 10],
            metadatas=[
                {"thread_id": thread_a, "document_id": "docA", "filename": "a.pdf", "page_number": 1},
                {"thread_id": thread_a, "document_id": "docA", "filename": "a.pdf", "page_number": 2},
            ],
        )

        # Add chunks for thread B
        store.add_chunks(
            ids=["b1"],
            documents=["Gamma content"],
            embeddings=[[0.3] * 10],
            metadatas=[
                {"thread_id": thread_b, "document_id": "docB", "filename": "b.pdf", "page_number": 1},
            ],
        )

        # Count should respect thread isolation
        assert store.count_document_chunks("docA", thread_a) == 2
        assert store.count_document_chunks("docA", thread_b) == 0
        assert store.count_document_chunks("docB", thread_b) == 1
        assert store.count_document_chunks("docB", thread_a) == 0

    def test_delete_removes_embeddings(self):
        """After delete, count should be 0."""
        from app.documents.vectorstore.chroma import ChromaVectorStore
        import chromadb

        store = ChromaVectorStore.__new__(ChromaVectorStore)
        client = chromadb.Client()
        col_name = f"test_{uuid.uuid4().hex[:8]}"
        store._client = client
        store._collection = client.get_or_create_collection(name=col_name)

        tid = f"t-{uuid.uuid4()}"
        did = f"d-{uuid.uuid4()}"

        store.add_chunks(
            ids=["x1"],
            documents=["Some text"],
            embeddings=[[0.5] * 10],
            metadatas=[{"thread_id": tid, "document_id": did, "filename": "x.pdf", "page_number": 1}],
        )
        assert store.count_document_chunks(did, tid) == 1

        store.delete_document(did, tid)
        assert store.count_document_chunks(did, tid) == 0

    def test_delete_thread_documents(self):
        """delete_thread_documents should wipe all docs for a thread."""
        from app.documents.vectorstore.chroma import ChromaVectorStore
        import chromadb

        store = ChromaVectorStore.__new__(ChromaVectorStore)
        client = chromadb.Client()
        col_name = f"test_{uuid.uuid4().hex[:8]}"
        store._client = client
        store._collection = client.get_or_create_collection(name=col_name)

        tid = f"t-{uuid.uuid4()}"

        store.add_chunks(
            ids=["y1", "y2"],
            documents=["Doc1", "Doc2"],
            embeddings=[[0.1] * 10, [0.2] * 10],
            metadatas=[
                {"thread_id": tid, "document_id": "d1", "filename": "1.pdf", "page_number": 1},
                {"thread_id": tid, "document_id": "d2", "filename": "2.pdf", "page_number": 1},
            ],
        )
        assert store.count_document_chunks("d1", tid) == 1
        assert store.count_document_chunks("d2", tid) == 1

        store.delete_thread_documents(tid)
        assert store.count_document_chunks("d1", tid) == 0
        assert store.count_document_chunks("d2", tid) == 0


# =========================================================================
# 4. Citations — must come from metadata, not LLM
# =========================================================================

class TestCitations:
    @pytest.mark.asyncio
    async def test_attach_sources_from_metadata(self):
        from langchain_core.documents import Document
        from app.graph.nodes import attach_sources

        docs = [
            Document(page_content="chunk1", metadata={"filename": "report.pdf", "page_number": 42, "document_id": "d1"}),
            Document(page_content="chunk2", metadata={"filename": "report.pdf", "page_number": 42, "document_id": "d1"}),
            Document(page_content="chunk3", metadata={"filename": "manual.pdf", "page_number": 7, "document_id": "d2"}),
        ]

        state = {"retrieved_documents": docs}
        result = await attach_sources(state, config={})

        sources = result["sources"]
        # De-duplicated by (filename, page_number)
        assert len(sources) == 2
        assert sources[0]["filename"] == "report.pdf"
        assert sources[0]["page_number"] == 42
        assert sources[1]["filename"] == "manual.pdf"
        assert sources[1]["page_number"] == 7


# =========================================================================
# 5. Graph structure
# =========================================================================

class TestGraphStructure:
    def test_graph_has_expected_nodes(self):
        """Verify the LangGraph contains all required nodes."""
        from app.graph.graph import build_graph
        # We need db_store.checkpointer to be set for this
        # Skip if MongoDB is not available
        from app.database.mongodb import db_store
        if db_store.checkpointer is None:
            pytest.skip("MongoDB not available")

        graph = build_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"prepare_query", "retrieve_documents", "build_context", "generate_answer", "attach_sources"}
        assert expected.issubset(node_names)


# =========================================================================
# 6. Chunking (preserved from existing tests)
# =========================================================================

class TestChunking:
    def test_basic_chunking(self):
        from app.documents.chunking.chunker import Chunker
        chunker = Chunker()
        text = "Hello world. " * 200  # Long enough to produce multiple chunks
        chunks = chunker.split_text(text)
        assert len(chunks) > 1

    def test_empty_text(self):
        from app.documents.chunking.chunker import Chunker
        chunker = Chunker()
        assert chunker.split_text("") == []
        assert chunker.split_text("   ") == []


# =========================================================================
# 7. Text cleaner (preserved from existing tests)
# =========================================================================

class TestCleaner:
    def test_clean_page_numbers(self):
        from app.documents.preprocessing.cleaner import TextCleaner
        cleaner = TextCleaner()
        text = "Some text\nPage 1 of 5\nMore text\n42\nEnd"
        cleaned = cleaner.clean(text)
        assert "Page 1 of 5" not in cleaned
        assert "Some text" in cleaned
        assert "More text" in cleaned

    def test_clean_empty(self):
        from app.documents.preprocessing.cleaner import TextCleaner
        cleaner = TextCleaner()
        assert cleaner.clean("") == ""
        assert cleaner.clean(None) == ""
