# backend/app/services/cache_invalidation.py
from backend.app.core.cache import cache_manager

class CacheInvalidation:
    @staticmethod
    async def on_practice_submit(student_id: int, chapter_id: str, book_id: str):
        # Invalidate mastery snapshots for this student
        await cache_manager.delete_pattern(f"mastery:snapshot:get_student_mastery:({student_id},*")

    @staticmethod
    async def on_exam_pass(student_id: int, book_id: str, chapter_id: str):
        # Invalidate student mastery snapshots and dashboard views
        await cache_manager.delete_pattern(f"mastery:snapshot:get_student_mastery:({student_id},*")

    @staticmethod
    async def on_chat_message(student_id: int):
        # Placeholder for chat history invalidations if cached in Redis
        pass

    @staticmethod
    async def on_question_added(book_id: str, chapter_id: str, tier: int):
        """Invalidate adaptive question pool when new questions are ingested."""
        await cache_manager.delete_pattern(f"adaptive_q_pool:_get_adaptive_question_pool:('{book_id}', '{chapter_id}', {tier})*")

