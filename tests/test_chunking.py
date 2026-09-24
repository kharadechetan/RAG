import pytest
from app.documents.chunking.chunker import Chunker
from app.config import settings

def test_chunker_basic():
    # Arrange
    chunker = Chunker()
    text = "A" * (settings.chunk_size + 10)
    
    # Act
    chunks = chunker.split_text(text)
    
    # Assert
    assert len(chunks) == 2
    assert len(chunks[0]) == settings.chunk_size
    assert len(chunks[1]) == 10 + settings.chunk_overlap
