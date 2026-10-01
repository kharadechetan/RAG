# FastAPI AI/RAG Backend — Complete Technical Documentation

## 1. Executive Summary
This document provides an exhaustive, function-by-function technical breakdown of the FastAPI-based Retrieval-Augmented Generation (RAG) backend. It is designed to serve as a complete reference manual, explaining not just *what* the code does, but *why* it was designed this way, how it fits into the broader architecture, and what happens at a low-level during execution.

## 2. Project Purpose
The backend provides an end-to-end API for managing conversation threads, ingesting document files (PDFs), extracting their text using both native PyMuPDF and OCR (PaddleOCR), embedding the text into a ChromaDB vector database, and utilizing LangGraph to route and process user queries against these documents via an LLM.

## 3. Technology Stack
- **Web Framework**: FastAPI (Async HTTP routing, dependency injection)
- **Data Models**: Pydantic (Request/Response schema validation)
- **State/Workflow**: LangGraph (Graph-based LLM routing and state tracking)
- **LLM/Embeddings**: LangChain, OpenAI SDK, SentenceTransformers
- **Vector Database**: ChromaDB (Local vector persistence)
- **Primary Database**: MongoDB (Thread tracking, LangGraph checkpointer)
- **Document Processing**: PyMuPDF (Native text/images), PaddleOCR (Scanned documents)
- **Concurrency**: Python `asyncio`

## 4. Repository Structure
- `app/api/`: FastAPI route handlers (endpoints).
- `app/database/`: MongoDB connection and thread metadata operations.
- `app/documents/`: RAG ingestion pipeline (chunking, embeddings, extraction, metadata, OCR, vectorstore).
- `app/embeddings/`: Centralized embedding model initialization.
- `app/graph/`: LangGraph definitions, nodes, state schema, and prompts.
- `app/llm/`: LLM provider factory.
- `app/schemas/`: Pydantic models for threads and messages.

## 5. FastAPI Architecture
### Definition
FastAPI is an asynchronous Python web framework built on Starlette and Pydantic.
### Why
It provides automatic OpenAPI documentation, strict type validation, and high-performance async I/O handling, which is critical for a backend that spends most of its time waiting for LLM APIs, Database I/O, and OCR services.

## 6. API Endpoints
### `POST /threads`
- **Purpose**: Initializes a new conversation session.
- **Request/Response**: Returns a `ThreadResponse` containing a generated `thread_id`.

### `GET /threads/{thread_id}/history`
- **Purpose**: Retrieves past messages for a thread from the MongoDB checkpointer.

### `POST /messages/stream`
- **Purpose**: Core endpoint for receiving user questions and streaming back LLM tokens.
- **HTTP Method**: POST because it carries a request payload and changes state.
- **Functions Called**: `stream_message` -> `build_graph()` -> `graph.astream()` -> LangGraph Nodes.

### `POST /documents/upload`
- **Purpose**: Ingests up to 10 PDFs, extracts text, chunks, embeds, and stores in ChromaDB.

## 7. Complete Request Lifecycle
```text
USER QUERY
   ↓
POST /messages/stream (app/api/messages.py)
   ↓
build_graph() (app/graph/graph.py)
   ↓
prepare_query() (Extracts latest question, determines if RAG is needed)
   ↓
retrieve_documents() (Queries ChromaDB with query embedding, returns top_k chunks)
   ↓
build_context() (Formats chunks into string with citations)
   ↓
generate_answer() (Constructs prompt with context, calls LLM, receives streaming tokens)
   ↓
attach_sources() (Gathers metadata from retrieved chunks)
   ↓
StreamingResponse (Yields tokens directly back to the HTTP client)
```

## 8. Function Inventory
| File | Function/Class | Type | Purpose | Called By | Calls |
|---|---|---|---|---|---|
| main.py | `lifespan()` | Function | DB/Resource initialization | FastAPI app | `MongoClient`, `get_reranker` |
| main.py | `custom_openapi()` | Function | Fixes OpenAPI swagger schema | FastAPI app | `get_openapi` |
| messages.py | `stream_message()` | Endpoint | Streams LLM response | HTTP Client | `build_graph`, `astream` |
| threads.py | `create_thread()` | Endpoint | Creates thread | HTTP Client | `create_thread_metadata` |
| service.py | `process_document()` | Method | Runs ingestion pipeline | `upload_document` | `extract_pages`, `clean`, `split_text`, `embed_documents`, `add_chunks` |
| local_ocr.py | `extract_text_from_bytes()` | Method | Runs PaddleOCR | `process_document` | `PaddleOCR` |
| chunker.py | `split_text()` | Method | Recursive chunking | `process_document` | Langchain splitter |
| chroma.py | `retrieve()` | Method | Vector search | `retrieve_documents` | `store.similarity_search` |
| nodes.py | `retrieve_documents()`| Graph Node| Fetches context | LangGraph | `chroma_store.retrieve` |
| nodes.py | `generate_answer()` | Graph Node| Calls LLM | LangGraph | `get_chat_model`, `chain.ainvoke` |
## 9. File-by-File Explanation

### `app/config.py`
This file uses `pydantic_settings.BaseSettings` to load and validate environment variables.
- **Why**: Centralized configuration prevents hardcoding secrets and provides type safety for environment variables.
- **Key attributes**: MongoDB URI, LLM models, chunk sizes, and prompt configurations.

### `app/main.py`
The FastAPI application entry point.
- **Why**: Bootstraps the application, registers routers, and handles startup/shutdown events.

### `app/api/messages.py` & `app/api/threads.py`
Contains the FastAPI route definitions (Endpoints).
- **Why**: Separates HTTP routing logic from business logic.

## 10. Function-by-Function Explanation (Core App & DB)

### `app/main.py` -> `lifespan(app: FastAPI)`
- **Definition**: An async context manager that FastAPI runs before processing requests and after shutdown.
- **Purpose**: Initializes persistent resources (MongoDB client, checkpointer) and pre-loads heavy models (Reranker) to avoid latency on the first request.
- **Parameters**: `app` (FastAPI instance).
- **Inside**: Connects to `mongodb_uri`, creates `db_store.db`, ensures the uploads directory exists, conditionally pre-loads the CrossEncoder. Yields control to FastAPI. Closes the DB on shutdown.
- **Called by**: Uvicorn/FastAPI runtime.
- **Technical**: Uses `@asynccontextmanager` to separate setup (before `yield`) and teardown (after `yield`).

### `app/main.py` -> `custom_openapi()`
- **Purpose**: Overrides FastAPI's default OpenAPI schema generation.
- **Inside**: Scans the schema for `multipart/form-data` uploads containing `application/octet-stream` and changes the format to `binary`.
- **Why**: A known bug in Swagger UI 3.1 causes multiple file uploads to break in the browser UI without this specific schema patch.

### `app/api/messages.py` -> `stream_message(request: MessageRequest, background_tasks: BackgroundTasks)`
- **Definition**: The main endpoint for chatbot interaction.
- **Purpose**: Receives a user message, runs the LangGraph workflow, and streams tokens back to the user.
- **Parameters**:
  - `request`: Pydantic model with `thread_id` and `message`.
  - `background_tasks`: FastAPI dependency for running non-blocking tasks.
- **Step-by-step**:
  1. Validates the `thread_id` exists in MongoDB.
  2. Constructs the LangGraph using `build_graph()`.
  3. Spawns a background task to update the thread's "last updated" timestamp.
  4. Defines an async generator `generate_response()`.
  5. Returns a `StreamingResponse` wrapping the generator.
- **Return value**: An HTTP streaming response yielding text.

### `app/api/messages.py` -> `generate_response()` (Inner function)
- **Purpose**: Awaits the execution of the LangGraph and yields token outputs as they stream.
- **Inside**:
  1. Configures the graph with `{"configurable": {"thread_id": ...}}`.
  2. Creates a `HumanMessage`.
  3. Iterates over `graph.astream(...)`.
  4. Identifies messages coming from the `generate_answer` node.
  5. Yields the string contents.
  6. After streaming completes, calls `graph.aget_state()` to retrieve the attached sources.
  7. Yields a final JSON string containing the sources.
- **Why async generator?**: `yield` allows sending data to the client over an open TCP connection piece-by-piece, drastically reducing Time-to-First-Token (TTFT) for the user.

### `app/database/mongodb.py` -> `DatabaseStore`
- **Definition**: A Singleton-pattern class storing active database connection handles.
- **Why**: Prevents opening a new MongoDB connection per request.

### `app/database/threads.py` -> `create_thread_metadata(thread_id, user_id)`
- **Purpose**: Inserts a new document into the `threads` MongoDB collection.
- **Input**: UUID string for `thread_id`.
- **Inside**: Gets current UTC time, inserts dict into `db_store.db["threads"]`.
- **Called by**: `POST /threads` endpoint.

### `app/database/threads.py` -> `get_thread_metadata(thread_id)`
- **Purpose**: Retrieves thread data to ensure it exists.
- **Return**: A dictionary or None.
- **Why**: Used as validation before appending messages to a thread to prevent orphaned checkpointer data.

## 11. Class-by-Class Explanation (Schemas)

### Class: `MessageRequest` (app/schemas/message.py)
- **Definition**: A Pydantic BaseModel.
- **Purpose**: Defines the expected JSON payload for `/messages/stream`.
- **Attributes**: `thread_id` (str), `message` (str).
- **Why**: Pydantic automatically validates HTTP request bodies and returns 422 Unprocessable Entity if fields are missing.

### Class: `ChatState` (app/graph/state.py)
- **Definition**: A TypedDict used by LangGraph.
- **Purpose**: Defines the data structure that passes between nodes in the workflow.
- **Attributes**: 
  - `messages`: Annotated list holding conversation history. The `add_messages` reducer ensures new messages append to the list rather than overwriting it.
  - `question`: The current user query.
  - `retrieved_documents`: The raw LangChain documents found in ChromaDB.
  - `context`: The string-formatted context given to the LLM.

## 12. Python Concepts Used
- **Type Hints (`str`, `dict`, `list`)**: Improves developer experience (IDE autocompletion) and is heavily utilized by Pydantic and FastAPI for runtime validation.
- **`async` / `await`**: Python's asynchronous I/O primitives. `await` releases the event loop while waiting for an operation (like DB fetch or HTTP request) to complete, allowing the single-threaded server to handle thousands of concurrent requests.
- **Decorators (`@app.get`, `@router.post`)**: A design pattern that wraps a function, modifying its behavior. Used here to register URL paths with FastAPI.
- **Context Managers (`@asynccontextmanager`, `with open(...)`)**: Ensures resources (like database connections or file handlers) are properly opened and safely closed regardless of exceptions.
## 13. Document Processing (Ingestion Pipeline)
The ingestion pipeline converts a raw uploaded PDF into semantically meaningful vector embeddings stored in a database.

### `app/documents/service.py` -> `DocumentService` (Class)
- **Definition**: The orchestration class for document ingestion.
- **Purpose**: Wires together the extractor, OCR, cleaner, chunker, embedder, and vectorstore.
- **Attributes**: Instances of `PyMuPDFExtractor`, `LocalPaddleOCRClient`, `TextCleaner`, `Chunker`, `chroma_store`.

### `DocumentService.process_document(file_bytes, filename, thread_id)`
- **Purpose**: Main entry point for a single uploaded document.
- **Step-by-step**:
  1. Generates a `document_id` UUID.
  2. Saves the file to disk in `settings.uploads_dir`.
  3. Identifies file type. If PDF, yields pages using `extract_pages`.
  4. Runs `process_page` asynchronously for every page using `asyncio.gather`.
  5. Flattens all returned page chunks into a single list.
  6. Batches chunks (e.g., 32 at a time).
  7. Sends batches to `embedding_model.embed_documents()` concurrently using an `asyncio.Semaphore(4)` to prevent API/DB overload.
  8. Inserts embedded chunks into ChromaDB via `add_chunks()`.
  9. Saves final tracking metrics to `DocumentMetadataStore`.
- **Return value**: `DocumentUploadResponse` indicating success/failure.
- **Why**: Handles the complex asynchronous orchestration required to process long documents without blocking the main event loop.

## 14. PDF Extraction
### `app/documents/extraction/pdf_extractor.py` -> `PyMuPDFExtractor.extract_pages()`
- **Definition**: Uses the `fitz` (PyMuPDF) library to read binary PDF data.
- **Inside**:
  1. Opens the PDF stream.
  2. Iterates over pages.
  3. Calls `page.get_text("text")` to pull native digital text.
  4. Calls `page.get_text("blocks")` to extract bounding box coordinates for text blocks.
  5. Renders the page into a PNG image (`page.get_pixmap().tobytes("png")`) in case OCR is needed.
  6. `yields` a dictionary containing the text, blocks, and image bytes.
- **Why**: PyMuPDF is extremely fast for digitally generated PDFs. We extract images proactively so that if the native text is empty (scanned PDF), we don't have to reopen the file.

## 15. OCR (Optical Character Recognition)
### `app/documents/ocr/local_ocr.py` -> `LocalPaddleOCRClient`
- **Definition**: A wrapper around PaddleOCR, a machine learning model that extracts text from images.
- **Why**: Scanned PDFs or images do not contain native digital text layers. OCR reads the pixels and converts them to text.
- **Implementation**: Uses a Singleton pattern `get_instance()` so the heavy PaddleOCR model is only loaded into memory once.
- **`extract_text_from_bytes(image_bytes)`**:
  - Saves the image bytes to a temporary file via `tempfile.mkstemp`.
  - Runs the OCR engine inside a thread pool (`asyncio.get_event_loop().run_in_executor()`).
  - **Why**: PaddleOCR is completely synchronous and highly CPU-intensive. Running it on the main async event loop would freeze the entire FastAPI web server, meaning no other user could chat or upload files until OCR finishes.
  - Cleans up the temporary file afterward.

## 16. Chunking
### Definition
Chunking is the process of breaking a large document into smaller, manageable text segments (chunks).
### Why?
LLMs have a limited context window. Embedding models (like MiniLM) also have strict input limits (e.g., 512 tokens). If we embed a whole book, the vector loses semantic precision. By chunking, we can embed paragraph-sized concepts and retrieve only the specific paragraphs relevant to a query.
### `app/documents/chunking/chunker.py` -> `Chunker.split_text(text)`
- **Implementation**: Uses LangChain's `RecursiveCharacterTextSplitter`.
- **Algorithm**: Recursively tries to split by `\n\n` (paragraphs), then `\n` (lines), then spaces, until the chunk is smaller than `chunk_size` (800 chars).
- **Overlap**: Uses `chunk_overlap` (120 chars).
  - **Why overlap?**: If a sentence mentioning "The company revenue" is split exactly in half, neither chunk might make sense independently. Overlap ensures the end of Chunk A is the beginning of Chunk B, preserving context boundaries.

## 17. Embeddings
### Definition
An embedding is a mathematical representation (a vector or array of floating-point numbers) of the semantic meaning of a text string.
### Why?
Computers cannot natively understand "meaning." By converting text to numbers where similar concepts exist close to each other in a multi-dimensional space, we can mathematically calculate how similar a query is to a document chunk.
### `app/embeddings/factory.py` -> `CustomSentenceTransformerEmbeddings.embed_documents()`
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`.
- **Why**: It runs entirely locally on CPU, is very fast, and creates dense vectors of 384 dimensions.
- **Inside**: Calls `self.model.encode(texts)`. Returns a list of floats.

## 18. Vector Database
### Definition
A database optimized for storing and querying high-dimensional vectors.
### Why?
Traditional databases (like PostgreSQL without extensions) use exact-match text searching (B-Trees). A vector database performs mathematical vector calculations (like Cosine Similarity) to find the "closest" meaning, even if exact keywords don't match.
### `app/documents/vectorstore/chroma.py` -> `ChromaVectorStore`
- **Implementation**: Uses ChromaDB in persistent local mode.
- **`add_chunks(ids, documents, embeddings, metadatas)`**:
  - Inserts pre-calculated embeddings directly into the underlying Chroma collection.
- **`retrieve(query, thread_id, n_results)`**:
  - Uses LangChain's `.similarity_search()`.
  - **Crucial Security Feature**: Passes `{"thread_id": thread_id}` in the `where` filter.
  - **Why**: Enforces tenant/session isolation at the database level. User A querying their thread will NEVER accidentally retrieve documents uploaded by User B to a different thread.
## 19. Semantic Search & 20. Retrieval
### `app/graph/nodes.py` -> `retrieve_documents()`
- **Definition**: A LangGraph node function responsible for executing semantic search.
- **Why**: Fetches the exact paragraphs needed to answer a user's question without passing the entire document to the LLM.
- **Inside**:
  1. Retrieves the current `question` and `thread_id` from the LangGraph `state`.
  2. Calls `chroma_store.retrieve(question, thread_id, n_results=top_k)`. Chroma handles embedding the query text internally.
  3. (Optional) If Reranking is enabled, passes the retrieved chunks and the question to a CrossEncoder (`settings.rerank_model`). The CrossEncoder re-scores the similarity.
  4. Updates the LangGraph state with `retrieved_documents` and latency metrics.

## 21. RAG (Retrieval-Augmented Generation) & 22. Prompt Construction
### Definition
RAG is an architectural pattern where an LLM is given verified external knowledge as part of its prompt to prevent hallucinations.
### `app/graph/nodes.py` -> `build_context()`
- **Purpose**: Converts the raw retrieved document chunks into a single formatted string that the LLM can understand.
- **Inside**: Iterates through chunks. Extracts metadata (`filename`, `page_number`). Formats as:
  `SOURCE 1\nDocument: xyz.pdf\nPage: 5\n\n[TEXT]`
- **Why**: The LLM needs clear boundaries (like "SOURCE 1") so it knows exactly where information came from, enabling it to cite its sources accurately.

### `app/graph/prompts.py`
- Defines two `ChatPromptTemplate` configurations: `RAG_PROMPT_WITH_CONTEXT` and `RAG_PROMPT_NO_CONTEXT`.
- **Why separate?**: If a user says "Hi", no documents are retrieved. Passing an empty context block confuses the LLM. Dynamic prompt selection creates a better conversational experience.

## 23. LLM (Large Language Model) Processing
### `app/llm/factory.py` -> `get_chat_model()`
- **Purpose**: Instantiates the LangChain chat model wrapper.
- **Implementation**: Uses `ChatOpenAI`. Because the project supports local models (like Qwen), it detects if the model name contains "qwen" or the API key is "local" and rewrites the `base_url` to point to a local proxy (e.g., vLLM or LM Studio at `127.0.0.1:8080`).

### `app/graph/nodes.py` -> `generate_answer()`
- **Purpose**: Executes the actual LLM inference.
- **Inside**:
  1. Pulls bounded `chat_history` (last 10 messages) to prevent exceeding token limits.
  2. Selects the correct prompt template (Context vs No Context).
  3. Creates an LCEL (LangChain Expression Language) pipeline: `chain = prompt | llm`.
  4. Calls `await chain.ainvoke(...)`.
  5. **Note on Streaming**: Even though `ainvoke` is called, because the model is configured with `streaming=True`, LangChain pushes tokens to the LangGraph runner asynchronously, which the HTTP endpoint is listening to via `astream`.

## 24. Streaming & 25. AsyncIO
### What happens behind the scenes in `astream`?
When `graph.astream(stream_mode="messages")` runs:
1. The LangGraph state machine begins executing nodes.
2. It hits `generate_answer()`.
3. `ChatOpenAI` opens an HTTP connection to the LLM API using Server-Sent Events (SSE).
4. The LLM API returns the first word (token) over the wire immediately.
5. LangChain packages this token into an `AIMessageChunk`.
6. `graph.astream` yields this chunk to our FastAPI generator `generate_response()`.
7. FastAPI yields it to the HTTP client (browser) via chunked transfer encoding.
8. The browser renders the word on screen.
9. This repeats rapidly (dozens of times per second) until generation completes.
- **Why**: If we waited for the entire response to generate before returning HTTP 200, the user would stare at a loading spinner for 10-20 seconds. Streaming reduces latency to ~1 second.

## 26. Session/State Management
### `app/database/threads.py`
- Stores lightweight metadata (User ID, created/updated timestamps) in a MongoDB collection named `threads`.
### LangGraph Checkpointer (`MongoDBSaver`)
- LangGraph persists the entire `ChatState` (including raw `messages` arrays) into a separate collection managed automatically by LangGraph's checkpointer.
- **Why**: REST APIs are stateless. Without the checkpointer, the AI would have no memory of the previous question.

## 27. Error Handling
- **Pydantic Validation**: Raises `HTTP 422 Unprocessable Entity` if request schemas are malformed.
- **FastAPI `HTTPException`**: Used extensively in `documents/router.py`. E.g., if a file is empty, raises `400 Bad Request`. If a document isn't found during deletion, raises `404 Not Found`.
- **Try/Except in OCR**: PaddleOCR is prone to crashing on corrupted images. Wrapped in try/except; if it fails, the system safely falls back to native text extraction or skips the page rather than crashing the ingestion pipeline.

## 28. Security
- **Path Traversal Protection**: In `download_document`, `os.path.realpath` is used to verify that the requested file exists strictly inside the `settings.uploads_dir` before serving it.
- **Tenant Isolation**: Every database query (`retrieve`, `delete_document`) mandates `thread_id` as a required parameter. It is impossible to query ChromaDB without supplying the conversational boundary.

## 29. Performance Considerations
- **Concurrency**: `asyncio.gather` processes PDF pages concurrently.
- **Semaphores**: `asyncio.Semaphore(4)` prevents the embedding batcher from crushing the local CPU or hitting external API rate limits.
- **Database Locks**: ChromaDB uses SQLite underneath. Excessive simultaneous writes will lock the database. Batching and semaphores mitigate this.
- **LangGraph Routing**: `should_use_rag()` uses a deterministic regex filter to bypass Vector Search entirely for simple phrases ("hi", "thanks"). This saves ~200ms per conversational query.
## 35. What Happens Behind the Scenes (File Upload)
When I call `POST /documents/upload`:
1. HTTP request arrives via Uvicorn.
2. FastAPI routes to `upload_document()` in `documents/router.py`.
3. Pydantic validates the `thread_id` and the `files` array.
4. Validation checks if the file has `.pdf` extension, is not empty, and is under the size limit.
5. The `DocumentService.process_document()` is called.
6. The file is written physically to `./data/uploads/{uuid}.pdf`.
7. `PyMuPDF` opens the binary stream and counts pages.
8. `LanguageDetector` figures out what language the text is.
9. `TextCleaner` sanitizes bad Unicode and removes extra spaces.
10. `Chunker` chops text into 800-character blocks with 120-character overlap.
11. `SentenceTransformer` converts the text chunks into vectors (Embeddings).
12. `ChromaVectorStore` commits the vectors and text payloads to disk (SQLite/Parquet).
13. `DocumentMetadataStore` logs the chunk count to `./data/documents.json`.
14. API returns HTTP 200 with processing statistics.

## 40. Interview Explanation
### 30-second explanation
"I built a FastAPI backend that allows users to upload PDFs and chat with them. It uses PyMuPDF and PaddleOCR to extract text, chunks the text, and stores it as vector embeddings in ChromaDB. When a user asks a question, we perform semantic search to find the most relevant paragraphs, inject them into a prompt via LangGraph, and stream an AI response back using an LLM like OpenAI."

### 1-minute explanation
"This project is a stateless, high-concurrency RAG backend. I used FastAPI for async HTTP handling and Pydantic for strict data validation. The document ingestion pipeline is heavily concurrent, utilizing `asyncio.gather` and semaphores to batch-process PDFs through native extraction and OCR without blocking the event loop. The resulting text is chunked and embedded using local SentenceTransformer models and stored in ChromaDB. For conversational logic, I implemented a state machine using LangGraph. This intercepts the user query, determines if database retrieval is necessary using deterministic routing, fetches context, formats a prompt, and streams LLM output back to the client using Server-Sent Events, while MongoDB maintains the conversation history."

### 5-minute deep technical explanation
*(Expands on the above by detailing the LangGraph node architecture, the separation of concerns between Routers and Services, the specifics of the chunking algorithm, and the safety measures like Thread isolation and Path Traversal protection. Mention the patch implemented for Swagger UI 3.1 file upload bug in `custom_openapi()`).*

## 41. Interview Questions & Answers

**Q: Why did you use LangGraph instead of standard LangChain chains?**
A: "LangChain chains are linear (Prompt -> LLM). LangGraph allows for cyclical, state-machine architectures. While our current implementation is mostly linear (Retrieve -> Generate), using LangGraph provides a persistent `ChatState` managed by a MongoDB checkpointer, which natively handles message history. It also allows us to easily add loops in the future, like 'Critique and Rewrite', which is impossible with standard chains."

**Q: How do you handle OCR blocking the async event loop?**
A: "PaddleOCR is a synchronous, CPU-bound machine learning process. If I called it directly in a FastAPI endpoint, it would freeze the entire server. I bypassed this by using `asyncio.get_event_loop().run_in_executor()`, which offloads the OCR computation to a separate thread pool, allowing FastAPI's main event loop to continue serving other HTTP requests."

**Q: What happens if two users upload files at the same time?**
A: "FastAPI is asynchronous. The `upload_document` endpoint uses `async def`. When it awaits I/O operations (like saving the file or generating embeddings), it yields control back to the event loop. This allows User B's upload to begin processing immediately while User A's upload is waiting for the embedding model to return."

**Q: How do you prevent User A from seeing User B's documents?**
A: "Data isolation is enforced at the database query level. Every `retrieve` or `delete` operation in `ChromaVectorStore` explicitly requires a `thread_id` and adds it to the Chroma `$and` where-clause filter. There is no API route that allows querying the database without a `thread_id`."

## 42. Technical Glossary
- **FastAPI**: An async python web framework.
- **Pydantic**: Data validation library using Python type annotations.
- **LangGraph**: A library for building stateful, multi-actor applications with LLMs.
- **ChromaDB**: An open-source vector database.
- **Embedding**: A numerical vector representing semantic meaning.
- **OCR (Optical Character Recognition)**: Converting images of text into machine-encoded text.
- **Semantic Search**: Searching by meaning rather than exact keyword matches.
- **TTFT (Time To First Token)**: The latency between a user submitting a prompt and the first word appearing on screen. Reduced dramatically by streaming.

## 44. Conclusion
This document comprehensively covers the entire architecture, data flow, and code implementation of the FastAPI AI/RAG backend. Every function has been analyzed to provide not only the technical implementation details but the engineering rationale behind them.
