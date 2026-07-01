"""
Badge catalog and award logic for the HBSE Adaptive Learning Platform.
"""
import json
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Badge Catalog ─────────────────────────────────────────────────────────────
BADGE_CATALOG: Dict[str, Dict[str, str]] = {
    # Streak badges
    "streak_3":     {"label": "3-Day Streak",     "icon": "", "tier": "bronze", "desc": "Learn 3 days in a row"},
    "streak_7":     {"label": "7-Day Streak",     "icon": "", "tier": "silver", "desc": "Learn 7 days in a row"},
    "streak_30":    {"label": "Month Strong",     "icon": "", "tier": "gold",   "desc": "Learn 30 days in a row"},
    # Exam badges
    "perfect_exam": {"label": "Perfect Score",    "icon": "", "tier": "gold",   "desc": "Score 100% on a board exam"},
    "first_pass":   {"label": "First Pass",       "icon": "", "tier": "bronze", "desc": "Pass a board exam on the first attempt"},
    # Subject mastery
    "math_master":  {"label": "Math Master",      "icon": "", "tier": "gold",   "desc": "Master all Mathematics chapters"},
    "sci_master":   {"label": "Science Master",   "icon": "", "tier": "gold",   "desc": "Master all Science chapters"},
    "eng_master":   {"label": "English Master",   "icon": "", "tier": "gold",   "desc": "Master all English chapters"},
    "hin_master":   {"label": "Hindi Master",     "icon": "", "tier": "gold",   "desc": "Master all Hindi chapters"},
    # Legacy subject badges (kept for backward compatibility)
    "math_magician":    {"label": "Math Magician",    "icon": "", "tier": "silver", "desc": "Complete Mathematics practice"},
    "science_scholar":  {"label": "Science Scholar",  "icon": "", "tier": "silver", "desc": "Complete Science practice"},
    "english_expert":   {"label": "English Expert",   "icon": "", "tier": "silver", "desc": "Complete English practice"},
    "hindi_master":     {"label": "Hindi Master",     "icon": "", "tier": "silver", "desc": "Complete Hindi practice"},
    # Speed badges
    "speed_reader": {"label": "Speed Reader",     "icon": "", "tier": "silver", "desc": "Complete a chapter reading in under 10 minutes"},
    # Chapter completion badges
    "first_chapter": {"label": "First Chapter",   "icon": "", "tier": "bronze", "desc": "Complete your first chapter (reading + practice + board exam)"},
    "chapters_3":    {"label": "Triple Crown",     "icon": "", "tier": "silver", "desc": "Complete 3 chapters fully"},
    "chapters_10":   {"label": "Ten Strong",       "icon": "", "tier": "gold",   "desc": "Complete 10 chapters fully"},
}


def get_badge_catalog() -> Dict[str, Dict[str, str]]:
    """Return full badge catalog with metadata."""
    return BADGE_CATALOG


def get_badge_info(badge_id: str) -> Optional[Dict[str, str]]:
    """Return metadata for a single badge by ID."""
    return BADGE_CATALOG.get(badge_id)


async def check_and_award_badges(
    student_id: int,
    current_badges: List[str],
    context: Dict[str, Any],
    db_pool,
) -> List[str]:
    """
    Evaluate badge eligibility and award any new badges.

    Args:
        student_id:      The student's DB ID.
        current_badges:  List of badge IDs already held by the student.
        context:         Dict of values to evaluate against:
                           - streak_count (int)
                           - exam_score   (int, 0–100)
                           - exam_passed  (bool)
                           - is_first_exam_attempt (bool)
    Returns:
        List of newly awarded badge IDs.
    """
    new_badges: List[str] = []

    streak = context.get("streak_count", 0)
    exam_score = context.get("exam_score")
    exam_passed = context.get("exam_passed", False)
    is_first_attempt = context.get("is_first_exam_attempt", False)

    if streak >= 3 and "streak_3" not in current_badges:
        new_badges.append("streak_3")
    if streak >= 7 and "streak_7" not in current_badges:
        new_badges.append("streak_7")
    if streak >= 30 and "streak_30" not in current_badges:
        new_badges.append("streak_30")

    if exam_score is not None and exam_score == 100 and "perfect_exam" not in current_badges:
        new_badges.append("perfect_exam")
    if exam_passed and is_first_attempt and "first_pass" not in current_badges:
        new_badges.append("first_pass")

    chapters_complete = context.get("chapters_complete", 0)
    if chapters_complete >= 1 and "first_chapter" not in current_badges:
        new_badges.append("first_chapter")
    if chapters_complete >= 3 and "chapters_3" not in current_badges:
        new_badges.append("chapters_3")
    if chapters_complete >= 10 and "chapters_10" not in current_badges:
        new_badges.append("chapters_10")

    if new_badges:
        all_badges = list(set(current_badges + new_badges))
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE students SET unlocked_badges = $1 WHERE id = $2",
                json.dumps(all_badges),
                student_id,
            )
        logger.info("Awarded badges to student %d: %s", student_id, new_badges)

    return new_badges
