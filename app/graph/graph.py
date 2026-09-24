"""
LangGraph RAG workflow.

Pipeline:
  START → prepare_query → retrieve_documents → build_context
        → generate_answer → attach_sources → END
"""
from langgraph.graph import StateGraph, START, END
from app.graph.state import ChatState
from app.graph.nodes import (
    prepare_query,
    retrieve_documents,
    build_context,
    generate_answer,
    attach_sources,
)
from app.database.mongodb import db_store


def route_rag(state: ChatState) -> str:
    """Route to retrieve_documents if RAG is required, else skip straight to generate_answer."""
    if state.get("rag_required", True):
        return "retrieve_documents"
    return "generate_answer"


def build_graph():
    graph = StateGraph(ChatState)

    graph.add_node("prepare_query", prepare_query)
    graph.add_node("retrieve_documents", retrieve_documents)
    graph.add_node("build_context", build_context)
    graph.add_node("generate_answer", generate_answer)
    graph.add_node("attach_sources", attach_sources)

    graph.add_edge(START, "prepare_query")
    
    # Conditional edge after preparing the query
    graph.add_conditional_edges(
        "prepare_query",
        route_rag,
        {
            "retrieve_documents": "retrieve_documents",
            "generate_answer": "generate_answer"
        }
    )
    
    graph.add_edge("retrieve_documents", "build_context")
    graph.add_edge("build_context", "generate_answer")
    graph.add_edge("generate_answer", "attach_sources")
    graph.add_edge("attach_sources", END)

    return graph.compile(checkpointer=db_store.checkpointer)
