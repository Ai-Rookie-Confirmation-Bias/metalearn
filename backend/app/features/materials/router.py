"""[1.Controller] 자료 업로드·파싱·RAG 색인 API — 골격.

기획서 §2 1단계(업로드): PDF → 파싱 → doc_chunks 색인. parsing 브랜치에서 재구현 예정.
"""
from fastapi import APIRouter

router = APIRouter()
