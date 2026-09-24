import pytest
from app.documents.preprocessing.cleaner import TextCleaner

def test_text_cleaner():
    text = "This is a test.\n\n\nPage 1\n\n\n12\n\nThis is more text."
    cleaned = TextCleaner.clean(text)
    
    assert "Page 1" not in cleaned
    assert "12" not in cleaned
    assert "This is a test.\n\nThis is more text." in cleaned
