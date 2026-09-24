import sys

print("Importing fastapi...", flush=True)
from fastapi import FastAPI

print("Importing config...", flush=True)
from app.config import settings

print("Importing mongodb...", flush=True)
from app.database.mongodb import db_store

print("Importing documents.router...", flush=True)
from app.documents.router import router as documents_router

print("Importing chat.router...", flush=True)
from app.chat.router import router as chat_router

print("Importing api...", flush=True)
from app.api import router as api_router

print("Done!", flush=True)
