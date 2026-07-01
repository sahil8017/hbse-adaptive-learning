from pydantic import BaseModel
from typing import Dict

class ExamSubmit(BaseModel):
    answers: Dict[str, int]
    exam_token: str
