from pydantic import BaseModel

class MarkReadRequest(BaseModel):
    completed: bool = True

class PracticeSubmitRequest(BaseModel):
    question_id: int
    user_answer: int

class GradeOpenRequest(BaseModel):
    question_id: int
    user_answer: str

class ReportDwellRequest(BaseModel):
    concept: str
    dwell_seconds: int
