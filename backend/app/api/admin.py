"""
Admin router — question bank CRUD, anomaly log, mastery distribution.
Protected by require_admin dependency (checks ADMIN_SECRET header or is_admin column).
"""
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel

from backend.app.core import database as _db
from backend.app.core.database import add_question
from backend.app.core.security import get_current_student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin")


# ── Auth guard ────────────────────────────────────────────────────────────────

async def require_admin(
    student: dict = Depends(get_current_student),
    x_admin_secret: Optional[str] = Header(default=None),
) -> dict:
    """
    Require the calling student to have is_admin = true in the database.

    The X-Admin-Secret header is NO LONGER a bypass: possession of the secret
    alone never grants admin access. It is retained only so admin tooling can
    tag privileged requests for audit logging.
    """
    async with _db.db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_admin FROM students WHERE id = $1", student["id"])
        is_admin = row["is_admin"] if row else False
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    if x_admin_secret:
        logger.info("Admin action by student id=%s with X-Admin-Secret header present", student["id"])
    return student


# ── Schemas ───────────────────────────────────────────────────────────────────

class QuestionCreate(BaseModel):
    book_id: str
    chapter_id: str
    tier: int
    text: str
    options: List[str]
    correct_answer: int
    subtopic: str
    is_pyq: bool = False
    pyq_year: Optional[int] = None
    question_type: str = "mcq"
    marks: int = 1

class QuestionUpdate(BaseModel):
    text: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[int] = None
    subtopic: Optional[str] = None
    tier: Optional[int] = None
    marks: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/questions")
async def admin_list_questions(
    book_id: str,
    chapter_id: str,
    tier: Optional[int] = None,
    limit: int = 50,
    _admin: dict = Depends(require_admin),
):
    """List questions in a chapter. Optionally filter by tier."""
    limit = min(max(limit, 1), 500)  # hard server-side cap
    async with _db.db_pool.acquire() as conn:
        if tier:
            rows = await conn.fetch(
                "SELECT * FROM questions WHERE book_id=$1 AND chapter_id=$2 AND tier=$3 ORDER BY id LIMIT $4",
                book_id, chapter_id, tier, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM questions WHERE book_id=$1 AND chapter_id=$2 ORDER BY tier, id LIMIT $3",
                book_id, chapter_id, limit
            )
    result = []
    for r in rows:
        q = dict(r)
        if isinstance(q.get("options"), str):
            try:
                q["options"] = json.loads(q["options"])
            except Exception:
                q["options"] = []
        result.append(q)
    return result


@router.post("/questions", status_code=201)
async def admin_create_question(body: QuestionCreate, _admin: dict = Depends(require_admin)):
    """Add a new question to the question bank."""
    await add_question(
        book_id=body.book_id,
        chapter_id=body.chapter_id,
        tier=body.tier,
        text=body.text,
        options=body.options,
        correct_answer=body.correct_answer,
        subtopic=body.subtopic,
        is_pyq=int(body.is_pyq),
        pyq_year=body.pyq_year,
        question_type=body.question_type,
        marks=body.marks,
    )
    return {"ok": True, "message": "Question created successfully."}


@router.put("/questions/{q_id}")
async def admin_update_question(q_id: int, body: QuestionUpdate, _admin: dict = Depends(require_admin)):
    """Update an existing question by ID."""
    updates: Dict[str, Any] = {}
    if body.text is not None:
        updates["text"] = body.text
    if body.options is not None:
        updates["options"] = json.dumps(body.options)
    if body.correct_answer is not None:
        updates["correct_answer"] = body.correct_answer
    if body.subtopic is not None:
        updates["subtopic"] = body.subtopic
    if body.tier is not None:
        updates["tier"] = body.tier
    if body.marks is not None:
        updates["marks"] = body.marks

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")

    set_clauses = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates.keys()))
    values = [q_id] + list(updates.values())

    async with _db.db_pool.acquire() as conn:
        result = await conn.execute(
            f"UPDATE questions SET {set_clauses} WHERE id = $1",
            *values,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Question not found.")
    return {"ok": True, "message": "Question updated."}


@router.delete("/questions/{q_id}", status_code=204)
async def admin_delete_question(q_id: int, _admin: dict = Depends(require_admin)):
    """Delete a question from the question bank."""
    async with _db.db_pool.acquire() as conn:
        result = await conn.execute("DELETE FROM questions WHERE id = $1", q_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Question not found.")


@router.get("/anomalies")
async def admin_list_anomalies(limit: int = 50, _admin: dict = Depends(require_admin)):
    """Return the most recent anomaly log entries."""
    limit = min(max(limit, 1), 200)  # hard server-side cap
    async with _db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id, a.anomaly_type, a.book_id, a.chapter_id, a.timestamp,
                   s.username
            FROM anomalies a
            JOIN students s ON s.id = a.student_id
            ORDER BY a.timestamp DESC LIMIT $1
            """,
            limit,
        )
    return [dict(r) for r in rows]


@router.get("/mastery-distribution")
async def admin_mastery_distribution(book_id: str, _admin: dict = Depends(require_admin)):
    """Return mastery percent distribution across students for a subject."""
    async with _db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT chapter_id,
                   COUNT(*) AS student_count,
                   ROUND(AVG(mastery_percent), 1) AS avg_mastery,
                   COUNT(*) FILTER (WHERE status = 'mastered') AS mastered_count,
                   COUNT(*) FILTER (WHERE status = 'in_progress') AS in_progress_count
            FROM student_mastery
            WHERE book_id = $1
            GROUP BY chapter_id
            ORDER BY chapter_id
            """,
            book_id,
        )
    return [dict(r) for r in rows]


@router.post("/ingest-materials")
async def admin_ingest_materials(_admin: dict = Depends(require_admin)):
    """
    Trigger ingestion of all Class 9 source materials (textbooks + PYP papers)
    into pgvector. Runs in a background task; returns immediately.
    """
    import asyncio

    async def _run():
        try:
            # Import here to avoid circular imports at module load time
            import importlib.util
            import os
            scripts_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
            )
            spec = importlib.util.spec_from_file_location(
                "ingest_all_source_materials",
                os.path.join(scripts_dir, "ingest_all_source_materials.py"),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            await mod.main()
            logger.info("Admin-triggered ingestion of all source materials completed.")
        except Exception as exc:
            logger.error("Admin-triggered ingestion failed: %s", exc, exc_info=True)

    asyncio.create_task(_run())
    return {"status": "started", "message": "Ingestion of all Class 9 source materials started in background."}


@router.get("/students")
async def admin_list_students(limit: int = 100, _admin: dict = Depends(require_admin)):
    """Return a list of all students with basic stats."""
    limit = min(max(limit, 1), 200)  # hard server-side cap
    async with _db.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, username, streak_count, last_active_date, created_at
            FROM students
            ORDER BY created_at DESC LIMIT $1
            """,
            limit,
        )
    result = []
    for r in rows:
        row = dict(r)
        if row.get("last_active_date"):
            row["last_active_date"] = row["last_active_date"].isoformat()
        if row.get("created_at"):
            row["created_at"] = row["created_at"].isoformat()
        result.append(row)
    return result
