from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class StudentOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: str = "student"
    class_grade: str = "Class 9"
    board: str = "HBSE"
    school: Optional[str] = None
    auth_provider: str = "firebase"
    streak_count: int
    last_active_date: Optional[datetime] = None
    focus_areas: List[str] = []
    unlocked_badges: List[str] = []


class FirebaseSessionRequest(BaseModel):
    id_token: str = Field(..., min_length=32)
    display_name: str = ""
    role: str = "student"
    class_grade: str = "Class 9"
    board: str = "HBSE"
    school: str = ""
    _hp: str = ""


class AuthSessionResponse(BaseModel):
    student: StudentOut
    is_new: bool
    needs_diagnostic: bool
    auth_provider: str = "firebase"


class ShareLinkResponse(BaseModel):
    url: str


LoginRequest = FirebaseSessionRequest
LoginResponse = AuthSessionResponse
