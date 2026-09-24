from pydantic import BaseModel
from datetime import datetime

class ThreadResponse(BaseModel):
    thread_id: str
    created_at: datetime
    updated_at: datetime

class ThreadDeleteResponse(BaseModel):
    success: bool
    thread_id: str
