from pydantic import BaseModel

class ReportAnomalyRequest(BaseModel):
    type: str
    book_id: str
    chapter_id: str
