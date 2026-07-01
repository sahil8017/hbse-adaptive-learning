import logging

from fastapi import APIRouter, Request, Depends

from backend.app.core.security import (
    get_current_student
)
from backend.app.core.database import (
    add_anomaly
)
from backend.app.core.limiter import limiter

# Import Pydantic schemas
from backend.app.schemas.analytics import ReportAnomalyRequest


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/analytics/report-anomaly")
@limiter.limit("10/minute")
async def api_report_anomaly(request: Request, body: ReportAnomalyRequest, student: dict = Depends(get_current_student)):
    logger.warning(
        f"ANOMALY DETECTED for student {student['username']}: "
        f"Type: {body.type}, Book: {body.book_id}, Chapter: {body.chapter_id}"
    )
    await add_anomaly(student["id"], body.type, body.book_id, body.chapter_id)
    return {"ok": True, "action": "logged"}

# ===========================================================================
# DOUBTS AI CHATBOT
# ===========================================================================

