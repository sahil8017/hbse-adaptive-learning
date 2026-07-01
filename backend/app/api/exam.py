import json
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException, Depends

from backend.app.core.config import CHAPTERS_DATA
from backend.app.core.security import (
    get_current_student,
    create_exam_token, decode_exam_token
)
from backend.app.core.database import (
    get_student_mastery, update_student_mastery, get_chapter_reading_percent,
    get_board_exam_questions,
    create_exam_attempt, update_review_timestamp,
    fetch_questions_bulk, check_and_unlock_badge, get_chapter_pyq_mcqs,
    consume_exam_nonce, cleanup_old_nonces
)
from backend.app.core import database as _db
from backend.app.core.limiter import limiter

# Import Pydantic schemas
from backend.app.schemas.exam import ExamSubmit


from backend.app.api.utils import _normalize_question_options
from backend.app.services.badges import check_and_award_badges, get_badge_catalog
from backend.app.services.cache_invalidation import CacheInvalidation

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/badges/catalog")
async def api_get_badge_catalog(student: dict = Depends(get_current_student)):
    catalog = get_badge_catalog()
    return [
        {
            "code": code,
            "name": badge["label"],
            "description": badge["desc"],
            "tier": badge["tier"]
        }
        for code, badge in catalog.items()
    ]


@router.post("/badges/check")
async def api_check_badges(student: dict = Depends(get_current_student)):
    """Check and award any badges the student has earned but not yet received. Returns newly unlocked ones."""
    async with _db.db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT streak_count, unlocked_badges FROM students WHERE id=$1", student["id"]
        )
    if not row:
        return {"new_badges": []}

    streak_count = row["streak_count"] or 0
    current_badges: list = []
    if row["unlocked_badges"]:
        try:
            current_badges = json.loads(row["unlocked_badges"])
        except Exception:
            current_badges = []

    ctx = {"streak_count": streak_count}
    new_badge_codes = await check_and_award_badges(student["id"], current_badges, ctx, _db.db_pool)

    catalog = get_badge_catalog()
    return {
        "new_badges": [
            {
                "code": code,
                "name": catalog[code]["label"],
                "description": catalog[code]["desc"],
                "tier": catalog[code]["tier"],
            }
            for code in new_badge_codes
            if code in catalog
        ]
    }

@router.get("/subject/{book_id}/chapter/{chapter_id}/exam/questions")
@limiter.limit("10/minute")
async def api_exam_questions(request: Request, book_id: str, chapter_id: str, student: dict = Depends(get_current_student)):
    chapters   = CHAPTERS_DATA.get(book_id, [])
    chapter    = next((c for c in chapters if c["id"] == chapter_id), None)
    total_secs = len(chapter["sections"]) if chapter else 0

    read_pct = await get_chapter_reading_percent(student["id"], book_id, chapter_id, total_secs)
    if read_pct < 100:
        raise HTTPException(status_code=403, detail="Board Exam locked. Complete 100% reading first.")

    mastery = await get_student_mastery(student["id"], book_id, chapter_id)
    if mastery["locked_until"]:
        locked_time = mastery["locked_until"]
        if datetime.now(timezone.utc) < locked_time:
            return {
                "cooldown":        True,
                "locked_until_ms": int(locked_time.timestamp() * 1000),
            }

    if book_id.lower() == "mathematics":
        questions = await get_chapter_pyq_mcqs(book_id, chapter_id)
        if not questions or len(questions) < 5:
            raise HTTPException(
                status_code=503,
                detail="Exam question bank is still being prepared for this chapter. Please try again later."
            )
    else:
        questions = await get_board_exam_questions(book_id, chapter_id, limit=10)

    normalized_questions = []
    for q in questions:
        normalized = dict(q)
        normalized["options"] = _normalize_question_options(normalized.get("options"))
        if not normalized.get("id"):
            logger.warning("Skipping exam question without id for %s/%s: %r", book_id, chapter_id, normalized)
            continue
        if not normalized["options"]:
            logger.warning(
                "Skipping exam question with invalid options for %s/%s: id=%s",
                book_id,
                chapter_id,
                normalized.get("id"),
            )
            continue
        normalized_questions.append(normalized)

    if not normalized_questions:
        raise HTTPException(status_code=503, detail="No exam questions are available for this chapter yet.")

    answer_key  = {str(q["id"]): q.get("correct_answer", 0) for q in normalized_questions}
    subtopic_key = {str(q["id"]): q.get("subtopic", "General") for q in normalized_questions}
    
    exam_token = create_exam_token(student["id"], answer_key, subtopic_key)

    for q in normalized_questions:
        q.pop("correct_answer", None)

    return {"questions": normalized_questions, "cooldown": False, "exam_token": exam_token}


@router.post("/subject/{book_id}/chapter/{chapter_id}/exam/submit")
@limiter.limit("5/minute")
async def api_exam_submit(request: Request, book_id: str, chapter_id: str, body: ExamSubmit, student: dict = Depends(get_current_student)):
    payload = decode_exam_token(body.exam_token, student["id"])
    exam_answers = payload.get("answers", {})
    exam_subtopics = payload.get("subtopics", {})

    # Replay guard: the one-time nonce embedded in the exam token is mandatory.
    # A token without one cannot be protected against replay, so reject it outright.
    nonce = payload.get("nonce")
    if not nonce:
        raise HTTPException(
            status_code=403,
            detail="Exam token is missing replay protection (nonce). Re-fetch the exam.",
        )
    await consume_exam_nonce(nonce)       # raises 409 if already used
    # Nonce cleanup is housekeeping — fire-and-forget so it doesn't add latency
    # to the exam submission response. The scheduler handles periodic cleanup too.
    import asyncio as _asyncio
    _asyncio.create_task(cleanup_old_nonces())
    question_ids = [int(q_id) for q_id in exam_answers.keys()]
    questions_by_id = await fetch_questions_bulk(question_ids)

    total_qs          = len(exam_answers)
    correct_count     = 0
    incorrect_subtopics = set()

    total_marks = 0
    scored_marks = 0

    for q_id, correct_ans in exam_answers.items():
        q_id_int = int(q_id)
        q = questions_by_id.get(q_id_int)
        q_marks = q.get("marks", 1) if q else 1
        total_marks += q_marks
        
        raw = body.answers.get(q_id)
        try:
            if raw is not None and int(raw) == correct_ans:
                correct_count += 1
                scored_marks += q_marks
            else:
                incorrect_subtopics.add(exam_subtopics.get(q_id, "General"))
        except (TypeError, ValueError):
            incorrect_subtopics.add(exam_subtopics.get(q_id, "General"))

    if book_id.lower() == "mathematics":
        score_percent = int((scored_marks / total_marks) * 100) if total_marks else 0
    else:
        score_percent = int((correct_count / total_qs) * 100) if total_qs else 0
        
    passed = score_percent >= 80
    from backend.app.core.database import get_latest_exam_attempt
    prev_attempt = await get_latest_exam_attempt(student["id"], book_id, chapter_id)
    is_first_attempt = prev_attempt is None

    await create_exam_attempt(
        student["id"], book_id, chapter_id,
        score_percent, int(passed), list(incorrect_subtopics),
    )

    await update_review_timestamp(student["id"], book_id, chapter_id)

    unlocked_badge = None
    new_badges: list = []
    if passed:
        await update_student_mastery(
            student["id"], book_id, chapter_id,
            mastery_percent=score_percent, status="mastered", locked_until=None,
        )
        await CacheInvalidation.on_exam_pass(student["id"], book_id, chapter_id)
        legacy_badge = await check_and_unlock_badge(student["id"], book_id)
        if legacy_badge:
            unlocked_badge = legacy_badge

        # Fetch streak count from student record
        async with _db.db_pool.acquire() as _conn:
            streak_row = await _conn.fetchrow("SELECT streak_count, unlocked_badges FROM students WHERE id=$1", student["id"])
            streak_count = streak_row["streak_count"] if streak_row else 0
            current_badges = []
            if streak_row and streak_row["unlocked_badges"]:
                try:
                    current_badges = json.loads(streak_row["unlocked_badges"])
                except Exception:
                    current_badges = []

        ctx = {
            "streak_count": streak_count,
            "exam_score": score_percent,
            "exam_passed": passed,
            "is_first_exam_attempt": is_first_attempt,
        }
        new_badges = await check_and_award_badges(student["id"], current_badges, ctx, _db.db_pool)
        if new_badges:
            unlocked_badge = new_badges[0]  # keep backward compat single badge field
    else:
        mastery      = await get_student_mastery(student["id"], book_id, chapter_id)
        scaled_tier  = max(1, mastery["current_tier"] - 1)
        cooldown_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        await update_student_mastery(
            student["id"], book_id, chapter_id,
            current_tier=scaled_tier, locked_until=cooldown_time, status="in_progress",
        )
        await CacheInvalidation.on_exam_pass(student["id"], book_id, chapter_id)

    ai_feedback = ""
    if book_id.lower() == "mathematics":
        incorrect_feedback_parts = []
        for q_id, correct_ans in exam_answers.items():
            user_ans = body.answers.get(q_id)
            is_correct = False
            try:
                is_correct = user_ans is not None and int(user_ans) == correct_ans
            except (TypeError, ValueError):
                is_correct = False

            if not is_correct:
                q = questions_by_id.get(int(q_id))
                if not q:
                    continue
                question_options = _normalize_question_options(q.get("options"))
                correct_opt_text = question_options[correct_ans] if correct_ans < len(question_options) else "Review the correct option"
                clean_question_text = str(q.get("text", "")).replace('\\"', '"').strip()
                clean_option_text = str(correct_opt_text).replace('\\"', '"').strip()
                incorrect_feedback_parts.append(
                    f"- Revise {q.get('subtopic', 'this concept')}: for \"{clean_question_text}\" the correct option is \"{clean_option_text}\"."
                )

        if incorrect_feedback_parts:
            ai_feedback = (
                f"You scored {scored_marks} out of {total_marks}. "
                "Focus on these areas before your next attempt:\n" +
                "\n".join(incorrect_feedback_parts[:5]) +
                "\nUse the tutor chat on the chapter page if you want a full step-by-step solution for any of these questions."
            )
        else:
            ai_feedback = "Congratulations! You got every question correct! You have mastered this chapter's board questions."

    return {
        "score_percent":        score_percent,
        "passed":               passed,
        "incorrect_subtopics":  list(incorrect_subtopics),
        "unlocked_badge":       unlocked_badge,
        "new_badges":           new_badges,
        "total_marks":          total_marks,
        "scored_marks":         scored_marks,
        "ai_feedback":          ai_feedback
    }

# ===========================================================================
# PROGRESS BACKUP / RESTORE
# ===========================================================================

