from pydantic import BaseModel, Field

class MessageRequest(BaseModel):
    thread_id: str = Field(..., min_length=1, description="The unique thread ID")
    message: str = Field(..., min_length=1, description="The user message to send")

class MessageResponse(BaseModel):
    role: str
    content: str
