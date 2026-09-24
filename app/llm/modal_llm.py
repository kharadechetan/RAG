from langchain_openai import ChatOpenAI
from app.config import settings

def get_modal_llm():
    # OpenAI SDK needs /v1 in base_url because the server exposes: POST /v1/chat/completions
    base_url = f"{settings.modal_llm_url.rstrip('/')}/v1"
    
    # We wrap ChatOpenAI configured for the Modal endpoint
    # This natively supports ainvoke() and astream() producing real token chunks
    return ChatOpenAI(
        model="phi-3-mini-4k-instruct", # Name must match the expected model in the custom server
        api_key="not-needed",
        base_url=base_url,
        timeout=180.0,
        streaming=True
    )
