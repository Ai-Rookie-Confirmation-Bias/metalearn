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


async def generate_from_parsing(
    db: Session,
    llm: LLMClient,
    course_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    verify_llm: LLMClient | None = None,
    config: QuizGenConfig | None = None,
    append: bool = False,
) -> QuizGenerationResult:
    """파싱 문서 하나로 문제은행을 만든다. 같은 문서를 다시 부르면 교체된다.

    append=True는 리필 — 문제를 다 푼 사용자를 위해 기존 은행을 유지한 채
    새 문항만 추가한다 (발문 중복은 서비스가 걸러냄).
    """
    parsed = parsed_document_of(db, document_id)
    service = QuizService(db, llm, verify_llm=verify_llm)
    return await service.generate_bank(
        course_id, document_id, parsed, config=config, append=append
    )
