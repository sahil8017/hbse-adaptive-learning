import json
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.core.config import CHAPTERS_DATA
from backend.app.core.limiter import limiter
from backend.app.core.database import (
    apply_mastery_decay,
    create_or_update_student_from_firebase,
    get_diagnostic_questions,
    get_diagnostic_questions_meta,
    get_student_mastery,
    update_student_mastery,
)
from backend.app.core.security import get_current_student, verify_firebase_id_token
from backend.app.schemas.auth import AuthSessionResponse, FirebaseSessionRequest, StudentOut
from backend.app.services.adaptive import determine_subject_tier
from backend.app.services.subject_catalog import get_subject_catalog, get_subject_meta

logger = logging.getLogger(__name__)

router = APIRouter()


def _student_out(student: dict) -> StudentOut:
    try:
        focus_areas = json.loads(student["focus_areas"]) if student.get("focus_areas") else []
    except Exception:
        focus_areas = []
    try:
        unlocked_badges = json.loads(student["unlocked_badges"]) if student.get("unlocked_badges") else []
    except Exception:
        unlocked_badges = []

    return StudentOut(
        id=student["id"],
        username=student["username"],
        email=student.get("email"),
        display_name=student.get("display_name"),
        role=student.get("role") or "student",
        class_grade=student.get("class_grade") or "Class 9",
        board=student.get("board") or "HBSE",
        school=student.get("school"),
        auth_provider=student.get("auth_provider") or "firebase",
        streak_count=student.get("streak_count", 0),
        last_active_date=student.get("last_active_date"),
        focus_areas=focus_areas,
        unlocked_badges=unlocked_badges,
    )


@router.post("/login", response_model=AuthSessionResponse)
@limiter.limit("10/minute")
async def api_login(request: Request, body: FirebaseSessionRequest):
    if getattr(body, "_hp", ""):
        raise HTTPException(status_code=422, detail="Invalid request.")

    identity = await verify_firebase_id_token(body.id_token)
    student, is_new = await create_or_update_student_from_firebase(
        firebase_uid=identity["firebase_uid"],
        email=identity["email"],
        display_name=(body.display_name or identity.get("name") or "").strip() or None,
        role=body.role,
        class_grade=body.class_grade,
        board=body.board,
        school=body.school,
    )

    await apply_mastery_decay(student["id"])

    needs_diagnostic = True
    if not is_new:
        # Resolve the first Mathematics chapter dynamically so a curriculum rename
        # doesn't silently send every returning student back to onboarding.
        math_chapters = CHAPTERS_DATA.get("Mathematics", [])
        first_ch_id = math_chapters[0]["id"] if math_chapters else "math_ch1"
        mastery = await get_student_mastery(student["id"], "Mathematics", first_ch_id)
        needs_diagnostic = mastery["status"] == "locked"

    return AuthSessionResponse(
        student=_student_out(student),
        is_new=is_new,
        needs_diagnostic=needs_diagnostic,
        auth_provider="firebase",
    )


@router.post("/refresh")
async def api_refresh():
    return {
        "status": "managed_by_firebase",
        "message": "Firebase client SDK refreshes ID tokens automatically.",
    }


@router.post("/logout")
async def api_logout():
    return {"ok": True}


@router.get("/me")
async def api_me(student: dict = Depends(get_current_student)):
    return {"student": _student_out(student)}


@router.get("/diagnostic/questions")
async def api_diagnostic_questions(student: dict = Depends(get_current_student)):
    import random

    subjects = list(get_subject_catalog().keys())
    questions: list = []

    for subject in subjects:
        rows = await get_diagnostic_questions(subject)
        for r in rows:
            q = dict(r)
            q["options"] = json.loads(q["options"])
            q.pop("correct_answer", None)
            questions.append(q)

    random.shuffle(questions)
    return questions


@router.post("/diagnostic/submit")
@limiter.limit("5/minute")
async def api_diagnostic_submit(request: Request, body: Dict[str, Any], student: dict = Depends(get_current_student)):
    answers: dict = body.get("answers", {})

    rows = await get_diagnostic_questions_meta()
    diag_qs = {str(r["id"]): (r["book_id"], r["correct_answer"]) for r in rows}

    subject_scores: dict = {
        book_id: {"correct": 0, "total": 0}
        for book_id in get_subject_catalog().keys()
    }

    for q_id, (book_id, correct_ans) in diag_qs.items():
        raw = answers.get(q_id)
        if book_id not in subject_scores:
            continue
        subject_scores[book_id]["total"] += 1
        try:
            if raw is not None and int(raw) == correct_ans:
                subject_scores[book_id]["correct"] += 1
        except (TypeError, ValueError):
            pass

    for book_id in CHAPTERS_DATA:
        stats = subject_scores.get(book_id, {"correct": 0, "total": 0})
        tier = determine_subject_tier(stats["correct"], stats["total"])
        subject_meta = get_subject_meta(book_id) or {}
        ch_id = subject_meta.get("first_chapter_id") or (
            CHAPTERS_DATA.get(book_id, [{}])[0].get("id") if CHAPTERS_DATA.get(book_id) else None
        )
        if not ch_id:
            continue
        await update_student_mastery(
            student["id"],
            book_id,
            ch_id,
            current_tier=tier,
            consecutive_correct=0,
            mastery_percent=0,
            status="in_progress",
        )

    return {"ok": True, "redirect": "/dashboard"}
