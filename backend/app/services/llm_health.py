"""LLM health check utilities — OpenRouter only."""
import logging
import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


async def check_openrouter_reachable(timeout: float = 3.0) -> bool:
    if not settings.OPENROUTER_API_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            )
            return r.status_code == 200
    except Exception as exc:
        logger.debug("OpenRouter unreachable: %s", exc)
        return False


async def get_llm_status() -> dict:
    openrouter_ok = await check_openrouter_reachable()
    return {
        "openrouter": openrouter_ok,
        "any_available": openrouter_ok,
    }
