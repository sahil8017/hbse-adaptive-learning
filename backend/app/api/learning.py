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

@router.get("/meta/subjects")
async def api_subject_catalog():
    catalog = get_subject_catalog()
    ordered_subjects = []
    for book_id in CHAPTERS_DATA:
        if book_id not in catalog:
            continue
        meta = dict(catalog[book_id])
        meta.pop("prompt_config_path", None)
        meta.pop("prompt_guard_key", None)
        ordered_subjects.append(meta)
    return {"subjects": ordered_subjects}

# ===========================================================================
# AUTH
# ===========================================================================

@router.get("/subject/{book_id}/chapters")
async def api_subject_chapters(book_id: str, student: dict = Depends(get_current_student)):
    chapters = CHAPTERS_DATA.get(book_id)
    if not chapters:
        raise HTTPException(status_code=404, detail="Subject not found")

    now = datetime.now(timezone.utc)
    result_chapters = []

    # Batch load all per-subject data in parallel
    progress_dict, mastery_dict, practice_solved_dict, board_passed_dict, pyq_counts = await asyncio.gather(
        get_subject_reading_progress(student["id"], book_id),
        get_subject_mastery_dict(student["id"], book_id),
        get_subject_practice_solved_dict(student["id"], book_id),
        get_subject_board_passed_dict(student["id"], book_id),
        get_book_pyq_counts(book_id),
    )

    # First chapter is always unlockable; subsequent chapters unlock when previous is complete
    previous_complete = True

    for ch in chapters:
        ch_id = ch["id"]
        total_secs = len(ch["sections"])

        completed_sections = progress_dict.get(ch_id, 0)
        read_pct = min(100, int((completed_sections / total_secs) * 100)) if total_secs > 0 else 100

        mastery = mastery_dict.get(ch_id)
        if not mastery:
            mastery = {
                "student_id": student["id"],
                "book_id": book_id,
                "chapter_id": ch_id,
                "current_tier": 1,
                "consecutive_correct": 0,
                "mastery_percent": 0,
                "status": "locked",
                "locked_until": None,
                "last_reviewed_at": None,
                "review_due_at": None
            }

        practice_total = pyq_counts.get(ch_id, 0)
        practice_solved = practice_solved_dict.get(ch_id, 0)
        board_passed = board_passed_dict.get(ch_id, False)

        status = mastery["status"]
        if previous_complete and status == "locked":
            status = "in_progress"
            await update_student_mastery(student["id"], book_id, ch_id, status="in_progress")
            mastery["status"] = status

        review_due = False
        due_at = mastery.get("review_due_at")
        if due_at and due_at < now and status != "locked":
            review_due = True

        # Chapter is fully complete when all three criteria are met
        chapter_complete = (
            status != "locked"
            and read_pct >= 100
            and board_passed
            and (practice_total == 0 or practice_solved >= practice_total)
        )

        result_chapters.append({
            "id": ch["id"],
            "title": ch["title"],
            "sub_category": ch.get("sub_category", "Core"),
            "read_percent": read_pct,
            "mastery_percent": mastery.get("mastery_percent", 0),
            "current_tier": mastery.get("current_tier", 1),
            "status": status,
            "review_due": review_due,
            "locked": status == "locked",
            "practice_total": practice_total,
            "practice_solved": practice_solved,
            "board_passed": board_passed,
            "chapter_complete": chapter_complete,
        })

        previous_complete = chapter_complete

    return result_chapters

# ===========================================================================
# CHAPTER READING
# ===========================================================================

@router.get("/subject/{book_id}/chapter/{chapter_id}")
async def api_chapter(book_id: str, chapter_id: str, student: dict = Depends(get_current_student)):
    chapters = CHAPTERS_DATA.get(book_id, [])
    chapter  = next((c for c in chapters if c["id"] == chapter_id), None)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found.")

    total_secs = len(chapter["sections"])
    read_pct   = await get_chapter_reading_percent(student["id"], book_id, chapter_id, total_secs)
    mastery    = await get_student_mastery(student["id"], book_id, chapter_id)
    completed_sections = await get_completed_sections(student["id"], book_id, chapter_id)

    return {
        "chapter":            chapter,
        "read_percent":       read_pct,
        "mastery":            mastery,
        "completed_sections": completed_sections,
    }


@router.post("/subject/{book_id}/chapter/{chapter_id}/read/{section_id}")
async def api_mark_read(book_id: str, chapter_id: str, section_id: str, body: MarkReadRequest, student: dict = Depends(get_current_student)):
    completed = 1 if body.completed else 0
    await update_reading_progress(student["id"], book_id, chapter_id, section_id, completed)

    chapters     = CHAPTERS_DATA.get(book_id, [])
    chapter      = next((c for c in chapters if c["id"] == chapter_id), None)
    total_secs   = len(chapter["sections"]) if chapter else 0
    read_pct     = await get_chapter_reading_percent(student["id"], book_id, chapter_id, total_secs)

    return {"read_percent": read_pct}

# ===========================================================================
# ADAPTIVE PRACTICE
# ===========================================================================

@router.get("/textbook/{book_id}/{chapter_id}")
async def api_get_textbook_chapter(book_id: str, chapter_id: str, student: dict = Depends(get_current_student)):
    subj_folder = book_id.lower()
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(base, "data", "textbook", subj_folder, f"{chapter_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Textbook file not found.")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Error reading textbook file.")


@router.get("/textbook/{book_id}/{chapter_id}/{section_id}")
async def api_get_textbook_section(book_id: str, chapter_id: str, section_id: str, student: dict = Depends(get_current_student)):
    subj_folder = book_id.lower()
    
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(base, "data", "textbook", subj_folder, f"{chapter_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Textbook file not found.")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            ch_data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Error reading textbook file.")
        
    if "reading_nodes" in ch_data:
        nodes = ch_data.get("reading_nodes", [])
        node = next((n for n in nodes if n.get("node_id") == section_id), None)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found in textbook.")
        return {
            "section_id": section_id,
            "title": node.get("node_title", ""),
            "content": node.get("content", ""),
            "key_terms": node.get("inline_glossary", {}),
            "formulas": [],
        }
    else:
        sections = ch_data.get("sections", {})
        sec = sections.get(section_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found in textbook.")
        return {
            "section_id": section_id,
            "title": sec.get("title", ""),
            "content": sec.get("content", ""),
            "key_terms": sec.get("key_terms", {}),
            "formulas": sec.get("formulas", []),
        }


@router.get("/textbook/{book_id}/{chapter_id}/{section_id}/simplify")
async def api_simplify_textbook_section(book_id: str, chapter_id: str, section_id: str, student: dict = Depends(get_current_student)):
    subj_folder = book_id.lower()
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    filepath = os.path.join(base, "data", "textbook", subj_folder, f"{chapter_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Textbook file not found.")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            ch_data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Error reading textbook file.")
        
    if "reading_nodes" in ch_data:
        nodes = ch_data.get("reading_nodes", [])
        node = next((n for n in nodes if n.get("node_id") == section_id), None)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found in textbook.")
        content = node.get("content", "")
    else:
        sections = ch_data.get("sections", {})
        sec = sections.get(section_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found in textbook.")
        content = sec.get("content", "")
    

    async def stream_generator():
        try:
            async for token in get_simplify_explanation_stream(content):
                yield f"data: {json.dumps({'text': token})}\n\n"
        except Exception as e:
            logger.error("Error in simplify stream endpoint: %s", e)
            yield f"data: {json.dumps({'text': 'System offline. Unable to generate AI summary.'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    return StreamingResponse(stream_generator(), media_type="text/event-stream")


