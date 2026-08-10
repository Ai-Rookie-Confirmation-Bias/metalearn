"""기출 스타일 프로파일 (QUIZ.md §2-③) — kind=exam 자료에서 추출·저장.

원칙: 기출 문항은 은행에 절대 복사하지 않는다. 뽑는 것은 두 가지뿐 —
  - stemPatterns  발문의 틀 ("다음 설명에 해당하는 용어를 쓰시오" 류, 내용 제거)
  - conceptFrequency  기출에 등장한 개념 이름과 횟수 (출제 예산 가중치용)

추출은 조각당 LLM 1콜. 기출 문서는 문항 단위 파싱이 없어도 조각 텍스트에서
발문 패턴이 반복적으로 드러나므로 이 수준으로 충분하다 (유형 분포 추정은
오차가 커서 1차에서 뺐다 — type_ratio는 기본값 유지).
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.base import LLMClient
from app.core.quality.parsing import extract_json
from app.features.course.models import Course, CourseDocument
from app.features.parsing.models import DocStatus, Document

logger = logging.getLogger("uvicorn.error")

MAX_STEMS = 8  # 프롬프트 슬롯에 들어갈 발문 틀 상한 (생성 쪽은 상위 5개 사용)

_EXTRACT_PROMPT = """아래는 기출 문제 모음의 일부다. 두 가지만 뽑아라:

1. stems: 발문의 **틀** — 구체 내용은 지우고 문형만.
   예: "다음 설명에 해당하는 용어를 쓰시오", "~에 대한 설명으로 옳지 않은 것은?"
   이 텍스트에 실제로 있는 문형만. 지어내지 마라.
2. concepts: 문제가 다루는 **개념 이름**과 등장 횟수.
   예: {{"name": "정규화", "count": 2}}. 일반 단어(설명, 다음, 보기)는 개념이 아니다.

[기출 텍스트]
{text}

[출력] JSON 객체 하나만:
{{"stems": ["..."], "concepts": [{{"name": "...", "count": 1}}]}}"""


def exam_documents_of(db: Session, course_id: uuid.UUID) -> list[Document]:
    """이 코스에 묶인 kind=exam 문서들 (파싱 ready만)."""
    rows = (
        db.query(Document)
        .join(CourseDocument, CourseDocument.document_id == Document.id)
        .filter(
            CourseDocument.course_id == course_id,
            Document.kind == "exam",
            Document.status == DocStatus.READY.value,
        )
        .all()
    )
    return rows


async def ensure_profile(
    db: Session, llm: LLMClient, course_id: uuid.UUID
) -> dict | None:
    """코스의 기출 프로파일을 반환. 없고 기출 자료가 있으면 지금 추출해 저장.

    본문 자료의 은행 생성 직전에 불린다 — 기출 파싱이 아직 안 끝났으면
    프로파일 없이 진행하고, 다음 생성(리필 포함)에서 다시 시도한다.
    """
    course = db.get(Course, course_id)
    if course is None:
        return None
    if course.exam_style_profile:
        return course.exam_style_profile

    exam_docs = exam_documents_of(db, course_id)
    if not exam_docs:
        return None

    profile = await _build_profile(db, llm, exam_docs)
    if profile is None:
        return None
    course.exam_style_profile = profile
    db.commit()
    logger.info(
        "기출 프로파일 저장: course=%s 발문틀 %d개 · 개념 %d개 (자료 %d권)",
        course_id, len(profile["stemPatterns"]),
        len(profile["conceptFrequency"]), len(exam_docs),
    )
    return profile


async def _build_profile(
    db: Session, llm: LLMClient, exam_docs: list[Document]
) -> dict | None:
    # 지연 import — quiz.bridge가 parsing.service를 물고 있어 상단 import는 순환
    from app.features.quiz import bridge

    stems: list[str] = []
    freq: dict[str, int] = {}
    for doc in exam_docs:
        try:
            parsed = bridge.parsed_document_of(db, doc.id)
        except LookupError:
            continue
        for chunk in parsed.chunks:
            text = chunk.raw_text[:3500]
            raw = await llm.generate(
                _EXTRACT_PROMPT.format(text=text),
                model=settings.QUIZ_CHAT_MODEL,
                json_mode=True,
            )
            data = extract_json(raw)
            if not isinstance(data, dict):
                continue
            for s in data.get("stems", []) or []:
                s = str(s).strip()
                if 5 <= len(s) <= 80 and s not in stems:
                    stems.append(s)
            for c in data.get("concepts", []) or []:
                if not isinstance(c, dict):
                    continue
                name = str(c.get("name", "")).strip()
                if 2 <= len(name) <= 40:
                    freq[name] = freq.get(name, 0) + max(1, int(c.get("count", 1)))

    if not stems and not freq:
        return None
    return {
        "stemPatterns": stems[:MAX_STEMS],
        "conceptFrequency": freq,
        "builtFrom": [str(d.id) for d in exam_docs],
    }
