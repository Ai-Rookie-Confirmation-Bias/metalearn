"""features/ 내 모든 라우터를 하나로 통합 (main에서 '/api' prefix로 등록).

병합(backend-ai-core + parsing) 통합 라우팅:
  - curriculum/learning은 docs/API.md 경로(/courses/:id, /chapters/:id, /sections/:id,
    /attempts)와 일치해야 하므로 prefix 없이 등록한다.
  - documents/diagnostic은 parsing 상류 파이프라인.
    TODO(병합 2단계): 두 라우터는 Integer PK 모델을 임포트하므로 UUID 포팅 전까지
    등록 보류 — 포팅 완료 후 아래 주석을 해제한다.
"""
from fastapi import APIRouter

from app.features.auth.router import router as auth_router
from app.features.curriculum.router import router as curriculum_router
from app.features.learning.router import router as learning_router
from app.features.materials.router import router as materials_router
from app.features.review.router import router as review_router
from app.features.seed.router import router as seed_router

# TODO(병합 2단계, UUID 포팅 후 활성화):
# from app.features.documents.router import router as documents_router
# from app.features.diagnostic.router import router as diagnostic_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(materials_router, prefix="/materials", tags=["materials"])
api_router.include_router(seed_router, prefix="/seed", tags=["seed"])
api_router.include_router(curriculum_router, tags=["curriculum"])
api_router.include_router(learning_router, tags=["learning"])
api_router.include_router(review_router, prefix="/review", tags=["review"])
# TODO(병합 2단계):
# api_router.include_router(documents_router, prefix="/documents", tags=["documents"])
# api_router.include_router(diagnostic_router, prefix="/diagnostic", tags=["diagnostic"])
