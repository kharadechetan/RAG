"""
Centralized RAG prompt template.

Two variants:
  - With document context (when retrieval found relevant chunks)
  - Without document context (normal conversation)
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from app.config import settings


RAG_PROMPT_WITH_CONTEXT = ChatPromptTemplate.from_messages(
    [
        ("system", settings.system_prompt + "\n\nDocument context:\n{context}"),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}"),
    ]
)

RAG_PROMPT_NO_CONTEXT = ChatPromptTemplate.from_messages(
    [
        ("system", settings.system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{question}"),
    ]
)
