import json
import logging
import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import uuid
from backend.app.core.cache_decorators import cached

import asyncpg
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Global connection pool references
db_pool: Optional[asyncpg.Pool] = None
db_replica_pool: Optional[asyncpg.Pool] = None


def get_pool() -> asyncpg.Pool:
    """Return the primary pool; raises clearly if init_db() was never awaited."""
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized. Was init_db() called?")
    return db_pool


def get_replica_pool() -> asyncpg.Pool:
    """Return the replica pool (falls back to primary when no replica is configured)."""
    if db_replica_pool is None:
        raise RuntimeError("Database replica pool is not initialized. Was init_db() called?")
    return db_replica_pool

async def setup_chat_history_partitions(conn):
    # Check if student_chat_history table exists and its relkind
    row = await conn.fetchrow("""
        SELECT relkind FROM pg_class 
        WHERE relname = 'student_chat_history' 
        AND relnamespace = 'public'::regnamespace;
    """)
    
    # Calculate dates for current and next month partitions
    now = datetime.now(timezone.utc)
    
    # Current month
    curr_year = now.year
    curr_month = now.month
    curr_start = f"{curr_year}-{curr_month:02d}-01"
    
    # Next month
    if curr_month == 12:
        next_year = curr_year + 1
        next_month = 1
    else:
        next_year = curr_year
        next_month = curr_month + 1
    next_start = f"{next_year}-{next_month:02d}-01"
    
    # Month after next
    if next_month == 12:
        after_year = next_year + 1
        after_month = 1
    else:
        after_year = next_year
        after_month = next_month + 1
    after_start = f"{after_year}-{after_month:02d}-01"

    curr_partition = f"student_chat_history_y{curr_year}_m{curr_month:02d}"
    next_partition = f"student_chat_history_y{next_year}_m{next_month:02d}"

    relkind: str | None = None
    if row is not None:
        raw = row["relkind"]
        relkind = raw.decode() if isinstance(raw, bytes) else raw

    if row is None:
        logger.info("student_chat_history table does not exist. Creating partitioned table.")
        await conn.execute("""
        CREATE TABLE student_chat_history (
            id SERIAL,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            session_id UUID,
            chapter_id VARCHAR(255),
            sender VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            is_blocked BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
        """)
    elif relkind == 'r':
        logger.info("Migrating student_chat_history to partitioned table.")
        await conn.execute("ALTER TABLE student_chat_history RENAME TO student_chat_history_old;")
        await conn.execute("""
        CREATE TABLE student_chat_history (
            id SERIAL,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            session_id UUID,
            chapter_id VARCHAR(255),
            sender VARCHAR(50) NOT NULL,
            message TEXT NOT NULL,
            is_blocked BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, timestamp)
        ) PARTITION BY RANGE (timestamp);
        """)
        
        # Create partitions before loading data
        await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {curr_partition} 
        PARTITION OF student_chat_history 
        FOR VALUES FROM ('{curr_start}') TO ('{next_start}');
        """)
        await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {next_partition} 
        PARTITION OF student_chat_history 
        FOR VALUES FROM ('{next_start}') TO ('{after_start}');
        """)
        
        # Copy data
        await conn.execute("""
        INSERT INTO student_chat_history (id, student_id, session_id, chapter_id, sender, message, is_blocked, timestamp)
        SELECT id, student_id, session_id, chapter_id, sender, message, is_blocked, timestamp
        FROM student_chat_history_old;
        """)
        
        # Sync identity serial sequence
        await conn.execute("SELECT setval(pg_get_serial_sequence('student_chat_history', 'id'), coalesce(max(id), 1)) FROM student_chat_history;")
        
        # Drop old table
        await conn.execute("DROP TABLE student_chat_history_old CASCADE;")
        logger.info("Migration to partitioned student_chat_history complete.")
        
    # Enforce partitions exist
    await conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {curr_partition} 
    PARTITION OF student_chat_history 
    FOR VALUES FROM ('{curr_start}') TO ('{next_start}');
    """)
    await conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {next_partition} 
    PARTITION OF student_chat_history 
    FOR VALUES FROM ('{next_start}') TO ('{after_start}');
    """)

    # Secure newly created partitions immediately
    for _part in (curr_partition, next_partition):
        try:
            await conn.execute(f"ALTER TABLE public.{_part} ENABLE ROW LEVEL SECURITY;")
            await conn.execute(f"ALTER TABLE public.{_part} FORCE ROW LEVEL SECURITY;")
            await conn.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = 'public'
                          AND tablename  = '{_part}'
                          AND policyname = 'backend_full_access'
                    ) THEN
                        EXECUTE 'CREATE POLICY backend_full_access ON public.{_part}
                                 AS PERMISSIVE FOR ALL
                                 TO postgres
                                 USING (true)
                                 WITH CHECK (true)';
                    END IF;
                END
                $$;
            """)
        except Exception as _rls_err:
            logger.warning("RLS setup skipped for partition %s: %s", _part, _rls_err)

def sanitize_dsn(dsn: str) -> str:
    if not dsn:
        return dsn
    try:
        import urllib.parse
        prefix = ""
        if dsn.startswith("postgresql+asyncpg://"):
            prefix = "postgresql://"
            url_part = dsn[len("postgresql+asyncpg://"):]
        elif dsn.startswith("postgresql://"):
            prefix = "postgresql://"
            url_part = dsn[len("postgresql://"):]
        else:
            return dsn
        
        if "@" in url_part:
            auth, rest = url_part.rsplit("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                unquoted_pass = urllib.parse.unquote(password)
                encoded_pass = urllib.parse.quote(unquoted_pass, safe="")
                return f"{prefix}{user}:{encoded_pass}@{rest}"
    except Exception as exc:
        logger.warning("Failed to sanitize DSN: %s", exc)
    return dsn


async def init_db():
    global db_pool, db_replica_pool
    if not settings.DATABASE_URL:
        logger.error("DATABASE_URL is not set. Database initialization skipped.")
        return
        
    try:
        dsn = sanitize_dsn(settings.DATABASE_URL)
        db_pool = await asyncpg.create_pool(
            dsn,
            min_size=5,
            max_size=50,
            max_queries=50000,
            statement_cache_size=0,
            max_cached_statement_lifetime=300,
            max_cacheable_statement_size=15000,
            command_timeout=30.0
        )
        logger.info("Primary PostgreSQL connection pool established.")
        
        # Check replica database configuration
        replica_dsn = settings.REPLICA_DATABASE_URL or None
        if replica_dsn:
            replica_dsn = sanitize_dsn(replica_dsn)
            db_replica_pool = await asyncpg.create_pool(
                replica_dsn,
                min_size=5,
                max_size=20,
                max_queries=50000,
                statement_cache_size=0,
                max_cached_statement_lifetime=300,
                max_cacheable_statement_size=15000,
                command_timeout=30.0
            )
            logger.info("Replica PostgreSQL connection pool established.")
        else:
            db_replica_pool = db_pool
            logger.info("REPLICA_DATABASE_URL not set; routing read queries to primary pool.")
            
    except Exception as e:
        logger.exception("Failed to create PostgreSQL connection pools: %s", e)
        raise e


    if not settings.INIT_DB_SCHEMA_ON_STARTUP:
        logger.info("Skipping automatic schema initialization (INIT_DB_SCHEMA_ON_STARTUP is disabled).")
        return

    # Create tables and indexes if they don't exist
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            # 1. Students Table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                  id SERIAL PRIMARY KEY,
                  username VARCHAR(255) UNIQUE NOT NULL,
                  firebase_uid VARCHAR(255) UNIQUE,
                  email VARCHAR(320),
                  email_sha256 VARCHAR(64),
                  display_name VARCHAR(255),
                  role VARCHAR(32) DEFAULT 'student',
                  class_grade VARCHAR(32) DEFAULT 'Class 9',
                  board VARCHAR(64) DEFAULT 'HBSE',
                  school VARCHAR(255),
                  auth_provider VARCHAR(32) DEFAULT 'firebase',
                  created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                streak_count INTEGER DEFAULT 0,
                last_active_date TIMESTAMPTZ,
                focus_areas TEXT DEFAULT '[]',
                unlocked_badges TEXT DEFAULT '[]',
                is_admin BOOLEAN DEFAULT FALSE
            );
            """)
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(255);")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS email VARCHAR(320);")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS email_sha256 VARCHAR(64);")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'student';")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS class_grade VARCHAR(32) DEFAULT 'Class 9';")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS board VARCHAR(64) DEFAULT 'HBSE';")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS school VARCHAR(255);")
            await conn.execute("ALTER TABLE students ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(32) DEFAULT 'firebase';")

            # 2. Reading Progress Table
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS reading_progress (
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                section_id VARCHAR(255) NOT NULL,
                completed BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (student_id, book_id, chapter_id, section_id)
            );
            """)

            # 3. Student Mastery Table
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS student_mastery (
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                current_tier INTEGER DEFAULT 1, -- 1=Easy, 2=Medium, 3=Hard
                consecutive_correct INTEGER DEFAULT 0,
                mastery_percent INTEGER DEFAULT 0,
                status VARCHAR(50) DEFAULT 'locked', -- 'locked', 'in_progress', 'mastered'
                locked_until TIMESTAMPTZ,
                last_reviewed_at TIMESTAMPTZ,
                review_due_at TIMESTAMPTZ,
                PRIMARY KEY (student_id, book_id, chapter_id)
            );
            """)

            # 4. Questions Table
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                q_key VARCHAR(255) UNIQUE,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                tier INTEGER NOT NULL, -- 1, 2, or 3
                text TEXT NOT NULL,
                options JSONB NOT NULL, -- JSON array of options
                correct_answer INTEGER NOT NULL, -- Index (0-3)
                subtopic VARCHAR(255) NOT NULL,
                is_pyq BOOLEAN DEFAULT FALSE,
                pyq_year INTEGER,
                question_type VARCHAR(50) DEFAULT 'mcq',
                marks INTEGER DEFAULT 1
            );
            """)
            await conn.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS marks INTEGER DEFAULT 1;")

            # Migrate questions.options from TEXT/VARCHAR to JSONB if needed
            options_col_type = await conn.fetchval("""
                SELECT data_type FROM information_schema.columns 
                WHERE table_name = 'questions' AND column_name = 'options'
            """)
            if options_col_type and options_col_type.lower() in ('text', 'character varying', 'varchar'):
                logger.info("Migrating questions.options from TEXT to JSONB...")
                await conn.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS options_json JSONB;")
                await conn.execute("""
                    UPDATE questions
                    SET options_json = options::jsonb
                    WHERE options_json IS NULL AND options ~ '^\\s*\\[';
                """)
                await conn.execute("""
                    UPDATE questions
                    SET options_json = '[]'::jsonb
                    WHERE options_json IS NULL;
                """)
                await conn.execute("ALTER TABLE questions RENAME COLUMN options TO options_text_backup;")
                await conn.execute("ALTER TABLE questions RENAME COLUMN options_json TO options;")
                await conn.execute("ALTER TABLE questions ALTER COLUMN options SET NOT NULL;")
                logger.info("Successfully migrated questions.options to JSONB.")

            # Drop the obsolete pre-migration backup column. It retained the old
            # NOT NULL constraint with no default, so it blocked every new INSERT
            # (PYP ingestion failed with a not-null violation). Nothing reads it.
            await conn.execute("ALTER TABLE questions DROP COLUMN IF EXISTS options_text_backup;")

            # 5. Exam Attempts Table
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS exam_attempts (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                score INTEGER NOT NULL,
                passed BOOLEAN NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                incorrect_subtopics TEXT -- JSON array of subtopics to revise
            );
            """)

            # 6. Anomalies Table
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                anomaly_type VARCHAR(255) NOT NULL,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 7. Student Chat History Table (Partitioned)
            await setup_chat_history_partitions(conn)

            # Indexes for performance
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_username ON students(username);")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_firebase_uid ON students(firebase_uid) WHERE firebase_uid IS NOT NULL;")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email_sha256 ON students(email_sha256) WHERE email_sha256 IS NOT NULL;")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_student_mastery_lookup ON student_mastery(student_id, book_id, chapter_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_student_mastery_review_due ON student_mastery(student_id, status, review_due_at);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_student_chat_history_lookup ON student_chat_history(student_id, session_id, chapter_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_progress_lookup ON reading_progress(student_id, book_id, chapter_id);")
            await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_q_key ON questions(q_key);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_exam_lookup ON questions(book_id, chapter_id, is_pyq, tier, question_type);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_attempts_lookup ON exam_attempts(student_id, book_id, chapter_id, timestamp DESC);")

            # Phase 3 database optimizations indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_reading_progress_student_date ON reading_progress(student_id, updated_at DESC) WHERE completed = FALSE;")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_exam_attempts_recent ON exam_attempts(student_id, timestamp DESC) WHERE passed = TRUE;")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_student_chat_daily ON student_chat_history(student_id, CAST(timestamp AT TIME ZONE 'UTC' AS date));")

            # 8. Used Exam Nonces Table (replay guard)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS used_exam_nonces (
                nonce TEXT PRIMARY KEY,
                used_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # 10b. Practice Question Attempts (tracks PYQ questions solved per chapter)
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS practice_question_attempts (
                id SERIAL PRIMARY KEY,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                book_id VARCHAR(255) NOT NULL,
                chapter_id VARCHAR(255) NOT NULL,
                question_id INTEGER NOT NULL,
                is_correct BOOLEAN NOT NULL,
                attempted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_practice_attempts_lookup ON practice_question_attempts(student_id, book_id, chapter_id, question_id, is_correct);")

            # 9. pgvector textbook embeddings setup
            if settings.ENABLE_PGVECTOR_SETUP:
                # Install vector into the `extensions` schema (not `public`) to satisfy
                # Supabase's security linter (lint 0014_extension_in_public).
                # The extensions schema is on the search_path by default in Supabase,
                # so the `vector` type remains usable in public tables without changes.
                await conn.execute("CREATE SCHEMA IF NOT EXISTS extensions;")
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;")

                await conn.execute("""
                CREATE TABLE IF NOT EXISTS textbook_embeddings (
                    id BIGSERIAL PRIMARY KEY,
                    book_id VARCHAR(255) NOT NULL,
                    chapter_id VARCHAR(255) NOT NULL,
                    section_id VARCHAR(255),
                    chunk_text TEXT NOT NULL,
                    embedding vector(384),
                    page_num INTEGER,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now(),
                    UNIQUE(book_id, chapter_id, section_id, chunk_text)
                );
                """)
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_textbook_embeddings_cosine ON textbook_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);")
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_textbook_embeddings_book_chapter ON textbook_embeddings(book_id, chapter_id);")
            else:
                logger.info("Skipping pgvector setup (ENABLE_PGVECTOR_SETUP is disabled).")

            # 10. Enable RLS on all public tables
            # The backend connects as the postgres superuser which bypasses RLS.
            # Enabling RLS + a permissive policy for the service role prevents
            # direct PostgREST/anonymous API access (fixes Supabase security linter).
            _rls_tables = [
                "students",
                "reading_progress",
                "student_mastery",
                "exam_attempts",
                "questions",
                "anomalies",
                "used_exam_nonces",
                "textbook_embeddings",
                "student_chat_history",
                "practice_question_attempts",
            ]

            # Also collect any chat-history partition tables that already exist
            partition_names = await conn.fetch("""
                SELECT relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND relname LIKE 'student_chat_history_%'
                  AND relkind = 'r';
            """)
            for row in partition_names:
                _rls_tables.append(row["relname"])

            for tbl in _rls_tables:
                try:
                    await conn.execute(f"ALTER TABLE public.{tbl} ENABLE ROW LEVEL SECURITY;")
                    await conn.execute(f"ALTER TABLE public.{tbl} FORCE ROW LEVEL SECURITY;")
                    # Allow the backend postgres role full access; deny everything else
                    await conn.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_policies
                                WHERE schemaname = 'public'
                                  AND tablename  = '{tbl}'
                                  AND policyname = 'backend_full_access'
                            ) THEN
                                EXECUTE 'CREATE POLICY backend_full_access ON public.{tbl}
                                         AS PERMISSIVE FOR ALL
                                         TO postgres
                                         USING (true)
                                         WITH CHECK (true)';
                            END IF;
                        END
                        $$;
                    """)
                except Exception as rls_err:
                    logger.warning("RLS setup skipped for %s: %s", tbl, rls_err)

            logger.info("RLS enabled on all public tables.")

async def close_db():
    global db_pool, db_replica_pool
    if db_replica_pool and db_replica_pool is not db_pool:
        try:
            await db_replica_pool.close()
            logger.info("Replica PostgreSQL pool closed.")
        except Exception as e:
            logger.error("Error closing replica pool: %s", e)
            
    if db_pool:
        try:
            await db_pool.close()
            logger.info("Primary PostgreSQL pool closed.")
        except Exception as e:
            logger.error("Error closing primary pool: %s", e)

async def add_anomaly(student_id: int, anomaly_type: str, book_id: str, chapter_id: str):
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO anomalies (student_id, anomaly_type, book_id, chapter_id, timestamp)
            VALUES ($1, $2, $3, $4, $5)
        """, student_id, anomaly_type, book_id, chapter_id, datetime.now(timezone.utc))

async def consume_exam_nonce(nonce: str) -> None:
    """Atomically mark an exam nonce as used. Raises 409 if already consumed."""
    from fastapi import HTTPException
    async with get_pool().acquire() as conn:
        inserted = await conn.fetchval(
            """
            INSERT INTO used_exam_nonces (nonce)
            VALUES ($1)
            ON CONFLICT (nonce) DO NOTHING
            RETURNING nonce
            """,
            nonce,
        )
        if not inserted:
            raise HTTPException(status_code=409, detail="Exam token has already been used.")

async def cleanup_old_nonces() -> None:
    """Delete nonces older than 2 hours — run periodically to avoid table bloat."""
    async with get_pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM used_exam_nonces WHERE used_at < now() - INTERVAL '2 hours'"
        )

async def create_student(username: str) -> Optional[Dict[str, Any]]:
    async with get_pool().acquire() as conn:
        try:
            row = await conn.fetchrow("""
                INSERT INTO students (username) VALUES ($1)
                RETURNING id, username
            """, username)
            if row:
                return dict(row)
        except asyncpg.UniqueViolationError:
            return None
    return None

def _normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower()

def _hash_email(email: Optional[str]) -> Optional[str]:
    normalized = _normalize_email(email)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _build_username_base(display_name: Optional[str], email: Optional[str], firebase_uid: str) -> str:
    raw = (display_name or "").strip().lower()
    if not raw and email:
        raw = email.split("@", 1)[0].strip().lower()
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw)
    cleaned = "_".join(filter(None, cleaned.split("_")))
    cleaned = cleaned[:24]
    if len(cleaned) < 3:
        cleaned = f"student_{firebase_uid[:6].lower()}"
    return cleaned

async def _allocate_unique_username(conn, base_username: str, firebase_uid: str) -> str:
    desired = base_username[:30]
    existing = await conn.fetchval("SELECT 1 FROM students WHERE username = $1", desired)
    if not existing:
        return desired

    suffix_seed = hashlib.sha256(firebase_uid.encode("utf-8")).hexdigest()
    for suffix_len in (6, 8, 10):
        suffix = suffix_seed[:suffix_len]
        trimmed = base_username[: max(3, 29 - suffix_len)]
        candidate = f"{trimmed}_{suffix}"[:30]
        existing = await conn.fetchval("SELECT 1 FROM students WHERE username = $1", candidate)
        if not existing:
            return candidate

    return f"stu_{suffix_seed[:26]}"[:30]

async def create_or_update_student_from_firebase(
    firebase_uid: str,
    email: str,
    display_name: Optional[str] = None,
    role: str = "student",
    class_grade: str = "Class 9",
    board: str = "HBSE",
    school: Optional[str] = None,
) -> tuple[Dict[str, Any], bool]:
    normalized_email = _normalize_email(email)
    email_sha256 = _hash_email(normalized_email)
    safe_role = (role or "student").strip().lower()[:32]
    safe_class_grade = (class_grade or "Class 9").strip()[:32]
    safe_board = (board or "HBSE").strip()[:64]
    safe_school = (school or "").strip()[:255] or None

    async with get_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT *
                FROM students
                WHERE firebase_uid = $1
                   OR (email_sha256 = $2 AND $2 IS NOT NULL)
                ORDER BY CASE WHEN firebase_uid = $1 THEN 0 ELSE 1 END
                LIMIT 1
                """,
                firebase_uid,
                email_sha256,
            )

            if row:
                existing = dict(row)
                updated = await conn.fetchrow(
                    """
                      UPDATE students
                      SET firebase_uid = $1,
                          email = $2,
                          email_sha256 = $3,
                          display_name = COALESCE($4, display_name),
                          role = COALESCE($5, role),
                          class_grade = COALESCE($6, class_grade),
                          board = COALESCE($7, board),
                          school = COALESCE($8, school),
                          auth_provider = 'firebase'
                      WHERE id = $9
                      RETURNING *
                      """,
                      firebase_uid,
                      normalized_email,
                      email_sha256,
                      display_name or existing.get("display_name"),
                      safe_role,
                      safe_class_grade,
                      safe_board,
                      safe_school,
                      existing["id"],
                  )
                return dict(updated), False

            username_base = _build_username_base(display_name, normalized_email, firebase_uid)
            username = await _allocate_unique_username(conn, username_base, firebase_uid)
            inserted = await conn.fetchrow(
                  """
                INSERT INTO students (username, firebase_uid, email, email_sha256, display_name, role, class_grade, board, school, auth_provider)
                  VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'firebase')
                  RETURNING *
                  """,
                  username,
                  firebase_uid,
                  normalized_email,
                  email_sha256,
                  display_name,
                  safe_role,
                  safe_class_grade,
                  safe_board,
                  safe_school,
              )
            return dict(inserted), True

async def get_student_by_firebase_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM students WHERE firebase_uid = $1", firebase_uid)
        if row:
            return dict(row)
    return None

async def get_student_by_email_hash(email_sha256: str) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM students WHERE email_sha256 = $1", email_sha256)
        if row:
            return dict(row)
    return None

async def get_student_by_username(username: str) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM students WHERE username = $1", username)
        if row:
            return dict(row)
    return None

async def get_student_by_id(student_id: int) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM students WHERE id = $1", student_id)
        if row:
            return dict(row)
    return None

async def update_reading_progress(student_id: int, book_id: str, chapter_id: str, section_id: str, completed: int):
    comp_bool = bool(completed)
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO reading_progress (student_id, book_id, chapter_id, section_id, completed, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT(student_id, book_id, chapter_id, section_id) DO UPDATE SET
                completed = EXCLUDED.completed,
                updated_at = EXCLUDED.updated_at
        """, student_id, book_id, chapter_id, section_id, comp_bool, datetime.now(timezone.utc))

async def get_chapter_reading_percent(student_id: int, book_id: str, chapter_id: str, total_sections: int) -> int:
    if total_sections == 0:
        return 100
    async with get_replica_pool().acquire() as conn:
        val = await conn.fetchval("""
            SELECT COUNT(*) FROM reading_progress 
            WHERE student_id = $1 AND book_id = $2 AND chapter_id = $3 AND completed = TRUE
        """, student_id, book_id, chapter_id)
        completed_sections = val if val else 0
        return min(100, int((completed_sections / total_sections) * 100))

@cached(ttl=300, key_prefix="mastery:snapshot")
async def get_student_mastery(student_id: int, book_id: str, chapter_id: str) -> Dict[str, Any]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM student_mastery 
            WHERE student_id = $1 AND book_id = $2 AND chapter_id = $3
        """, student_id, book_id, chapter_id)
        if row:
            return dict(row)
            
        # Return default if not exists
        return {
            "student_id": student_id,
            "book_id": book_id,
            "chapter_id": chapter_id,
            "current_tier": 1,
            "consecutive_correct": 0,
            "mastery_percent": 0,
            "status": "locked",
            "locked_until": None,
            "last_reviewed_at": None,
            "review_due_at": None
        }

async def update_student_mastery(student_id: int, book_id: str, chapter_id: str, **kwargs):
    keys = ["student_id", "book_id", "chapter_id"] + list(kwargs.keys())
    values = [student_id, book_id, chapter_id] + list(kwargs.values())
    
    placeholders = [f"${i}" for i in range(1, len(keys) + 1)]
    updates = [f"{k} = EXCLUDED.{k}" for k in kwargs.keys()]
    
    if updates:
        query = f"""
            INSERT INTO student_mastery ({", ".join(keys)})
            VALUES ({", ".join(placeholders)})
            ON CONFLICT (student_id, book_id, chapter_id)
            DO UPDATE SET {", ".join(updates)}
        """
    else:
        query = """
            INSERT INTO student_mastery (student_id, book_id, chapter_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (student_id, book_id, chapter_id)
            DO NOTHING
        """
        
    async with get_pool().acquire() as conn:
        await conn.execute(query, *values)

@cached(ttl=300, key_prefix="adaptive_q_pool")
async def _get_adaptive_question_pool(book_id: str, chapter_id: str, tier: int) -> List[Dict[str, Any]]:
    """Cached pool of adaptive questions for a chapter/tier."""
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM questions
            WHERE book_id = $1 AND chapter_id = $2 AND tier = $3
            LIMIT 50
        """, book_id, chapter_id, tier)
        return [dict(r) for r in rows]

async def get_adaptive_questions(book_id: str, chapter_id: str, tier: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetch cached question pool and randomly sample."""
    pool = await _get_adaptive_question_pool(book_id, chapter_id, tier)
    if not pool:
        return []
    return random.sample(pool, min(limit, len(pool)))

@cached(ttl=600, key_prefix="board_exam_q")
async def get_board_exam_questions(book_id: str, chapter_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM questions
            WHERE book_id = $1 AND chapter_id
= $2 AND (is_pyq = TRUE OR tier = 3)
            ORDER BY RANDOM() LIMIT $3
        """, book_id, chapter_id, limit)
        return [dict(r) for r in rows]

async def add_question(book_id: str, chapter_id: str, tier: int, text: str, options: list, correct_answer: int, subtopic: str, is_pyq: int = 0, pyq_year: Optional[int] = None, q_key: Optional[str] = None, question_type: str = "mcq", marks: int = 1):
    is_pyq_bool = bool(is_pyq)
    if not q_key:
        q_key = f"{book_id}_{chapter_id}_{tier}_{hash(text) & 0xffffffff}"
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO questions (q_key, book_id, chapter_id, tier, text, options, correct_answer, subtopic, is_pyq, pyq_year, question_type, marks)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (q_key) DO UPDATE SET
                book_id = EXCLUDED.book_id,
                chapter_id = EXCLUDED.chapter_id,
                tier = EXCLUDED.tier,
                text = EXCLUDED.text,
                options = EXCLUDED.options,
                correct_answer = EXCLUDED.correct_answer,
                subtopic = EXCLUDED.subtopic,
                is_pyq = EXCLUDED.is_pyq,
                pyq_year = EXCLUDED.pyq_year,
                question_type = EXCLUDED.question_type,
                marks = EXCLUDED.marks
        """, q_key, book_id, chapter_id, tier, text, json.dumps(options), correct_answer, subtopic, is_pyq_bool, pyq_year, question_type, marks)

    from backend.app.services.cache_invalidation import CacheInvalidation
    await CacheInvalidation.on_question_added(book_id, chapter_id, tier)

async def create_exam_attempt(student_id: int, book_id: str, chapter_id: str, score: int, passed: int, incorrect_subtopics: list):
    passed_bool = bool(passed)
    subtopics_json = json.dumps(incorrect_subtopics)
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO exam_attempts (student_id, book_id, chapter_id, score, passed, timestamp, incorrect_subtopics)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, student_id, book_id, chapter_id, score, passed_bool, datetime.now(timezone.utc), subtopics_json)

async def get_latest_exam_attempt(student_id: int, book_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM exam_attempts 
            WHERE student_id = $1 AND book_id = $2 AND chapter_id = $3
            ORDER BY timestamp DESC LIMIT 1
        """, student_id, book_id, chapter_id)
        if row:
            res = dict(row)
            res["incorrect_subtopics"] = json.loads(res["incorrect_subtopics"]) if res["incorrect_subtopics"] else []
            return res
        return None

async def export_student_data(student_id: int) -> dict:
    async with get_replica_pool().acquire() as conn:
        student_row = await conn.fetchrow("""
            SELECT username, email, display_name, streak_count, last_active_date, focus_areas, unlocked_badges 
            FROM students WHERE id = $1
        """, student_id)
        
        if student_row:
            username = student_row["username"]
            email = student_row["email"]
            display_name = student_row["display_name"]
            streak_count = student_row["streak_count"] or 0
            last_active_date = student_row["last_active_date"].isoformat() if student_row["last_active_date"] else None
            focus_areas = student_row["focus_areas"] or "[]"
            unlocked_badges = student_row["unlocked_badges"] or "[]"
        else:
            username, email, display_name, streak_count, last_active_date, focus_areas, unlocked_badges = "unknown", None, None, 0, None, "[]", "[]"
            
        reading_rows = await conn.fetch("""
            SELECT book_id, chapter_id, section_id, completed 
            FROM reading_progress WHERE student_id = $1
        """, student_id)
        reading = [dict(r) for r in reading_rows]
        for r in reading:
            r["completed"] = 1 if r["completed"] else 0
            
        mastery_rows = await conn.fetch("""
            SELECT book_id, chapter_id, current_tier, consecutive_correct, mastery_percent, status, locked_until, last_reviewed_at, review_due_at 
            FROM student_mastery WHERE student_id = $1
        """, student_id)
        mastery = [dict(r) for r in mastery_rows]
        for m in mastery:
            if m["locked_until"]:
                m["locked_until"] = m["locked_until"].isoformat()
            if m["last_reviewed_at"]:
                m["last_reviewed_at"] = m["last_reviewed_at"].isoformat()
            if m["review_due_at"]:
                m["review_due_at"] = m["review_due_at"].isoformat()

        exam_rows = await conn.fetch("""
            SELECT book_id, chapter_id, score, passed, timestamp, incorrect_subtopics 
            FROM exam_attempts WHERE student_id = $1
        """, student_id)
        exams = [dict(r) for r in exam_rows]
        for e in exams:
            e["passed"] = 1 if e["passed"] else 0
            if e["timestamp"]:
                e["timestamp"] = e["timestamp"].isoformat()
            e["incorrect_subtopics"] = json.loads(e["incorrect_subtopics"]) if e["incorrect_subtopics"] else []
            
        return {
            "username": username,
            "email": email,
            "display_name": display_name,
            "streak_count": streak_count,
            "last_active_date": last_active_date,
            "focus_areas": focus_areas,
            "unlocked_badges": unlocked_badges,
            "reading_progress": reading,
            "student_mastery": mastery,
            "exam_attempts": exams
        }

async def import_student_data(username: str, data: dict) -> bool:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            student_row = await conn.fetchrow("SELECT id FROM students WHERE username = $1", username)
            
            # parse times
            def parse_dt(val):
                if not val:
                    return None
                try:
                    return datetime.fromisoformat(val)
                except Exception:
                    return None
            
            last_active = parse_dt(data.get("last_active_date"))
            
            if student_row:
                student_id = student_row["id"]
                await conn.execute("""
                    UPDATE students SET 
                        streak_count = $1, 
                        last_active_date = $2, 
                        email = COALESCE($6, email),
                        display_name = COALESCE($7, display_name),
                        focus_areas = $3, 
                        unlocked_badges = $4 
                    WHERE id = $5
                """, 
                data.get("streak_count", 0),
                last_active,
                data.get("focus_areas", "[]"),
                data.get("unlocked_badges", "[]"),
                student_id,
                _normalize_email(data.get("email")),
                data.get("display_name"))
            else:
                student_id = await conn.fetchval("""
                    INSERT INTO students (username, email, email_sha256, display_name, streak_count, last_active_date, focus_areas, unlocked_badges)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, 
                username,
                _normalize_email(data.get("email")),
                _hash_email(data.get("email")),
                data.get("display_name"),
                data.get("streak_count", 0),
                last_active,
                data.get("focus_areas", "[]"),
                data.get("unlocked_badges", "[]"))
                
            await conn.execute("DELETE FROM reading_progress WHERE student_id = $1", student_id)
            await conn.execute("DELETE FROM student_mastery WHERE student_id = $1", student_id)
            await conn.execute("DELETE FROM exam_attempts WHERE student_id = $1", student_id)
            
            for r in data.get("reading_progress", []):
                await conn.execute("""
                    INSERT INTO reading_progress (student_id, book_id, chapter_id, section_id, completed)
                    VALUES ($1, $2, $3, $4, $5)
                """, student_id, r["book_id"], r["chapter_id"], r["section_id"], bool(r["completed"]))
                
            for m in data.get("student_mastery", []):
                await conn.execute("""
                    INSERT INTO student_mastery (
                        student_id, book_id, chapter_id, current_tier, consecutive_correct, 
                        mastery_percent, status, locked_until, last_reviewed_at, review_due_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """, 
                student_id, 
                m["book_id"], 
                m["chapter_id"], 
                m["current_tier"], 
                m["consecutive_correct"], 
                m["mastery_percent"], 
                m["status"], 
                parse_dt(m.get("locked_until")),
                parse_dt(m.get("last_reviewed_at")),
                parse_dt(m.get("review_due_at")))
                
            for e in data.get("exam_attempts", []):
                await conn.execute("""
                    INSERT INTO exam_attempts (student_id, book_id, chapter_id, score, passed, timestamp, incorrect_subtopics)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 
                student_id, 
                e["book_id"], 
                e["chapter_id"], 
                e["score"], 
                bool(e["passed"]), 
                parse_dt(e.get("timestamp")), 
                json.dumps(e["incorrect_subtopics"]) if isinstance(e["incorrect_subtopics"], list) else e["incorrect_subtopics"])
                
            return True

async def update_review_timestamp(student_id: int, book_id: str, chapter_id: str):
    now = datetime.now(timezone.utc)
    mastery = await get_student_mastery(student_id, book_id, chapter_id)
    tier = mastery.get("current_tier", 1)
    
    from backend.app.services.adaptive import compute_review_interval
    interval_days = compute_review_interval(tier)
    due = now + timedelta(days=interval_days)
    
    await update_student_mastery(
        student_id, book_id, chapter_id,
        last_reviewed_at=now,
        review_due_at=due
    )

async def apply_mastery_decay(student_id: int):
    now = datetime.now(timezone.utc)
    
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            student = await conn.fetchrow("""
                SELECT streak_count, last_active_date FROM students WHERE id = $1
            """, student_id)
            
            if not student:
                return
                
            last_active = student["last_active_date"]
            streak = student["streak_count"] or 0
            
            if last_active:
                if now.date() == last_active.date():
                    return
                
            new_streak = 1
            if last_active:
                time_diff = now - last_active
                if time_diff < timedelta(hours=48):
                    new_streak = streak + 1
                    
            await conn.execute("""
                UPDATE students SET last_active_date = $1, streak_count = $2 WHERE id = $3
            """, now, new_streak, student_id)
            
            records = await conn.fetch("""
                SELECT * FROM student_mastery WHERE student_id = $1 AND status != 'locked'
            """, student_id)
            
            for rec in records:
                due_at = rec.get("review_due_at")
                if not due_at:
                    continue
                    
                if now > due_at:
                    overdue_days = (now - due_at).days + 1
                    decay_amt = min(15, overdue_days * 5)
                    curr_mastery = rec.get("mastery_percent", 0) or 0
                    tier = rec.get("current_tier", 1)
                    
                    if tier == 3:
                        floor = 60
                    elif tier == 2:
                        floor = 30
                    else:
                        floor = 0
                        
                    if curr_mastery >= floor:
                        new_mastery = max(floor, curr_mastery - decay_amt)
                    else:
                        new_mastery = max(0, curr_mastery - decay_amt)
                    
                    if new_mastery != curr_mastery:
                        await conn.execute("""
                            UPDATE student_mastery SET mastery_percent = $1 
                            WHERE student_id = $2 AND book_id = $3 AND chapter_id = $4
                        """, new_mastery, student_id, rec["book_id"], rec["chapter_id"])

async def get_all_student_mastery(student_id: int) -> list:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("SELECT * FROM student_mastery WHERE student_id = $1", student_id)
        return [dict(r) for r in rows]

async def save_chat_message(student_id: int, session_id: Optional[str], chapter_id: Optional[str], sender: str, message: str, is_blocked: bool):
    session_uuid = None
    if session_id:
        try:
            session_uuid = uuid.UUID(session_id) if isinstance(session_id, str) else session_id
        except Exception:
            session_uuid = None
            
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO student_chat_history (student_id, session_id, chapter_id, sender, message, is_blocked, timestamp)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """, student_id, session_uuid, chapter_id, sender, message, is_blocked, datetime.now(timezone.utc))

async def get_chat_history(student_id: int, session_id: Optional[str], chapter_id: Optional[str], limit: int = 20) -> list:
    # Scope to today's messages for this student
    today = datetime.now(timezone.utc).date()
    async with get_replica_pool().acquire() as conn:
        if chapter_id:
            rows = await conn.fetch("""
                SELECT * FROM student_chat_history 
                WHERE student_id = $1 AND CAST(timestamp AT TIME ZONE 'UTC' AS date) = $2 AND chapter_id = $3 
                ORDER BY id DESC LIMIT $4
            """, student_id, today, chapter_id, limit)
        else:
            rows = await conn.fetch("""
                SELECT * FROM student_chat_history 
                WHERE student_id = $1 AND CAST(timestamp AT TIME ZONE 'UTC' AS date) = $2 AND chapter_id IS NULL 
                ORDER BY id DESC LIMIT $3
            """, student_id, today, limit)
            
        return [dict(r) for r in reversed(rows)]

async def clear_chat_history(student_id: int, chapter_id: Optional[str] = None) -> int:
    """Delete chat history for a student. If chapter_id is specified, only delete for that chapter."""
    today = datetime.now(timezone.utc).date()
    async with get_pool().acquire() as conn:
        if chapter_id:
            result = await conn.execute("""
                DELETE FROM student_chat_history
                WHERE student_id = $1 AND CAST(timestamp AT TIME ZONE 'UTC' AS date) = $2 AND chapter_id = $3
            """, student_id, today, chapter_id)
        else:
            result = await conn.execute("""
                DELETE FROM student_chat_history
                WHERE student_id = $1 AND CAST(timestamp AT TIME ZONE 'UTC' AS date) = $2 AND chapter_id IS NULL
            """, student_id, today)
    return result

# ── Upgraded functions to eliminate direct DB access in security & endpoints ──

async def get_diagnostic_questions(book_id: str) -> List[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM questions
            WHERE chapter_id = 'Diagnostic' AND book_id = $1
            ORDER BY RANDOM() LIMIT 3
        """, book_id)
        return [dict(r) for r in rows]

async def get_diagnostic_questions_meta() -> List[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, book_id, correct_answer FROM questions 
            WHERE chapter_id = 'Diagnostic'
        """)
        return [dict(r) for r in rows]

async def get_completed_sections(student_id: int, book_id: str, chapter_id: str) -> List[str]:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT section_id FROM reading_progress 
            WHERE student_id = $1 AND book_id = $2 AND chapter_id = $3 AND completed = TRUE
        """, student_id, book_id, chapter_id)
        return [r["section_id"] for r in rows]

async def add_student_focus_area(student_id: int, concept: str) -> List[str]:
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            student = await conn.fetchrow("SELECT focus_areas FROM students WHERE id = $1", student_id)
            focus_areas = []
            if student and student["focus_areas"]:
                try:
                    focus_areas = json.loads(student["focus_areas"])
                except Exception:
                    focus_areas = []
            if concept not in focus_areas:
                focus_areas.append(concept)
                await conn.execute("""
                    UPDATE students SET focus_areas = $1 WHERE id = $2
                """, json.dumps(focus_areas), student_id)
            return focus_areas

async def get_question_text(question_id: int) -> Optional[str]:
    async with get_replica_pool().acquire() as conn:
        return await conn.fetchval("SELECT text FROM questions WHERE id = $1", question_id)

@cached(ttl=3600, key_prefix="question")
async def fetch_question(question_id: int) -> Optional[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM questions WHERE id = $1", question_id)
        if row:
            q = dict(row)
            if isinstance(q.get("options"), str):
                try:
                    q["options"] = json.loads(q["options"])
                except (json.JSONDecodeError, TypeError):
                    q["options"] = []
            return q
    return None

async def fetch_questions_bulk(question_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not question_ids:
        return {}

    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM questions WHERE id = ANY($1::int[])",
            question_ids
        )

    result: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        q = dict(row)
        if isinstance(q.get("options"), str):
            try:
                q["options"] = json.loads(q["options"])
            except (json.JSONDecodeError, TypeError):
                q["options"] = []
        result[q["id"]] = q
    return result

async def check_and_unlock_badge(student_id: int, book_id: str) -> Optional[str]:
    badge_map = {
        "Mathematics": "math_magician",
        "Science": "science_scholar",
        "English": "english_expert",
        "Hindi": "hindi_master"
    }
    badge = badge_map.get(book_id)
    if not badge:
        return None
        
    async with get_pool().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT unlocked_badges FROM students WHERE id = $1", student_id)
            if not row:
                return None
                
            badges = []
            if row["unlocked_badges"]:
                try:
                    badges = json.loads(row["unlocked_badges"])
                except Exception:
                    badges = []
                    
            if badge not in badges:
                badges.append(badge)
                await conn.execute("UPDATE students SET unlocked_badges = $1 WHERE id = $2", json.dumps(badges), student_id)
                return badge
    return None

async def get_subject_reading_progress(student_id: int, book_id: str, conn: Optional[asyncpg.Connection] = None) -> Dict[str, int]:
    if conn:
        rows = await conn.fetch("""
            SELECT chapter_id, COUNT(*) as completed_sections FROM reading_progress 
            WHERE student_id = $1 AND book_id = $2 AND completed = TRUE
            GROUP BY chapter_id
        """, student_id, book_id)
        return {row["chapter_id"]: row["completed_sections"] for row in rows}
        
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT chapter_id, COUNT(*) as completed_sections FROM reading_progress 
            WHERE student_id = $1 AND book_id = $2 AND completed = TRUE
            GROUP BY chapter_id
        """, student_id, book_id)
        return {row["chapter_id"]: row["completed_sections"] for row in rows}

async def get_subject_mastery_dict(student_id: int, book_id: str, conn: Optional[asyncpg.Connection] = None) -> Dict[str, Dict[str, Any]]:
    if conn:
        rows = await conn.fetch("""
            SELECT * FROM student_mastery 
            WHERE student_id = $1 AND book_id = $2
        """, student_id, book_id)
        return {row["chapter_id"]: dict(row) for row in rows}
        
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM student_mastery 
            WHERE student_id = $1 AND book_id = $2
        """, student_id, book_id)
        return {row["chapter_id"]: dict(row) for row in rows}

@cached(ttl=3600, key_prefix="book_pyq_counts")
async def get_book_pyq_counts(book_id: str) -> Dict[str, int]:
    """Return total PYQ MCQ count per chapter for a subject (cached)."""
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT chapter_id, COUNT(*) AS cnt FROM questions
            WHERE book_id = $1 AND is_pyq = TRUE AND question_type = 'mcq'
            GROUP BY chapter_id
        """, book_id)
        return {row["chapter_id"]: row["cnt"] for row in rows}


async def record_practice_attempt(student_id: int, book_id: str, chapter_id: str, question_id: int, is_correct: bool) -> None:
    async with get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO practice_question_attempts (student_id, book_id, chapter_id, question_id, is_correct)
            VALUES ($1, $2, $3, $4, $5)
        """, student_id, book_id, chapter_id, question_id, is_correct)


async def get_subject_practice_solved_dict(student_id: int, book_id: str, conn: Optional[asyncpg.Connection] = None) -> Dict[str, int]:
    """Return count of distinct PYQ questions solved per chapter for a subject."""
    if conn:
        rows = await conn.fetch("""
            SELECT pqa.chapter_id, COUNT(DISTINCT pqa.question_id) AS solved
            FROM practice_question_attempts pqa
            JOIN questions q ON q.id = pqa.question_id
            WHERE pqa.student_id = $1 AND pqa.book_id = $2
              AND pqa.is_correct = TRUE AND q.is_pyq = TRUE AND q.question_type = 'mcq'
            GROUP BY pqa.chapter_id
        """, student_id, book_id)
        return {row["chapter_id"]: row["solved"] for row in rows}
        
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT pqa.chapter_id, COUNT(DISTINCT pqa.question_id) AS solved
            FROM practice_question_attempts pqa
            JOIN questions q ON q.id = pqa.question_id
            WHERE pqa.student_id = $1 AND pqa.book_id = $2
              AND pqa.is_correct = TRUE AND q.is_pyq = TRUE AND q.question_type = 'mcq'
            GROUP BY pqa.chapter_id
        """, student_id, book_id)
        return {row["chapter_id"]: row["solved"] for row in rows}


async def get_subject_board_passed_dict(student_id: int, book_id: str, conn: Optional[asyncpg.Connection] = None) -> Dict[str, bool]:
    """Return whether the board exam has been passed per chapter for a subject."""
    if conn:
        rows = await conn.fetch("""
            SELECT chapter_id FROM exam_attempts
            WHERE student_id = $1 AND book_id = $2 AND passed = TRUE
        """, student_id, book_id)
        return {row["chapter_id"]: True for row in rows}
        
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT chapter_id FROM exam_attempts
            WHERE student_id = $1 AND book_id = $2 AND passed = TRUE
        """, student_id, book_id)
        return {row["chapter_id"]: True for row in rows}


async def get_chapter_practice_solved_count(student_id: int, book_id: str, chapter_id: str) -> int:
    """Return count of distinct PYQ MCQ questions the student solved in a chapter."""
    async with get_replica_pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COUNT(DISTINCT pqa.question_id) AS solved
            FROM practice_question_attempts pqa
            JOIN questions q ON q.id = pqa.question_id
            WHERE pqa.student_id = $1 AND pqa.book_id = $2 AND pqa.chapter_id = $3
              AND pqa.is_correct = TRUE AND q.is_pyq = TRUE AND q.question_type = 'mcq'
        """, student_id, book_id, chapter_id)
        return row["solved"] if row else 0


@cached(ttl=3600, key_prefix="pyq_mcqs")
async def get_chapter_pyq_mcqs(book_id: str, chapter_id: str) -> List[Dict[str, Any]]:
    async with get_replica_pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM questions
            WHERE book_id = $1 AND chapter_id = $2 AND is_pyq = TRUE AND question_type = 'mcq'
            ORDER BY pyq_year DESC, id ASC
        """, book_id, chapter_id)
        return [dict(r) for r in rows]


# NOTE: add_question is defined earlier (see ~L670) with q_key + ON CONFLICT
# upsert semantics. A second, non-idempotent definition used to live here and
# silently shadowed it (Python keeps the last def), breaking PYP ingestion
# (`unexpected keyword argument 'q_key'`). It has been removed.
#
# NOTE: get_latest_exam_attempt is defined earlier (see ~L850).
# The duplicate definition that used to live here has been removed (F811).
