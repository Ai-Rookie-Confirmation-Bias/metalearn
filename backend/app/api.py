"""features/ 내 모든 라우터를 하나로 통합 (main에서 '/api' prefix로 등록).

블루프린트(기획서 §9) 기준 재구성 중. 현재 각 feature 라우터는 골격(스텁) 상태이며,
도메인 로직을 재구현하면서 엔드포인트를 채운다.
"""
from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.curriculum.router import router as curriculum_router
from app.features.learning.router import router as learning_router
from app.features.materials.router import router as materials_router
from app.features.review.router import router as review_router
from app.features.seed.router import router as seed_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(materials_router, prefix="/materials", tags=["materials"])
api_router.include_router(seed_router, prefix="/seed", tags=["seed"])
# curriculum/learning은 docs/API.md 경로(/courses/:id, /chapters/:id, /sections/:id,
# /attempts)와 일치해야 하므로 prefix 없이 등록한다.
api_router.include_router(curriculum_router, tags=["curriculum"])
api_router.include_router(learning_router, tags=["learning"])
api_router.include_router(review_router, prefix="/review", tags=["review"])
