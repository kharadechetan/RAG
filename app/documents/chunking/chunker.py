from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings

class Chunker:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def split_text(self, text: str) -> list[str]:
        if not text.strip():
            return []
        return self.splitter.split_text(text)
