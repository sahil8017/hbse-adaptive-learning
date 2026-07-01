"""
Previous Year Papers (PYP) quiz API endpoints.
Students browse by subject/year and answer extracted MCQ + open questions.
"""
import base64
import json
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core import database as _db
from backend.app.core.database import fetch_question
from backend.app.core.limiter import limiter
from backend.app.core.prompt_security import contains_prompt_injection
from backend.app.core.security import get_current_student
from backend.app.services.adaptive import grade_subjective_answer
from backend.app.services.rag import get_relevant_context

logger = logging.getLogger(__name__)

router = APIRouter()

PYP_CHAPTER_ID = "pyp"
_VISION_MODEL = "meta-llama/llama-3.2-11b-vision-instruct"
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


# ── Schemas ──────────────────────────────────────────────────────────────────

class PYPSubmitMCQ(BaseModel):
    question_id: int
    user_answer: int


class PYPGradeOpen(BaseModel):
    question_id: int
    user_answer: str
    book_id: str = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _fetch_pyp_years(book_id: str):
    async with _db.db_replica_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                pyq_year,
                COUNT(*) FILTER (WHERE question_type = 'mcq')  AS mcq_count,
                COUNT(*) FILTER (WHERE question_type = 'open') AS open_count
            FROM questions
            WHERE book_id = $1
              AND chapter_id = $2
              AND is_pyq = TRUE
              AND pyq_year IS NOT NULL
            GROUP BY pyq_year
            ORDER BY pyq_year DESC
            """,
            book_id,
            PYP_CHAPTER_ID,
        )
    return [
        {
            "year": r["pyq_year"],
            "mcq_count": r["mcq_count"] or 0,
            "open_count": r["open_count"] or 0,
        }
        for r in rows
    ]


async def _extract_handwritten_text(
    image_b64: str,
    mime: str,
    question_context: str,
) -> str:
    """Call OpenRouter vision model to transcribe a handwritten answer image."""
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "HBSE Adaptive Learning",
    }
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                },
                {
                    "type": "text",
                    "text": (
                        f"The student is answering: {question_context}\n\n"
                        "Carefully transcribe the handwritten answer from this image. "
                        "Output ONLY the transcribed text. "
                        "Preserve any mathematical expressions or formulas exactly as written."
                    ),
                },
            ],
        }
    ]
    payload = {
        "model": _VISION_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 600,
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if r.status_code == 200:
                return (
                    r.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
            logger.error("Vision model error %d: %s", r.status_code, r.text[:200])
    except Exception as exc:
        logger.exception("Error extracting handwritten text: %s", exc)

    return ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/practice/pyp/subjects")
async def list_pyp_subjects(student: dict = Depends(get_current_student)):
    """List subjects that have PYP data in the database."""
    async with _db.db_replica_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT book_id, COUNT(*) AS total
            FROM questions
            WHERE chapter_id = $1 AND is_pyq = TRUE
            GROUP BY book_id
            ORDER BY book_id
            """,
            PYP_CHAPTER_ID,
        )
    return [{"book_id": r["book_id"], "total_questions": r["total"]} for r in rows]


@router.get("/practice/pyp/{book_id}/years")
async def list_pyp_years(book_id: str, student: dict = Depends(get_current_student)):
    """List available PYP years for a subject."""
    years = await _fetch_pyp_years(book_id)
    return {"book_id": book_id, "years": years}


@router.get("/practice/pyp/{book_id}/{year}/questions")
async def get_pyp_questions(
    book_id: str,
    year: int,
    student: dict = Depends(get_current_student),
):
    """Return all questions from a specific PYP year (correct_answer excluded)."""
    async with _db.db_replica_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, text, options, question_type, subtopic, marks
            FROM questions
            WHERE book_id = $1
              AND chapter_id = $2
              AND is_pyq = TRUE
              AND pyq_year = $3
            ORDER BY question_type DESC, id ASC
            """,
            book_id,
            PYP_CHAPTER_ID,
            year,
        )

    questions = []
    for r in rows:
        q = dict(r)
        opts = q.get("options")
        if isinstance(opts, str):
            try:
                q["options"] = json.loads(opts)
            except Exception:
                q["options"] = []
        questions.append(q)

    return {"year": year, "book_id": book_id, "questions": questions}


@router.post("/practice/pyp/{book_id}/{year}/submit")
async def submit_pyp_mcq(
    book_id: str,
    year: int,
    body: PYPSubmitMCQ,
    student: dict = Depends(get_current_student),
):
    """Grade a PYP MCQ submission. Returns instant feedback with correct_answer."""
    question = await fetch_question(body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    correct_answer = question.get("correct_answer", 0)
    is_correct = body.user_answer == correct_answer

    opts = question.get("options") or []
    if isinstance(opts, str):
        try:
            opts = json.loads(opts)
        except Exception:
            opts = []

    return {
        "is_correct": is_correct,
        "correct_answer": correct_answer,
        "correct_option_text": opts[correct_answer] if 0 <= correct_answer < len(opts) else None,
        "selected_option_text": opts[body.user_answer] if 0 <= body.user_answer < len(opts) else None,
    }


@router.post("/practice/pyp/grade-open")
async def grade_pyp_open(
    body: PYPGradeOpen,
    student: dict = Depends(get_current_student),
):
    """Grade a typed open-ended answer for a PYP question."""
    if contains_prompt_injection(body.user_answer):
        raise HTTPException(status_code=400, detail="Prompt-injection style instructions are not allowed.")

    if not body.user_answer.strip():
        raise HTTPException(status_code=400, detail="user_answer cannot be empty.")

    question = await fetch_question(body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    context = await get_relevant_context(body.book_id, PYP_CHAPTER_ID, question["text"])
    grade = await grade_subjective_answer(
        question["text"], context or "", body.user_answer.strip()
    )

    return {
        "score": grade.get("score", 5),
        "feedback": grade.get("feedback", "Answer evaluated."),
        "is_correct": grade.get("score", 5) >= 6,
    }


@router.post("/practice/pyp/grade-handwritten")
@limiter.limit("5/minute")
async def grade_pyp_handwritten(
    request: Request,
    file: UploadFile = File(...),
    question_id: int = Form(...),
    book_id: str = Form(default=""),
    student: dict = Depends(get_current_student),
):
    """
    Grade a handwritten answer photo.
    - Accepts JPEG/PNG/WEBP image upload (max 5 MB)
    - Transcribes handwriting via OpenRouter vision model
    - Grades the transcription with the subjective grader
    """
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="AI grading service is not configured.")

    image_data = await file.read()
    if len(image_data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 5 MB.")

    # Validate by magic bytes — never trust the Content-Type header alone.
    _IMAGE_MAGIC = [
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"RIFF", "image/webp"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
    ]
    is_valid_image = any(image_data[:8].startswith(magic) for magic, _ in _IMAGE_MAGIC)
    if image_data[:4] == b"RIFF" and image_data[8:12] != b"WEBP":
        is_valid_image = False
    if not is_valid_image:
        raise HTTPException(status_code=400, detail="File must be a valid image (JPEG, PNG, or WebP).")

    content_type = file.content_type or "image/jpeg"

    question = await fetch_question(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found.")

    image_b64 = base64.b64encode(image_data).decode()
    extracted_text = await _extract_handwritten_text(
        image_b64, content_type, question["text"]
    )

    if not extracted_text:
        raise HTTPException(
            status_code=422,
            detail="Could not read handwritten text from the image. Please ensure the image is clear and well-lit.",
        )

    context = await get_relevant_context(book_id, PYP_CHAPTER_ID, question["text"])
    grade = await grade_subjective_answer(question["text"], context or "", extracted_text)

    return {
        "extracted_text": extracted_text,
        "score": grade.get("score", 5),
        "feedback": grade.get("feedback", "Answer evaluated."),
        "is_correct": grade.get("score", 5) >= 6,
    }
