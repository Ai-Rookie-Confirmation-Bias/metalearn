"""파싱 DocumentTree → 문제은행.

어댑터(`parsed_from_tree`)는 순수 변환만 한다. 여기는 **언제·무엇을** 올리는지.
커리큘럼의 `features/curriculum/bridge.py`와 같은 자리, 같은 역할이다.

⚠️ 커리큘럼과 달리 **자동 주입은 하지 않는다.** 문항 생성은 조각마다 LLM을
   여러 번 부르는 비싼 작업이라(실측: 조각 1개 · 예산 4문항에 수십 초),
   목록을 여는 것 같은 읽기 요청에 딸려 돌면 안 된다. 명시 호출만 받는다.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.llm.base import LLMClient
from app.features.parsing.models import DocStatus
from app.features.parsing.service import ParsingService
from app.features.quiz.adapters import parsed_from_tree
from app.features.quiz.schemas import ParsedDocument, QuizGenConfig
from app.features.quiz.service import QuizGenerationResult, QuizService


def parsed_document_of(db: Session, document_id: uuid.UUID) -> ParsedDocument:
    """파싱 ready 문서 하나 → quiz 입력 형태.

    아직 파싱 중이면 LookupError. 부분 결과로 문항을 만들면 조용히 반쪽짜리
    은행이 생기고, 다시 만들 계기가 없다.
    """
    try:
        tree = ParsingService(db).get_tree(document_id)
    except ValueError as exc:
        raise LookupError(str(exc)) from exc

    if tree.document.status != DocStatus.READY.value:
        raise LookupError(
            f"아직 파싱이 끝나지 않았습니다: {document_id} "
            f"(status={tree.document.status})"
        )

    return parsed_from_tree(tree.model_dump(mode="json"))


def studied_toc_titles(
    db: Session, document_id: uuid.UUID, user_id: uuid.UUID
) -> set[str]:
    """학습 페이지에서 풀이 기록이 있는 단원 제목들 — 범위 화면 "학습함" 라벨용.

    QUIZ.md §3.5의 선: 학습 기록은 "어디를 풀지" **안내에만** 쓴다 (문항 선정
    불사용). 커리큘럼 진도는 사용자별 파일 스냅샷이라 목차 제목으로 잇는다 —
    인덱스는 진단이 보강 단원을 끼우면 밀리지만 제목은 같은 파싱 목차에서 온다.
    실패는 전부 빈 집합 — 라벨은 참고 정보라 요약 응답을 깨면 안 된다.
    """
    try:
        from app.features.curriculum.bridge import ingest_parsing_document
        from app.features.curriculum.store import store

        key = str(document_id)
        if key not in store.documents:
            ingest_parsing_document(db, document_id)
        doc = store.documents.get(key)
        if doc is None:
            return set()
        progress = store.progress_of(str(user_id))
        return {
            ch.title.strip()
            for ch in doc.chapters
            if any(progress.of(s.section_id).attempts > 0 for s in ch.sections)
        }
    except Exception:  # noqa: BLE001 — 참고 라벨이 요약을 깨면 안 된다
        return set()


async def generate_from_parsing(
    db: Session,
    llm: LLMClient,
    course_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    verify_llm: LLMClient | None = None,
    config: QuizGenConfig | None = None,
    append: bool = False,
    style: str = "standard",
) -> QuizGenerationResult:
    """파싱 문서 하나로 문제은행을 만든다. 같은 문서를 다시 부르면 교체된다.

    append=True는 리필 — 문제를 다 푼 사용자를 위해 기존 은행을 유지한 채
    새 문항만 추가한다 (발문 중복은 서비스가 걸러냄).

    style="exam"은 [기출문제 스타일로 생성] — 기본 흐름은 건드리지 않고,
    기출 프로파일(발문 말투·출제 가중치, QUIZ.md §2-③)을 반영한 문항을
    exam 표시를 달아 **추가**한다. 프로파일이 없으면(기출 자료 없음) 실패.
    """
    from app.features.quiz import exam_style

    parsed = parsed_document_of(db, document_id)

    exam_frequency = None
    stem_patterns = None
    if style == "exam":
        profile = await exam_style.ensure_profile(db, llm, course_id)
        if not profile:
            raise LookupError(
                "기출 자료가 없거나 아직 파싱 중이라 기출 스타일을 만들 수 없습니다"
            )
        exam_frequency = profile.get("conceptFrequency") or None
        stem_patterns = (profile.get("stemPatterns") or [])[:5] or None

    service = QuizService(db, llm, verify_llm=verify_llm)
    return await service.generate_bank(
        course_id,
        document_id,
        parsed,
        config=config,
        append=append,
        style=style,
        exam_frequency=exam_frequency,
        stem_patterns=stem_patterns,
    )
