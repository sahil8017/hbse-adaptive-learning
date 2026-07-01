import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import uuid
import re

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Depends, status, Response
from fastapi.responses import StreamingResponse, JSONResponse

from backend.app.core.config import settings, CHAPTERS_DATA
from backend.app.core.security import (
    _validate_username, _safe_int, _sign_exam, _verify_exam_sig,
    get_current_student,
    create_exam_token, decode_exam_token
)
from backend.app.core.database import (
    create_student, get_student_by_username, apply_mastery_decay,
    get_student_mastery, update_student_mastery, get_chapter_reading_percent,
    update_reading_progress, get_adaptive_questions, get_board_exam_questions,
    create_exam_attempt, export_student_data, import_student_data,
    add_anomaly, save_chat_message, get_chat_history, update_review_timestamp,
    get_diagnostic_questions, get_diagnostic_questions_meta,
    get_completed_sections, add_student_focus_area, get_question_text,
    fetch_question, fetch_questions_bulk, check_and_unlock_badge, get_subject_reading_progress,
    get_subject_mastery_dict, get_chapter_pyq_mcqs,
    consume_exam_nonce, cleanup_old_nonces
)
from backend.app.services.adaptive import (
    determine_subject_tier, process_practice_answer, grade_subjective_answer,
    get_tutor_chat_stream,
    get_simplify_explanation_stream, tutor_config,
    get_openrouter_completion
)
from backend.app.services.rag import get_relevant_context
from backend.app.services.subject_catalog import get_subject_catalog, get_subject_meta, get_subject_prompt_config
from backend.app.core.limiter import limiter

# Import Pydantic schemas
from backend.app.schemas.auth import LoginRequest, LoginResponse, StudentOut
from backend.app.schemas.learning import MarkReadRequest, PracticeSubmitRequest, GradeOpenRequest, ReportDwellRequest
from backend.app.schemas.chat import ChatAskRequest
from backend.app.schemas.exam import ExamSubmit
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

