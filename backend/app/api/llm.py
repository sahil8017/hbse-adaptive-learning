"""LLM status and warmup endpoints."""
import logging

from fastapi import APIRouter, Depends
from backend.app.core.security import get_current_student
from backend.app.core.config import settings
from backend.app.services.llm_health import get_llm_status

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health/llm")
async def api_health_llm():
    """Check reachability of LLM providers. No auth required."""
    from fastapi.responses import JSONResponse
    status_data = await get_llm_status()
    code = 200 if status_data["any_available"] else 503
    return JSONResponse(content=status_data, status_code=code)


@router.get("/llm/warmup")
async def api_llm_warmup(student: dict = Depends(get_current_student)):
    """Confirm LLM provider availability."""
    if settings.OPENROUTER_API_KEY:
        return {"status": "ready", "provider": "openrouter"}
    return {"status": "unavailable", "provider": "none"}
