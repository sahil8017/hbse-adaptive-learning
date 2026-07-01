import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from fastapi import FastAPI, Request, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.core.cache import cache_manager
from backend.app.core.limiter import limiter
from backend.app.api.endpoints import router as api_router
from backend.app.core.logging_config import configure_logging, request_id_middleware
from backend.app.core.metrics import http_request_duration_seconds, http_requests_total
import structlog

# Initialize structured logging
configure_logging()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Sentry SDK
sentry_dsn = os.getenv("SENTRY_DSN", "")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            AsyncioIntegration(),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        environment=os.getenv("ENV", "development"),
        release=os.getenv("GIT_SHA", "unknown"),
        ignore_errors=["HTTPException"],
    )
    logger.info("Sentry SDK initialized successfully.")
else:
    logger.warning("SENTRY_DSN not set. Sentry error tracking is disabled.")

def _log_step(n, total, msg, since=None):
    """Log startup progress step with optional elapsed time."""
    elapsed = f" ({time.monotonic()-since:.1f}s)" if since is not None else ""
    logger.info("[%d/%d] %s%s", n, total, msg, elapsed)


async def _preload_embedding_model():
    """Preload embedding model in background thread (non-blocking)."""
    from backend.app.services.rag import get_embedding_model
    loop = asyncio.get_event_loop()
    t = time.monotonic()
    logger.info("[RAG] Preloading embedding model in background thread…")
    try:
        await loop.run_in_executor(None, get_embedding_model)
        logger.info("[RAG] Embedding model ready (%.1f s)", time.monotonic() - t)
    except Exception as exc:
        logger.error("[RAG] Model preload failed: %s", exc)


async def poll_db_pool_metrics():
    """Periodically poll connection pool status and update Prometheus metrics."""
    from backend.app.core.database import db_pool
    from backend.app.core.metrics import db_connection_pool_size, db_connection_pool_max
    while True:
        try:
            if db_pool:
                db_connection_pool_size.set(db_pool.get_size())
                max_size = getattr(db_pool, "_maxsize", 15)
                db_connection_pool_max.set(max_size)
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Error polling DB pool metrics: {e}")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.monotonic()

    # Surface risky/missing configuration early (non-fatal).
    from backend.app.core.config import validate_production_config
    validate_production_config(settings)

    # [1/5] Connect to cache manager
    _log_step(1, 5, "Connecting to Redis…")
    t_redis = time.monotonic()
    await cache_manager.connect()
    _log_step(1, 5, "Redis ready", t_redis)

    # [2/5] Initialize connection pool and create tables
    _log_step(2, 5, "Initialising database…")
    t_db = time.monotonic()
    await init_db()
    _log_step(2, 5, "Database ready", t_db)

    # Start periodic DB pool monitoring background task
    pool_task = asyncio.create_task(poll_db_pool_metrics())

    # [3/5] Schedule background model preload (non-blocking)
    _log_step(3, 5, "Scheduling embedding model preload (background)…")
    asyncio.create_task(_preload_embedding_model())

    # [4/5] Check RAG chunks and optional ingestion
    _log_step(4, 5, "Checking RAG chunks…")

    # Avoid expensive textbook ingestion on every dev restart unless explicitly enabled.
    if settings.RAG_INGEST_ON_STARTUP:
        try:
            from backend.app.services.rag import ingest_structured_textbooks
            await ingest_structured_textbooks()
            logger.info("Textbook RAG ingestion completed on startup.")
        except Exception as e:
            logger.error("Error during startup RAG ingestion: %s", e)
    else:
        logger.info("Skipping textbook RAG ingestion on startup (RAG_INGEST_ON_STARTUP is disabled).")

    # Warn if Science/Math have no embeddings
    try:
        from backend.app.services import rag as rag_service
        for book_id in ["Mathematics", "Science"]:
            count = await rag_service.count_chunks(book_id=book_id)
            if count == 0:
                logger.warning(
                    f"RAG: No chunks found for {book_id}. "
                    f"Run ingest_ncert.py before serving students."
                )
            else:
                logger.info(f"RAG: Found {count} chunks for {book_id}.")
    except Exception as e:
        logger.error("Error during startup RAG check: %s", e)

    # [5/5] Start background scheduler for nightly tasks
    _log_step(5, 5, "Starting scheduler…")
    scheduler = None
    try:
        from backend.app.services.scheduler import scheduler
        await scheduler.start()
        logger.info("Background job scheduler started.")
    except Exception as e:
        logger.error("Failed to start background scheduler: %s", e)

    logger.info("Startup complete in %.1f s", time.monotonic() - t0)

    yield
    
    # Disconnect cache manager
    await cache_manager.disconnect()
    
    # Close database pools
    from backend.app.core.database import close_db
    await close_db()
    
    # Cancel DB pool polling task
    pool_task.cancel()
    try:
        await pool_task
    except asyncio.CancelledError:
        pass
        
    # Shutdown background scheduler
    if scheduler is not None:
        try:
            scheduler.shutdown()
            logger.info("Background job scheduler shut down.")
        except Exception as e:
            logger.error("Failed to shut down background scheduler: %s", e)

app = FastAPI(title="HBSE Adaptive Learning Platform", lifespan=lifespan)


def _redact_request_headers(headers: Request.headers.__class__) -> dict[str, str]:
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in {"authorization", "cookie", "set-cookie", "x-admin-secret"}:
            redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted

# Custom Middleware for Sentry Context & Prometheus HTTP metrics
async def observability_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    
    # Skip metrics endpoint to avoid metrics pollution
    if endpoint == "/metrics":
        return await call_next(request)
        
    start_time = time.time()
    
    # Retrieve request ID from structlog context if available, otherwise generate
    ctx = structlog.contextvars.get_contextvars()
    request_id = ctx.get("request_id", str(uuid.uuid4())[:8])
    
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("request_id", request_id)
        scope.set_tag("endpoint", endpoint)
        scope.set_context("http", {
            "method": method,
            "url": str(request.url),
            "headers": _redact_request_headers(request.headers),
        })
                
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
            scope.set_tag("status_code", status_code)
            
            # Record metrics
            elapsed = time.time() - start_time
            http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint, status=status_code).observe(elapsed)
            
            return response
        except Exception as e:
            sentry_sdk.capture_exception(e)
            scope.set_tag("status_code", "500")
            
            # Record metrics
            elapsed = time.time() - start_time
            http_requests_total.labels(method=method, endpoint=endpoint, status="500").inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint, status="500").observe(elapsed)
            raise e

# Add middlewares (FastAPI executes them in reverse order of declaration)
app.middleware("http")(observability_middleware)  # Runs second (inner)
app.middleware("http")(request_id_middleware)    # Runs first (outer)

# Add Rate Limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS configuration
# In non-production environments, also allow common localhost dev ports.
# In production (ENV=production), only origins from settings.ALLOWED_ORIGINS are accepted.
_is_production = os.getenv("ENV", "development").lower() == "production"
_dev_origins: set[str] = (
    set()
    if _is_production
    else {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    }
)
allowed_origins = sorted({*(settings.ALLOWED_ORIGINS or []), *_dev_origins})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=(
        None if _is_production else r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Admin-Secret"],
    expose_headers=["Content-Type", "Content-Length", "Content-Disposition"],
)

# ── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status": exc.status_code,
            "message": exc.detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation failed for request %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Validation failed.",
            "detail": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error occurred during request processing: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Internal server error."
        }
    )

# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics(request: Request):
    """Prometheus metrics endpoint."""
    metrics_token = settings.METRICS_BEARER_TOKEN.strip()
    if metrics_token:
        auth_header = request.headers.get("authorization", "")
        expected = f"Bearer {metrics_token}"
        if auth_header != expected:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized metrics access.")
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# Include the modular api routes
app.include_router(api_router, prefix="/api")

# Include admin routes (protected by require_admin dependency)
from backend.app.api.admin import router as admin_router
app.include_router(admin_router, prefix="/api")
