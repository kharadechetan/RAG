"""
Provider-agnostic LLM factory.

Selects the chat model based on settings.llm_provider.
Currently implements: openai.
Adding a new provider requires only a new elif branch here.
"""
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import settings


def get_chat_model() -> BaseChatModel:
    provider = settings.llm_provider.lower()

    if provider == "openai":
        return _get_openai_chat_model()

    # Example future providers — uncomment when needed:
    # if provider == "anthropic":
    #     return _get_anthropic_chat_model()
    # if provider == "ollama":
    #     return _get_ollama_chat_model()

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        f"Supported: openai"
    )


def _get_openai_chat_model() -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    # If the user specifically configures a local model or the default openai_chat_model
    model_name = settings.openai_chat_model if settings.openai_chat_model else "Qwen/Qwen2.5-0.5B-Instruct"
    api_key = settings.openai_api_key if settings.openai_api_key else "local"
    
    # Check if we should use local proxy based on model name or lack of real API key
    if "qwen" in model_name.lower() or api_key == "local":
        base_url = "http://127.0.0.1:8080/v1"
    else:
        base_url = None # Default OpenAI

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=settings.temperature,
        max_tokens=settings.llm_max_tokens,
        streaming=True,
    )
