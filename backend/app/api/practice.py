import json
import logging
import base64
from typing import Optional, List, Dict, Any
import uuid

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import StreamingResponse

from backend.app.core.security import (
    get_current_student
)
from backend.app.core.database import (
    get_student_mastery, get_adaptive_questions, get_board_exam_questions,
    update_review_timestamp,
    add_student_focus_area, get_question_text,
    fetch_question, get_chapter_pyq_mcqs,
    record_practice_attempt
)
from backend.app.services.adaptive import (
    process_practice_answer, grade_subjective_answer,
    get_practice_hint_stream, get_practice_chat_stream
)
from backend.app.services.cache_invalidation import CacheInvalidation
from backend.app.services.rag import get_relevant_context
from backend.app.core.limiter import limiter
from backend.app.core.prompt_security import contains_prompt_injection, sanitize_history

# Import Pydantic schemas
from backend.app.schemas.learning import PracticeSubmitRequest, GradeOpenRequest, ReportDwellRequest


from backend.app.api.utils import _normalize_question_options, _load_textbook_chapter_data, _extract_chapter_text_fragments

logger = logging.getLogger(__name__)

router = APIRouter()

def _build_dynamic_open_practice_question(book_id: str, chapter_id: str, tier: int = 3) -> Optional[Dict[str, Any]]:
    chapter_data = _load_textbook_chapter_data(book_id, chapter_id)
    if not chapter_data:
        return None

    chapter_title = chapter_data.get("title") or chapter_id
    fragments = _extract_chapter_text_fragments(chapter_data)
    if not fragments:
        return None

    section_labels: List[str] = []
    if isinstance(chapter_data.get("sections"), dict):
        for section in chapter_data["sections"].values():
            if isinstance(section, dict) and section.get("title"):
                section_labels.append(str(section["title"]))
    elif isinstance(chapter_data.get("reading_nodes"), list):
        for node in chapter_data["reading_nodes"]:
            if isinstance(node, dict) and node.get("title"):
                section_labels.append(str(node["title"]))

    focus = ", ".join(section_labels[:2]) if section_labels else chapter_title
    synthetic_id = -((uuid.uuid5(uuid.NAMESPACE_URL, f"{book_id}:{chapter_id}").int % 1_000_000) + 1)
    prompt = (
        f"In your own words, explain the main idea of the chapter \"{chapter_title}\". "
        f"Use at least one concept, rule, example, or definition from {focus}. "
        "Keep the answer clear and suitable for a Class 9 student."
    )

    return {
        "id": synthetic_id,
        "text": prompt,
        "options": [],
        "subtopic": chapter_title,
        "question_type": "open",
        "is_dynamic": True,
        "tier": tier,
    }


def _get_dynamic_practice_context(book_id: str, chapter_id: str) -> str:
    chapter_data = _load_textbook_chapter_data(book_id, chapter_id)
    if not chapter_data:
        return ""
    fragments = _extract_chapter_text_fragments(chapter_data)
    return "\n\n".join(fragments[:3])[:3000]


@router.get("/subject/{book_id}/chapter/{chapter_id}/practice")
async def api_get_practice(
    book_id: str,
    chapter_id: str,
    retry_q_id: Optional[int] = None,
    student: dict = Depends(get_current_student)
):
    mastery = await get_student_mastery(student["id"], book_id, chapter_id)
    current_tier = mastery.get("current_tier", 3)

    if retry_q_id is not None:
        question = _build_dynamic_open_practice_question(book_id, chapter_id, current_tier) if retry_q_id < 0 else await fetch_question(retry_q_id)
    else:
        questions = await get_adaptive_questions(book_id, chapter_id, current_tier, limit=1)
        if not questions:
            if book_id.lower() == "mathematics":
                questions = await get_chapter_pyq_mcqs(book_id, chapter_id)
            if not questions:
                questions = await get_board_exam_questions(book_id, chapter_id, limit=1)

        question = questions[0] if questions else None
        if question and not question.get("question_type"):
            question["question_type"] = "mcq" if question.get("options") else "open"
        if question:
            question["options"] = _normalize_question_options(question.get("options"))

        if not question:
            question = _build_dynamic_open_practice_question(book_id, chapter_id, current_tier)

    if question:
        question.pop("correct_answer", None)

    return {"question": question, "mastery": mastery}


@router.post("/subject/{book_id}/chapter/{chapter_id}/practice/submit")
@limiter.limit("30/minute")
async def api_practice_submit(request: Request, book_id: str, chapter_id: str, body: PracticeSubmitRequest, student: dict = Depends(get_current_student)):
    question = await fetch_question(body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    options = _normalize_question_options(question.get("options"))
    if body.user_answer < 0 or body.user_answer >= len(options):
        raise HTTPException(status_code=400, detail="user_answer is out of range.")

    correct_answer = question["correct_answer"]
    is_correct = (body.user_answer == correct_answer)

    new_tier, consecutive_correct, promoted = await process_practice_answer(
        student["id"], book_id, chapter_id, is_correct
    )

    if question.get("is_pyq"):
        await record_practice_attempt(student["id"], book_id, chapter_id, body.question_id, is_correct)

    await update_review_timestamp(student["id"], book_id, chapter_id)
    await CacheInvalidation.on_practice_submit(student["id"], chapter_id, book_id)
    mastery = await get_student_mastery(student["id"], book_id, chapter_id)

    context = None
    if not is_correct:
        context = await get_relevant_context(book_id, chapter_id, question["text"])

    question.pop("correct_answer", None)

    return {
        "is_correct":          is_correct,
        "promoted":            promoted,
        "new_tier":            new_tier,
        "consecutive_correct": consecutive_correct,
        "mastery":             mastery,
        "question":            question,
        "context":             context,
        "student_answer_text": options[body.user_answer] if not is_correct else None,
    }


@router.post("/subject/{book_id}/chapter/{chapter_id}/practice/grade-open")
@limiter.limit("10/minute")
async def api_grade_open(request: Request, book_id: str, chapter_id: str, body: GradeOpenRequest, student: dict = Depends(get_current_student)):
    if contains_prompt_injection(body.user_answer):
        raise HTTPException(status_code=400, detail="Prompt-injection style instructions are not allowed.")

    if body.question_id < 0:
        question = _build_dynamic_open_practice_question(book_id, chapter_id)
        context = _get_dynamic_practice_context(book_id, chapter_id)
    else:
        question = await fetch_question(body.question_id)
        context = await get_relevant_context(book_id, chapter_id, question["text"]) if question else None

    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")
    
    grade_res = await grade_subjective_answer(question["text"], context or "", body.user_answer)
    
    score = grade_res.get("score", 5)
    feedback = grade_res.get("feedback", "Answer evaluated.")
    is_correct = score >= 6
    
    new_tier, consecutive_correct, promoted = await process_practice_answer(
        student["id"], book_id, chapter_id, is_correct
    )

    if body.question_id > 0 and question.get("is_pyq"):
        await record_practice_attempt(student["id"], book_id, chapter_id, body.question_id, is_correct)

    await update_review_timestamp(student["id"], book_id, chapter_id)
    await CacheInvalidation.on_practice_submit(student["id"], chapter_id, book_id)
    mastery = await get_student_mastery(student["id"], book_id, chapter_id)

    return {
        "score": score,
        "feedback": feedback,
        "is_correct": is_correct,
        "promoted": promoted,
        "new_tier": new_tier,
        "consecutive_correct": consecutive_correct,
        "mastery": mastery,
        "question": question
    }


@router.post("/practice/report-dwell")
async def api_report_dwell(body: ReportDwellRequest, student: dict = Depends(get_current_student)):
    if body.dwell_seconds > 600 or body.dwell_seconds < 300:
        return {"ok": True, "action": "ignored"}
        
    focus_areas = await add_student_focus_area(student["id"], body.concept)
    return {"ok": True, "action": "flagged", "focus_areas": focus_areas}


@router.get("/subject/{book_id}/chapter/{chapter_id}/practice/stream")
@limiter.limit("10/minute")
async def api_practice_stream(
    request: Request,
    book_id: str,
    chapter_id: str,
    question_id: int,
    student_ans: str = "",
    student: dict = Depends(get_current_student),
):
    student_ans = student_ans[:300]
    if contains_prompt_injection(student_ans):
        raise HTTPException(status_code=400, detail="Prompt-injection style instructions are not allowed.")

    question_text = await get_question_text(question_id)
    if not question_text:
        question_text = "Class 9 textbook exercise question."
    context = await get_relevant_context(book_id, chapter_id, question_text)


    async def event_generator():
        async for token in get_practice_hint_stream(question_text, context, student_ans):
            yield f"data: {json.dumps({'text': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/subject/{book_id}/chapter/{chapter_id}/practice/chat-stream")
@limiter.limit("10/minute")
async def api_practice_chat_stream(
    request: Request,
    book_id: str,
    chapter_id: str,
    question_id: int,
    user_query: str,
    chat_history: str = "[]",
    student: dict = Depends(get_current_student),
):
    user_query = user_query[:300]
    if contains_prompt_injection(user_query):
        raise HTTPException(status_code=400, detail="Prompt-injection style instructions are not allowed.")

    question_text = await get_question_text(question_id)
    if not question_text:
        question_text = ""
    context = await get_relevant_context(book_id, chapter_id, question_text)

    try:
        history_list = json.loads(chat_history)
        if not isinstance(history_list, list):
            history_list = []
    except (json.JSONDecodeError, ValueError):
        history_list = []

    history_list = sanitize_history(history_list)


    async def event_generator():
        async for token in get_practice_chat_stream(question_text, context, history_list, user_query):
            yield f"data: {json.dumps({'text': token})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/practice/grade-handwritten")
@limiter.limit("5/minute")
async def api_grade_handwritten(
    request: Request,
    file: UploadFile = File(...),
    question_id: int = Form(...),
    book_id: str = Form(default=""),
    chapter_id: str = Form(default=""),
    student: dict = Depends(get_current_student),
):
    """
    Grade a handwritten answer from a photo.
    Transcribes the image via OpenRouter vision, then grades with AI.
    """
    from backend.app.api.pyp import _extract_handwritten_text

    image_data = await file.read()
    if len(image_data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 5 MB.")

    # Validate by magic bytes — never trust the Content-Type header alone.
    _IMAGE_MAGIC: list[tuple[bytes, str]] = [
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"RIFF", "image/webp"),      # RIFF....WEBP
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
    ]
    is_valid_image = any(image_data[:8].startswith(magic) for magic, _ in _IMAGE_MAGIC)
    # Special-case WebP: first 4 bytes are RIFF, bytes 8-12 must be WEBP.
    if image_data[:4] == b"RIFF" and image_data[8:12] != b"WEBP":
        is_valid_image = False
    if not is_valid_image:
        raise HTTPException(status_code=400, detail="File must be a valid image (JPEG, PNG, or WebP).")

    # Detect MIME type from magic bytes (never trust Content-Type header alone).
    content_type = "image/jpeg"  # safe default
    for magic, mime in _IMAGE_MAGIC:
        if image_data[:len(magic)].startswith(magic):
            content_type = mime
            break

    question = await fetch_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    image_b64 = base64.b64encode(image_data).decode()
    extracted_text = await _extract_handwritten_text(image_b64, content_type, question["text"])

    if not extracted_text:
        raise HTTPException(
            status_code=422,
            detail="Could not read handwritten text. Please ensure the image is clear and well-lit.",
        )

    context = await get_relevant_context(book_id or "", chapter_id or "", question["text"])
    grade = await grade_subjective_answer(question["text"], context or "", extracted_text)

    score = grade.get("score", 5)
    is_correct = score >= 6

    new_tier, consecutive_correct, promoted = await process_practice_answer(
        student["id"], book_id or "", chapter_id or "", is_correct
    )
    mastery = await get_student_mastery(student["id"], book_id or "", chapter_id or "")

    return {
        "extracted_text": extracted_text,
        "score": score,
        "feedback": grade.get("feedback", "Answer evaluated."),
        "is_correct": is_correct,
        "promoted": promoted,
        "new_tier": new_tier,
        "consecutive_correct": consecutive_correct,
        "mastery": mastery,
    }


# ===========================================================================
# BOARD EXAM
# ===========================================================================

