from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: Optional[str] = "gpt-3.5-turbo"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000

class ChatResponse(BaseModel):
    role: str
    content: str

class OutlineRequest(BaseModel):
    prompt: str
    pageCount: int

class OutlineResponse(BaseModel):
    chapters: List[dict]

class ChapterContent(BaseModel):
    chapter_id: int
    content: str

class ResponseBreakdownRequest(BaseModel):
    chapter_title: str
    content: str
    sections: List[str]
    total_word_count: int
    response_word_limit: Optional[int] = None 