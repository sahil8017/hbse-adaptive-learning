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
    get_book_pyq_counts, get_subject_practice_solved_dict, get_subject_board_passed_dict,
    consume_exam_nonce, cleanup_old_nonces
)
from backend.app.core import database as _db
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
_MAX_UPLOAD_BYTES = 1_000_000

@router.get("/dashboard")
@limiter.limit("30/minute")
async def api_dashboard(request: Request, student: dict = Depends(get_current_student)):
    await apply_mastery_decay(student["id"])
    
    from backend.app.core.database import get_student_by_id

    updated_student = await get_student_by_id(student["id"])
    if not updated_student:
        raise HTTPException(status_code=404, detail="Student not found.")

    now = datetime.now(timezone.utc)
    

    async def build_subject_progress(book_id: str, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        async with _db.get_replica_pool().acquire() as conn:
            progress_dict = await get_subject_reading_progress(updated_student["id"], book_id, conn=conn)
            mastery_dict = await get_subject_mastery_dict(updated_student["id"], book_id, conn=conn)
            practice_solved_dict = await get_subject_practice_solved_dict(updated_student["id"], book_id, conn=conn)
            board_passed_dict = await get_subject_board_passed_dict(updated_student["id"], book_id, conn=conn)
            pyq_counts = await get_book_pyq_counts(book_id)
        total_ch = len(chapters)
        mastered_ch = 0
        completed_ch = 0
        total_reading = 0
        total_mastery = 0
        review_due = False

        for ch in chapters:
            ch_id = ch["id"]
            total_secs = len(ch["sections"])
            completed_sections = progress_dict.get(ch_id, 0)
            read_pct = min(100, int((completed_sections / total_secs) * 100)) if total_secs > 0 else 100
            mastery = mastery_dict.get(ch_id, {
                "student_id": updated_student["id"],
                "book_id": book_id,
                "chapter_id": ch_id,
                "current_tier": 1,
                "consecutive_correct": 0,
                "mastery_percent": 0,
                "status": "locked",
                "locked_until": None,
                "last_reviewed_at": None,
                "review_due_at": None,
            })
            practice_total = pyq_counts.get(ch_id, 0)
            practice_solved = practice_solved_dict.get(ch_id, 0)
            board_passed = board_passed_dict.get(ch_id, False)

            total_reading += read_pct
            total_mastery += mastery.get("mastery_percent", 0)

            if mastery.get("status") == "mastered":
                mastered_ch += 1

            if (mastery.get("status") != "locked"
                    and read_pct >= 100
                    and board_passed
                    and (practice_total == 0 or practice_solved >= practice_total)):
                completed_ch += 1

            due_at = mastery.get("review_due_at")
            if due_at and due_at < now and mastery.get("status") != "locked":
                review_due = True

        return {
            "book_id": book_id,
            "total_chapters": total_ch,
            "mastered_chapters": mastered_ch,
            "completed_chapters": completed_ch,
            "read_percent": int(total_reading / total_ch) if total_ch else 0,
            "mastery_percent": int(total_mastery / total_ch) if total_ch else 0,
            "review_due": review_due
        }

    subjects_progress = await asyncio.gather(
        *(build_subject_progress(book_id, chapters) for book_id, chapters in CHAPTERS_DATA.items())
    )

    try:
        focus_areas = json.loads(updated_student["focus_areas"]) if updated_student.get("focus_areas") else []
    except Exception:
        focus_areas = []
    try:
        unlocked_badges = json.loads(updated_student["unlocked_badges"]) if updated_student.get("unlocked_badges") else []
    except Exception:
        unlocked_badges = []

    return {
            "student": {
                "id": updated_student["id"],
                "username": updated_student["username"],
                "email": updated_student.get("email"),
                "display_name": updated_student.get("display_name"),
                "role": updated_student.get("role") or "student",
                "class_grade": updated_student.get("class_grade") or "Class 9",
                "board": updated_student.get("board") or "HBSE",
                "school": updated_student.get("school"),
                "auth_provider": updated_student.get("auth_provider") or "firebase",
                "streak_count": updated_student.get("streak_count", 0),
            "last_active_date": updated_student.get("last_active_date"),
            "focus_areas": focus_areas,
            "unlocked_badges": unlocked_badges
        },
        "subjects": subjects_progress
    }


@router.get("/dashboard/export")
@limiter.limit("3/minute")
async def api_export(request: Request, student: dict = Depends(get_current_student)):
    data = await export_student_data(student["id"])
    username = student["username"]
    safe_name = re.sub(
        r'[^a-zA-Z0-9_-]',
        '_',
        username
    )[:50]
    filename = f"hbse_progress_{safe_name}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/dashboard/import")
@limiter.limit("2/minute")
async def api_import(request: Request, backup_file: UploadFile = File(...), student: dict = Depends(get_current_student)):
    contents = await backup_file.read(_MAX_UPLOAD_BYTES + 1)
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Backup file too large (max 1 MB).")

    try:
        backup_data = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in backup file.")

    try:
        success = await import_student_data(student["username"], backup_data)
    except Exception:
        logger.exception("Error during import for user %s", student["username"])
        raise HTTPException(status_code=500, detail="Import failed due to a server error.")

    if not success:
        raise HTTPException(status_code=500, detail="Import failed: database error.")

    return {"ok": True}


# ===========================================================================
# PARENT / TEACHER SHARE LINK  (Step 17)
# ===========================================================================

from backend.app.core.security import create_share_token, decode_share_token

@router.post("/dashboard/share-link")
async def create_share_link(student: dict = Depends(get_current_student)):
    """Generate a 7-day signed read-only progress link for parents/teachers."""
    token = create_share_token(student_id=student["id"], expires_days=7)
    base_url = settings.FRONTEND_URL.rstrip("/")
    return {"url": f"{base_url}/progress/{token}"}


@router.get("/dashboard/view/{token}")
@limiter.limit("20/minute")
async def view_shared_progress(request: Request, token: str):
    """
    Public endpoint — no auth required.
    Decodes a share token and returns a progress snapshot for parent/teacher view.
    """
    student_id = decode_share_token(token)
    if not student_id:
        raise HTTPException(status_code=404, detail="This progress link has expired or is invalid.")

    async with _db.db_pool.acquire() as conn:
        student_row = await conn.fetchrow(
            "SELECT id, username, streak_count, unlocked_badges FROM students WHERE id=$1", student_id
        )
    if not student_row:
        raise HTTPException(status_code=404, detail="Student not found.")

    student_data = dict(student_row)
    try:
        student_data["unlocked_badges"] = json.loads(student_data.get("unlocked_badges") or "[]")
    except Exception:
        student_data["unlocked_badges"] = []

    # Subject-level mastery summary
    subjects_summary = {}
    async with _db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT book_id, chapter_id, mastery_percent, status
            FROM student_mastery WHERE student_id=$1
            ORDER BY book_id, chapter_id
            """,
            student_id,
        )
    for r in rows:
        book = r["book_id"]
        if book not in subjects_summary:
            subjects_summary[book] = {"chapters": [], "avg_mastery": 0}
        subjects_summary[book]["chapters"].append({
            "chapter_id": r["chapter_id"],
            "mastery_percent": r["mastery_percent"],
            "status": r["status"],
        })

    for book_data in subjects_summary.values():
        if book_data["chapters"]:
            book_data["avg_mastery"] = round(
                sum(c["mastery_percent"] for c in book_data["chapters"]) / len(book_data["chapters"]), 1
            )

    # Recent exam history (last 10 attempts)
    async with _db.db_pool.acquire() as conn:
        exam_rows = await conn.fetch(
            """
            SELECT book_id, chapter_id, score, passed, timestamp
            FROM exam_attempts WHERE student_id=$1
            ORDER BY timestamp DESC LIMIT 10
            """,
            student_id,
        )
    exam_history = [
        {
            "book_id": r["book_id"],
            "chapter_id": r["chapter_id"],
            "score_percent": r["score"],
            "passed": bool(r["passed"]),
            "attempted_at": r["timestamp"].isoformat() if r["timestamp"] else None,
        }
        for r in exam_rows
    ]

    return {
        "student": {
            "username": student_data["username"],
            "streak_count": student_data["streak_count"],
            "unlocked_badges": student_data["unlocked_badges"],
        },
        "subjects": subjects_summary,
        "exam_history": exam_history,
    }


# ===========================================================================
# PER-SUBJECT RE-DIAGNOSTIC  (Step 18)
# ===========================================================================

@router.post("/diagnostic/retest/{book_id}")
async def request_subject_retest(book_id: str, student: dict = Depends(get_current_student)):
    """
    Unlock a per-subject re-diagnostic when mastery has dropped below 40%.
    Resets the first chapter's tier to 1 so the student is re-placed.
    """
    # Check subject average mastery
    async with _db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT mastery_percent FROM student_mastery WHERE student_id=$1 AND book_id=$2",
            student["id"], book_id,
        )

    if not rows:
        raise HTTPException(status_code=404, detail=f"No mastery data found for {book_id}.")

    avg_mastery = sum(r["mastery_percent"] for r in rows) / len(rows)
    if avg_mastery > 40:
        raise HTTPException(
            status_code=400,
            detail=f"Re-test is only available when your average mastery for {book_id} drops below 40% (currently {avg_mastery:.0f}%).",
        )

    # Reset the first chapter to tier 1 for re-placement
    async with _db.db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE student_mastery
            SET current_tier = 1, consecutive_correct = 0, status = 'in_progress'
            WHERE student_id = $1 AND book_id = $2
              AND chapter_id = (
                SELECT chapter_id FROM student_mastery
                WHERE student_id = $1 AND book_id = $2
                ORDER BY chapter_id LIMIT 1
              )
            """,
            student["id"], book_id,
        )

    return {"ok": True, "message": f"Re-diagnostic unlocked for {book_id}. Start your first chapter to be re-placed."}
