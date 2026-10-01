# FastAPI AI/RAG Backend

This repository contains a backend-only FastAPI application implementing a robust Retrieval-Augmented Generation (RAG) architecture. It is designed to handle document ingestion (PDFs), text extraction, OCR, chunking, embeddings generation, and conversational retrieval.

## Features
- **FastAPI Backend**: High-performance asynchronous API endpoints.
- **RAG Pipeline**: Complete pipeline from document upload to LLM response using LangGraph.
- **Document Processing**: PyMuPDF for native PDF extraction and PaddleOCR for scanned images.
- **Vector Database**: ChromaDB for persisting and querying document chunks.
- **Embeddings**: SentenceTransformers (all-MiniLM-L6-v2) for generating dense vectors.
- **LLM Integration**: Provider-agnostic LLM factory (currently using OpenAI SDK / Qwen / Modal).
- **Session Management**: Thread-based conversation history backed by MongoDB.
- **Metrics & Monitoring**: Prometheus Instrumentator integrated.

## Architecture

1. **Upload**: Users upload PDFs via `/documents/upload`.
2. **Extraction & Chunking**: Text is extracted, cleaned, and split into chunks.
3. **Embedding**: Chunks are embedded and stored in ChromaDB.
4. **Chat**: Users send queries via `/messages/stream`.
5. **Retrieval**: System determines if RAG is needed, queries ChromaDB, and formats context.
6. **Generation**: LLM generates a response streamed back to the user.

## Setup

1. Clone the repository.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in credentials.
4. Run MongoDB and ChromaDB (or let them run locally).
5. Start server: `python -m app.main` or `uvicorn app.main:app --reload`.

## Detailed Documentation
Please refer to `FASTAPI_AI_BACKEND_COMPLETE_DOCUMENTATION.pdf` for an extremely detailed, function-by-function technical breakdown of the entire codebase, including system flows, architectural decisions, and beginner-to-advanced explanations.
# RAG
