import json
from app.main import app

schema = app.openapi()
upload_path = schema["paths"].get("/documents/upload", {})
print(json.dumps(upload_path, indent=2))
