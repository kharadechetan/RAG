import sys

print("Importing app.api.threads...", flush=True)
from app.api.threads import router as threads_router

print("Importing app.api.messages...", flush=True)
from app.api.messages import router as messages_router

print("Importing app.documents.router...", flush=True)
from app.documents.router import router as documents_router

print("Done!", flush=True)
