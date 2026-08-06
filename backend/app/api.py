"""features/ 내 모든 라우터를 하나로 통합 (main에서 '/api' prefix로 등록)."""
from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.course.router import router as course_router
from app.features.curriculum.router import router as curriculum_router
from app.features.parsing.debug_router import router as parsing_debug_router
from app.features.parsing.router import router as parsing_router
from app.features.seed.router import router as seed_router
from app.features.materials.router import router as materials_router
from app.features.learning.router import router as learning_router
from app.features.review.router import router as review_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(parsing_router, prefix="/parsing", tags=["parsing"])
api_router.include_router(
    parsing_debug_router, prefix="/parsing/debug", tags=["parsing-debug"]
)
api_router.include_router(course_router, prefix="/courses", tags=["courses"])
api_router.include_router(curriculum_router, prefix="/curriculum", tags=["curriculum"])
api_router.include_router(seed_router, prefix="/seed", tags=["seed"])
api_router.include_router(materials_router, prefix="/materials", tags=["materials"])
api_router.include_router(learning_router, prefix="/learning", tags=["learning"])
api_router.include_router(review_router, prefix="/review", tags=["review"])
