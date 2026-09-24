"""
LangGraph RAG workflow nodes.

Node pipeline:
  prepare_query → retrieve_documents → build_context → generate_answer → attach_sources
"""
import time
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from app.config import settings
from app.documents.vectorstore.chroma import chroma_store
from app.llm.factory import get_chat_model
from app.graph.prompts import RAG_PROMPT_WITH_CONTEXT, RAG_PROMPT_NO_CONTEXT
import logging

_reranker = None
def get_reranker():
    global _reranker
    if _reranker is None and settings.enable_reranking:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(settings.rerank_model)
        except Exception as e:
            logging.error(f"Failed to load reranker {settings.rerank_model}: {e}")
            _reranker = False # disable permanently on fail
    return _reranker


import re

def should_use_rag(question: str) -> bool:
    """
    Lightweight deterministic routing to skip RAG for purely conversational queries.
    Conservatively defaults to True (use RAG) for ambiguous queries.
    """
    q_clean = re.sub(r'[^\w\s]', '', question.strip().lower())
    
    # 1. Very short obvious conversational phrases
    conversational_phrases = {
        "hi", "hello", "hey", "hola",
        "good morning", "good afternoon", "good evening", "goodnight", "good night",
        "how are you", "whats up", "hows it going", "how are you doing",
        "thanks", "thank you", "appreciate it", "thanks a lot", "thank you so much",
        "bye", "goodbye", "see you", "see ya", "cya", "farewell",
        "who are you", "what are you", "tell me about yourself", "are you a bot", "are you an ai",
        "tell me a joke", "say a joke", "joke",
        "ok", "okay", "cool", "awesome", "great", "nice", "good", "perfect", "yes", "no", "yep", "nope",
        "wow", "lol", "haha"
    }
    
    if q_clean in conversational_phrases:
        return False
        
    # 2. Short conversational starters (e.g. "hi there")
    if q_clean.startswith(("hi ", "hello ", "hey ")) and len(q_clean.split()) <= 3:
        return False
        
    # 3. Everything else defaults to RAG to preserve document context
    return True


# ------------------------------------------------------------------
# 1. prepare_query — extract the latest human question and thread_id
# ------------------------------------------------------------------

async def prepare_query(state: dict, config: RunnableConfig) -> dict:
    thread_id = config.get("configurable", {}).get("thread_id", "")
    messages = state.get("messages", [])

    # Find the latest human message
    question = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and isinstance(msg.content, str):
            question = msg.content
            break

    # RAG routing decision
    rag_required = should_use_rag(question)
    
    print(f"[CHAT] Query received")
    print(f"[CHAT] RAG decision: {'true' if rag_required else 'false'}")

    return {
        "question": question,
        "thread_id": thread_id,
        "rag_required": rag_required,
        "retrieved_documents": [],
        "context": "",
        "sources": [],
        "retrieval_latency": 0.0,
        "reranking_latency": 0.0,
        "generation_latency": 0.0,
        "total_latency": 0.0,
    }


# ------------------------------------------------------------------
# 2. retrieve_documents — embedding + Chroma similarity search
# ------------------------------------------------------------------

async def retrieve_documents(state: dict, config: RunnableConfig) -> dict:
    question = state.get("question", "")
    thread_id = state.get("thread_id", "")

    if not question or not thread_id:
        return {"retrieved_documents": [], "retrieval_latency": 0.0}

    t0 = time.perf_counter()
    try:
        k = settings.rerank_top_k if settings.enable_reranking else settings.top_k
        docs = chroma_store.retrieve(
            query=question,
            thread_id=thread_id,
            n_results=k,
        )
    except Exception as e:
        print(f"[RAG] Retrieval failed: {e}")
        docs = []

    reranking_latency = 0.0
    if settings.enable_reranking and docs:
        reranker = get_reranker()
        if reranker:
            t1 = time.perf_counter()
            pairs = [[question, doc.page_content] for doc in docs]
            scores = reranker.predict(pairs)
            scored_docs = list(zip(docs, scores))
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            docs = [doc for doc, score in scored_docs[:settings.final_context_k]]
            reranking_latency = time.perf_counter() - t1

    latency = time.perf_counter() - t0
    print(f"[RAG] Retrieval: {latency:.3f}s — {len(docs)} chunks")
    return {"retrieved_documents": docs, "retrieval_latency": latency, "reranking_latency": reranking_latency}


# ------------------------------------------------------------------
# 3. build_context — format retrieved docs into a numbered context string
# ------------------------------------------------------------------

async def build_context(state: dict, config: RunnableConfig) -> dict:
    docs = state.get("retrieved_documents", [])

    # Limit to max_context_chunks
    docs = docs[: settings.max_context_chunks]

    if not docs:
        return {"context": "", "retrieved_documents": []}

    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        filename = meta.get("filename", "unknown")
        page = meta.get("page_number", "?")
        parts.append(
            f"SOURCE {i}\nDocument: {filename}\nPage: {page}\n\n{doc.page_content}"
        )

    context = "\n\n---\n\n".join(parts)
    return {"context": context, "retrieved_documents": docs}


# ------------------------------------------------------------------
# 4. generate_answer — invoke the LLM via the provider factory
# ------------------------------------------------------------------

async def generate_answer(state: dict, config: RunnableConfig) -> dict:
    question = state.get("question", "")
    context = state.get("context", "")
    messages = state.get("messages", [])

    # Build bounded chat history (exclude the latest human message — it's the question)
    chat_history = []
    for msg in messages[:-1]:  # everything except the last message
        if isinstance(msg, (HumanMessage, AIMessage)):
            chat_history.append(msg)
    # Keep only last 10 messages for context window management
    chat_history = chat_history[-10:]

    llm = get_chat_model()

    # Pick prompt based on whether retrieval found documents
    has_context = bool(context.strip())
    if has_context:
        prompt = RAG_PROMPT_WITH_CONTEXT
    else:
        prompt = RAG_PROMPT_NO_CONTEXT

    chain = prompt | llm

    t0 = time.perf_counter()
    try:
        invoke_args = {"chat_history": chat_history, "question": question}
        if has_context:
            invoke_args["context"] = context
        response = await chain.ainvoke(invoke_args)
    except Exception as e:
        print(f"[RAG] Generation failed: {e}")
        error_text = "I'm sorry, I encountered an error generating a response. Please try again."
        response = AIMessage(content=error_text)

    latency = time.perf_counter() - t0
    retrieval = state.get("retrieval_latency", 0.0)
    total = retrieval + latency
    rag_req = state.get("rag_required", True)
    
    if rag_req:
        print(f"[RAG] Generation: {latency:.3f}s")
    else:
        print(f"[CHAT] Generation: {latency:.3f}s")
        
    print(f"[CHAT] Total user-facing latency: {total:.3f}s")

    return {
        "messages": [response],
        "generation_latency": latency,
        "total_latency": total,
    }


# ------------------------------------------------------------------
# 5. attach_sources — build verified citations from retrieval metadata
# ------------------------------------------------------------------

async def attach_sources(state: dict, config: RunnableConfig) -> dict:
    docs = state.get("retrieved_documents", [])

    # No sources if retrieval didn't find anything (normal conversation)
    if not docs:
        return {"sources": []}

    seen = set()
    sources = []
    for doc in docs:
        meta = doc.metadata or {}
        key = (meta.get("filename", ""), meta.get("page_number", ""))
        if key not in seen:
            seen.add(key)
            doc_id = meta.get("document_id", "")
            thread_id = meta.get("thread_id", "")
            url = f"{settings.server_url}/documents/{doc_id}/download?thread_id={thread_id}" if doc_id and thread_id else ""
            sources.append({
                "filename": meta.get("filename", "unknown"),
                "page_number": meta.get("page_number"),
                "document_id": doc_id,
                "url": url
            })

    return {"sources": sources}
