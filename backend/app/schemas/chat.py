from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ChatAskRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    book_id: Optional[str] = None
    chapter_id: Optional[str] = None
    section_id: Optional[str] = None
    session_id: Optional[str] = None
    history: List[Dict[str, Any]] = []
    tab_id: Optional[str] = None
