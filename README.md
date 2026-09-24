# Modal LLM Chatbot Backend

A production-ready AI chatbot backend using FastAPI, LangChain, LangGraph, and MongoDB, natively interacting with an existing Modal LLM endpoint.

## Features
- **Strict Thread Isolation:** Every conversation runs in an independent sandbox based on its UUID `thread_id`.
- **Persistent State:** Uses MongoDB and LangGraph `MongoDBSaver` to checkpoint conversation threads.
- **Real Token Streaming:** Yields text chunk deltas sequentially via `fastapi.responses.StreamingResponse` for immediate frontend feedback.
- **Context Awareness:** Remembers internal thread conversation context natively.
- **Pydantic Validation:** Fully-typed data schemas handling HTTP validation.

## Architecture

```text
                         FRONTEND
                            |
                     FastAPI REST API
                            |
              +-------------+-------------+
              |                           |
              v                           v
        Thread APIs                /messages/stream
                                          |
                                          v
                                      LangGraph
                                          |
                                  thread_id config
                                          |
                                          v
                              MongoDB Checkpointer
                                          |
                                   Previous Messages
                                          |
                                          v
                                      LangChain
                                          |
                                          v
                                     Modal LLM
                                          |
                                  NEW TOKEN/CHUNK
                                          |
                                          v
                                      LangGraph
                                          |
                                  NEW TOKEN/CHUNK
                                          |
                                          v
                                      FastAPI
                                          |
                                  NEW TEXT CHUNK
                                          |
                                          v
                                      Frontend
                                          |
                              Append to SAME message
```

## Setup & Installation

1. Create a virtual environment and install dependencies:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

2. Make sure MongoDB is running locally or specify your URI in `.env`.
```bash
cp .env.example .env
```
Ensure `MODAL_LLM_URL` in `.env` is set to your Modal LLM backend.

3. Run the FastAPI development server:

If you are NOT using the OCR component, you can run:
```bash
uvicorn app.main:app --reload
```

**IMPORTANT**: If you are using PaddleOCR to extract text from images, you MUST run the application using the pre-configured OCR environment on the B: drive:
```bash
B:\ocr\ocr-env\Scripts\python.exe -m uvicorn app.main:app --reload
```
This ensures the app uses the `paddleocr` installation and models cache at `B:\ocr\paddlex_cache`.

Swagger UI will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

## Example Client Usage (Streaming)
The frontend should decode the stream chunks and append them progressively:

```javascript
const response = await fetch("/messages/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: "your-thread-id", message: "Explain RAG" })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
const assistantElement = document.createElement("div"); // Ensure ONE UI block!
let assistantText = "";

while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });
    assistantText += chunk; // Incrementally append delta
    assistantElement.textContent = assistantText;
}
```

## Testing
Unit tests rely on `pytest` and `httpx`. Ensure MongoDB is accessible on localhost or per `.env`, then run:
```bash
pytest
```
This tests endpoint functionality, isolation, and streaming output formats.
# RAG
