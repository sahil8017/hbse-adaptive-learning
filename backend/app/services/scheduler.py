import os
import uuid
import asyncio
import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.app.core import database as _db
from backend.app.core.cache import cache_manager

logger = logging.getLogger(__name__)

class DistributedScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.instance_id = os.getenv("INSTANCE_ID", str(uuid.uuid4())[:8])
        self.lock_task: Optional[asyncio.Task] = None
        self._running = False
        
    def scheduled_job(self, *args, **kwargs):
        return self.scheduler.scheduled_job(*args, **kwargs)
        
    async def start(self):
        if self._running:
            return
            
        acquired = False
        if cache_manager and cache_manager.redis:
            try:
                res = await cache_manager.redis.set(
                    "scheduler:lock",
                    self.instance_id,
                    nx=True,
                    ex=300
                )
                acquired = bool(res)
            except Exception as e:
                logger.error(
                    "Error checking Redis scheduler lock: %s. Scheduler will remain inactive to avoid duplicate jobs.",
                    e,
                )
                acquired = False
        else:
            logger.warning(
                "Redis cache manager not available. Scheduler will remain inactive to avoid duplicate jobs."
            )
            acquired = False
            
        if acquired:
            logger.info(f"Scheduler lock acquired by instance {self.instance_id}. Starting job scheduler...")
            self.scheduler.start()
            self._running = True
            if cache_manager and cache_manager.redis:
                self.lock_task = asyncio.create_task(self._renew_lock())
        else:
            logger.info(f"Instance {self.instance_id} failed to acquire scheduler lock. Scheduler inactive on this instance.")
            
    async def _renew_lock(self):
        while self._running:
            try:
                await asyncio.sleep(120)
                if cache_manager and cache_manager.redis:
                    val = await cache_manager.redis.get("scheduler:lock")
                    if val == self.instance_id:
                        await cache_manager.redis.set("scheduler:lock", self.instance_id, ex=300)
                    else:
                        logger.warning(f"Instance {self.instance_id} lost the scheduler lock to {val}. Stopping scheduler.")
                        self.shutdown()
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error renewing scheduler lock: {e}")
                await asyncio.sleep(10)
                
    def shutdown(self):
        if self._running:
            try:
                self.scheduler.shutdown()
                logger.info("Scheduler shut down successfully.")
            except Exception as e:
                logger.error(f"Error during scheduler shutdown: {e}")
            self._running = False
            
        if self.lock_task:
            self.lock_task.cancel()
            self.lock_task = None

scheduler = DistributedScheduler()

@scheduler.scheduled_job("cron", hour=3, minute=0)  # 3 AM daily
async def nightly_nonce_cleanup():
    """Remove expired exam nonces to keep the used_exam_nonces table small."""
    logger.info("Starting nightly exam nonce cleanup...")
    if not _db.db_pool:
        logger.error("Database pool not initialized. Nonce cleanup skipped.")
        return
    try:
        await _db.cleanup_old_nonces()
        logger.info("Exam nonce cleanup completed.")
    except Exception as e:
        logger.exception("Error during nonce cleanup: %s", e)


@scheduler.scheduled_job("cron", hour=2, minute=0)  # 2 AM daily
async def nightly_mastery_decay():
    logger.info("Starting nightly mastery decay job...")
    if not _db.db_pool:
        logger.error("Database connection pool is not initialized. Nightly decay skipped.")
        return

    try:
        async with _db.db_pool.acquire() as conn:
            async with conn.transaction():
                # Apply 5% decay per overdue day, capped at 15%, respecting tier floors
                result = await conn.execute("""
                    UPDATE student_mastery
                    SET mastery_percent = GREATEST(
                        CASE current_tier
                            WHEN 3 THEN 60
                            WHEN 2 THEN 30
                            ELSE 0
                        END,
                        mastery_percent - LEAST(
                            15,
                            5 * GREATEST(0,
                                EXTRACT(DAY FROM (now() - review_due_at))::int
                            )
                        )
                    )
                    WHERE review_due_at < now()
                      AND status = 'in_progress'
                """)
                logger.info(f"Nightly mastery decay completed: {result}")
    except Exception as e:
        logger.exception("Error executing nightly mastery decay: %s", e)
