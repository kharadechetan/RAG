import json
from app.main import app

schema = app.openapi()
body = schema["components"]["schemas"].get("Body_upload_document_documents_upload_post")
print(json.dumps(body, indent=2))
