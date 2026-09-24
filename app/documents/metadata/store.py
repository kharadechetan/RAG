import os
import json
from datetime import datetime, timezone
from app.config import settings
from typing import Optional
from app.documents.schemas import DocumentMetadata

class MetadataStore:
    def __init__(self, path: str):
        self.path = path
        self._ensure_file()

    def _ensure_file(self):
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({}, f)

    def _read_all(self):
        self._ensure_file()
        with open(self.path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _write_all(self, data):
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=4)

    def save_metadata(self, metadata: DocumentMetadata):
        data = self._read_all()
        data[metadata.document_id] = metadata.model_dump()
        self._write_all(data)

    def get_by_thread(self, thread_id: str):
        data = self._read_all()
        return [DocumentMetadata(**v) for v in data.values() if v.get("thread_id") == thread_id]

    def get_by_id(self, document_id: str, thread_id: str) -> Optional[DocumentMetadata]:
        data = self._read_all()
        doc = data.get(document_id)
        if doc and doc.get("thread_id") == thread_id:
            return DocumentMetadata(**doc)
        return None

    def delete_metadata(self, document_id: str, thread_id: str) -> bool:
        data = self._read_all()
        if document_id in data and data[document_id].get("thread_id") == thread_id:
            del data[document_id]
            self._write_all(data)
            return True
        return False

document_metadata_store = MetadataStore(settings.document_metadata_path)
