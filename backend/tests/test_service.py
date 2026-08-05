"""파이프라인 엔드투엔드 — LLM·DB를 fake로 대체하고 흐름 전체를 검증."""
import re
import uuid

import pytest

from app.core.llm.base import LLMClient
from app.features.quiz.service import QuizService


class FakeLLM(LLMClient):
    """생성 프롬프트 → 지시된 개념마다 trueFalse 1개 / 심판 프롬프트 → 전원 합격."""

    def __init__(self) -> None:
        self.generation_calls = 0
        self.verification_calls = 0

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "출제 검수자" in prompt:
            self.verification_calls += 1
            n = prompt.count("[문항 ")
            entries = ",".join(f'{{"index":{i},"pass":true,"reason":""}}' for i in range(n))
            return f"[{entries}]"

        self.generation_calls += 1
        items = []
        for m in re.finditer(r"^- (.+?) \(\w+\) → .+? · 근거 후보: s(\d+)", prompt, re.M):
            name, sid = m.group(1), m.group(2)
            items.append(
                f'{{"type":"trueFalse","concept":"{name}",'
                f'"data":{{"statement":"{name} 관련 진술","answer":true,"explanation":"e"}},'
                f'"evidence":["s{sid}"],"difficulty":2}}'
            )
        return "[" + ",".join(items) + "]"

    async def embed(self, text: str) -> list[float]:
        return []


class FakeRepo:
    def __init__(self) -> None:
        self.rows = []

    def replace_document_items(self, course_id, document_id, items) -> None:
        self.rows = items

    def sample_items(self, course_id, document_id, toc_indexes, count):
        return [r for r in self.rows if r.toc_index in toc_indexes][:count]

    def get_item(self, item_id):
        return next((r for r in self.rows if r.id == item_id), None)

    def record_attempt(self, item_id, correct, user_input, user_id=None) -> None:
        pass


@pytest.fixture
def service() -> QuizService:
    svc = QuizService.__new__(QuizService)
    svc.repo = FakeRepo()
    svc.llm = FakeLLM()
    return svc


async def test_generate_bank_end_to_end(service, parsed_doc):
    course_id, document_id = uuid.uuid4(), uuid.uuid4()
    result = await service.generate_bank(course_id, document_id, parsed_doc)

    assert result.report.ok
    assert result.saved > 0
    rows = service.repo.rows
    # 전부 verified, 목차 귀속, evidence에 원문 슬라이스 포함
    assert all(r.verified for r in rows)
    assert {r.toc_index for r in rows} <= {t.index for t in parsed_doc.tocs}
    for r in rows:
        assert r.evidence["text"]
        assert r.evidence["sentenceRanges"]
    # 조각 3개 = 생성 콜 3회
    assert service.llm.generation_calls == 3
    assert service.llm.verification_calls >= 1


async def test_generate_bank_rejects_bad_parser_version(service, parsed_doc):
    doc = parsed_doc.model_copy(update={"parser_version": "9.9"})
    result = await service.generate_bank(uuid.uuid4(), uuid.uuid4(), doc)
    assert not result.report.ok
    assert result.saved == 0


async def test_session_and_attempt_flow(service, parsed_doc):
    course_id, document_id = uuid.uuid4(), uuid.uuid4()
    await service.generate_bank(course_id, document_id, parsed_doc)
    for row in service.repo.rows:  # ORM 밖이라 PK 수동 부여
        row.id = uuid.uuid4()

    session = service.start_session(course_id, document_id, [0], count=5)
    assert 1 <= len(session.items) <= 5
    for item in session.items:
        assert "answer" not in item.data  # trueFalse 정답 미노출

    first = session.items[0]
    resp = service.submit_attempt(uuid.UUID(first.id), True)
    assert resp.correct is True  # FakeLLM은 answer=true로 생성
    assert resp.evidence["text"]
    assert resp.answer["answer"] is True
