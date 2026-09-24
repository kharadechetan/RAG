from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    # Conversation messages — LangGraph reducer appends new messages
    messages: Annotated[list, add_messages]
    # RAG fields populated during the workflow
    question: str
    thread_id: str
    rag_required: bool
    retrieved_documents: list  # LangChain Document objects
    context: str
    sources: list  # verified citation dicts
    retrieval_latency: float
    reranking_latency: float
    generation_latency: float
    total_latency: float
