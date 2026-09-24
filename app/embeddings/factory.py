"""
Centralized embeddings factory.

Returns the configured SentenceTransformer embedding model.
Used by both ingestion and query-time retrieval to guarantee the same model.
"""
from typing import List
from langchain_core.embeddings import Embeddings
from sentence_transformers import SentenceTransformer

class CustomSentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

# Global instance loaded immediately when the server starts
_embeddings_instance = CustomSentenceTransformerEmbeddings()

def get_embeddings() -> Embeddings:
    return _embeddings_instance
