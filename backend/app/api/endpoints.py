from fastapi import APIRouter

# Import split routers
from backend.app.api.auth import router as auth_router
from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.learning import router as learning_router
from backend.app.api.practice import router as practice_router
from backend.app.api.pyp import router as pyp_router
from backend.app.api.chat import router as chat_router
from backend.app.api.exam import router as exam_router
from backend.app.api.analytics import router as analytics_router
from backend.app.api.llm import router as llm_router
from backend.app.api.privacy import router as privacy_router

router = APIRouter()

# Include routes
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(learning_router)
router.include_router(practice_router)
router.include_router(pyp_router)
router.include_router(chat_router)
router.include_router(exam_router)
router.include_router(analytics_router)
router.include_router(llm_router)
router.include_router(privacy_router)

# Health check endpoint directly on root router
@router.get("/health")
async def api_health():
    return {"status": "ok"}



