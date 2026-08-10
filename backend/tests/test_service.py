"""파이프라인 엔드투엔드 — LLM·DB를 fake로 대체하고 흐름 전체를 검증."""
import re
import uuid

import pytest

from app.core.llm.base import LLMClient
from app.features.quiz.service import QuizService


class FakeLLM(LLMClient):
    """생성 → 개념마다 trueFalse 1개 / 심판 → 전원 합격 / 풀이자 → 정답(true) / 수정 → 없음."""

    def __init__(self) -> None:
        self.generation_calls = 0
        self.verification_calls = 0
        self.solve_calls = 0
        self.revision_calls = 0

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "출제 검수자" in prompt:
            self.verification_calls += 1
            n = prompt.count("[문항 ")
            entries = ",".join(f'{{"index":{i},"pass":true,"reason":""}}' for i in range(n))
            return f"[{entries}]"
        if "너는 수험생이다" in prompt:
            self.solve_calls += 1
            n = prompt.count("[문항 ")
            # FakeLLM이 만드는 문항은 전부 trueFalse(answer=true) — 정답을 답한다
            entries = ",".join(f'{{"index":{i},"answer":true}}' for i in range(n))
            return f"[{entries}]"
        if "검수 불합격" in prompt:
            self.revision_calls += 1
            return "[]"

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

    def append_document_items(self, items) -> None:
        self.rows.extend(items)

    def list_document_items(self, course_id, document_id):
        return list(self.rows)

    def sample_items(
        self, course_id, document_id, toc_indexes, count, exclude_ids=None, style=None
    ):
        # 실제 repo 계약의 축소판 — 안 푼 것 먼저, 모자라면 exclude 순서(오래된
        # 순)대로 복습 채움. 반환도 동일하게 (items, recycled).
        exclude = exclude_ids or []
        pool = [r for r in self.rows if r.toc_index in toc_indexes]
        if style:
            pool = [r for r in pool if getattr(r, "style", "standard") == style]
        fresh = [r for r in pool if r.id not in exclude][:count]
        shortfall = count - len(fresh)
        if shortfall <= 0 or not exclude:
            return fresh, 0
        by_id = {r.id: r for r in pool}
        recycled = [by_id[i] for i in exclude if i in by_id][:shortfall]
        return fresh + recycled, len(recycled)

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
    # 조각 3개 = 생성 콜 3회, 심판·풀이 왕복이 실제로 돌았는지
    assert service.llm.generation_calls == 3
    assert service.llm.verification_calls >= 1
    assert service.llm.solve_calls >= 1


async def test_failed_item_revived_by_revision_loop(service):
    """critique-revise: 심판 불합격 문항이 사유 첨부 수정 1회로 살아난다."""
    from app.features.quiz.schemas import (
        ParsedChunk,
        ParsedConcept,
        ParsedDocument,
        ParsedToc,
        SentenceAnchor,
    )

    doc = ParsedDocument(
        parser_version="3.0",
        tocs=[ParsedToc(index=0, title="1장", chunk_indexes=[0])],
        chunks=[
            ParsedChunk(
                index=0,
                page_from=1,
                page_to=1,
                raw_text="폭포수 모형은 고전적 생명 주기 모형이다.",
                sentences=[SentenceAnchor(start=0, end=22)],
                concepts=[ParsedConcept(name="폭포수 모형", definition="고전적 모형")],
            )
        ],
    )

    class ReviseLLM(FakeLLM):
        def __init__(self) -> None:
            super().__init__()
            self.judge_seen = 0

        async def generate(self, prompt: str, **kwargs: object) -> str:
            if "출제 검수자" in prompt:
                self.judge_seen += 1
                if self.judge_seen == 1:  # 1차 심판: 전원 불합격
                    n = prompt.count("[문항 ")
                    entries = ",".join(
                        f'{{"index":{i},"pass":false,"reason":"발문 모호"}}' for i in range(n)
                    )
                    return f"[{entries}]"
                return await super().generate(prompt)  # 재검사: 합격
            if "검수 불합격" in prompt:
                self.revision_calls += 1
                return ('[{"index":0,"data":{"statement":"폭포수 모형은 고전적 생명 주기 '
                        '모형이다","answer":true,"explanation":"수정본"}}]')
            return await super().generate(prompt)

    service.llm = ReviseLLM()
    result = await service.generate_bank(uuid.uuid4(), uuid.uuid4(), doc)
    assert service.llm.revision_calls == 1
    assert result.saved == 1  # 불합격 → 수정 → 재검사 통과 → 저장
    assert service.repo.rows[0].data["explanation"] == "수정본"


async def test_generate_bank_rejects_bad_version_only_when_gate_configured(service, parsed_doc):
    from app.features.quiz.schemas import QuizGenConfig

    doc = parsed_doc.model_copy(update={"parser_version": "9.9"})
    config = QuizGenConfig(supported_parser_versions=["3.0"])
    result = await service.generate_bank(uuid.uuid4(), uuid.uuid4(), doc, config=config)
    assert not result.report.ok
    assert result.saved == 0


async def test_generation_parse_failure_retries_then_reports(service):
    """QUIZ_TUNING §4: 응답 파싱 실패는 1회 재시도, 그래도 비면 리포트에 남는다."""
    from app.features.quiz.schemas import (
        ParsedChunk,
        ParsedConcept,
        ParsedDocument,
        ParsedToc,
        SentenceAnchor,
    )

    doc = ParsedDocument(
        parser_version="3.0",
        tocs=[ParsedToc(index=0, title="1장", chunk_indexes=[0])],
        chunks=[
            ParsedChunk(
                index=0,
                page_from=1,
                page_to=1,
                raw_text="폭포수 모형은 고전적 생명 주기 모형이다.",
                sentences=[SentenceAnchor(start=0, end=22)],
                concepts=[ParsedConcept(name="폭포수 모형", definition="고전적 모형")],
            )
        ],
    )

    class GarbageLLM(FakeLLM):
        async def generate(self, prompt: str, **kwargs: object) -> str:
            if "출제 검수자" in prompt:
                return await super().generate(prompt)
            self.generation_calls += 1
            return "JSON이 아닌 잡담"

    service.llm = GarbageLLM()
    result = await service.generate_bank(uuid.uuid4(), uuid.uuid4(), doc)
    assert service.llm.generation_calls == 2  # 재시도 1회
    assert result.saved == 0
    assert any("파싱 실패" in d for d in result.discarded)


async def test_session_and_attempt_flow(service, parsed_doc):
    course_id, document_id = uuid.uuid4(), uuid.uuid4()
    await service.generate_bank(course_id, document_id, parsed_doc)
    for row in service.repo.rows:  # ORM 밖이라 PK 수동 부여
        row.id = uuid.uuid4()

    session = service.start_session(course_id, document_id, [0], count=5)
    assert 1 <= len(session.items) <= 5
    assert session.recycled == 0  # 푼 기록 없이 시작 — 전부 새 문항
    for item in session.items:
        assert "answer" not in item.data  # trueFalse 정답 미노출

    first = session.items[0]
    resp = service.submit_attempt(uuid.UUID(first.id), True)
    assert resp.correct is True  # FakeLLM은 answer=true로 생성
    assert resp.evidence["text"]
    assert resp.answer["answer"] is True


async def test_session_prefers_unsolved_then_recycles(service, parsed_doc):
    """안 푼 문항 우선 — 모자라면 푼 지 오래된 순으로 복습이 뒤에 붙는다."""
    course_id, document_id = uuid.uuid4(), uuid.uuid4()
    await service.generate_bank(course_id, document_id, parsed_doc)
    for row in service.repo.rows:  # ORM 밖이라 PK 수동 부여
        row.id = uuid.uuid4()
    pool = [r for r in service.repo.rows if r.toc_index == 0]
    assert len(pool) >= 2

    # 첫 문항만 푼 상태 → 안 푼 것들이 먼저, 푼 것은 나오지 않는다(수량 충분)
    solved = [pool[0].id]
    session = service.start_session(
        course_id, document_id, [0], count=len(pool) - 1, exclude_ids=solved
    )
    assert session.recycled == 0
    assert str(pool[0].id) not in [i.id for i in session.items]

    # 전부 푼 상태에서 더 달라고 하면 → 빈손 대신 오래된 순 복습으로 채워진다
    solved = [r.id for r in pool]
    session = service.start_session(
        course_id, document_id, [0], count=len(pool), exclude_ids=solved
    )
    assert session.recycled == len(session.items) == len(pool)
    assert [uuid.UUID(i.id) for i in session.items] == solved


async def test_generate_bank_append_keeps_bank_and_dedupes(service, parsed_doc):
    """리필(append) — 기존 은행 유지, 발문이 같은 문항은 폐기."""
    course_id, document_id = uuid.uuid4(), uuid.uuid4()
    await service.generate_bank(course_id, document_id, parsed_doc)
    first = list(service.repo.rows)
    assert first

    # FakeLLM은 같은 입력에 같은 발문을 만든다 → 리필 전부 중복 폐기가 정답
    result = await service.generate_bank(
        course_id, document_id, parsed_doc, append=True
    )
    assert result.saved == 0
    assert service.repo.rows == first  # 교체 아님 — 기존 은행 그대로
    assert any("발문 중복" in d for d in result.discarded)


async def test_generate_bank_replace_dedupes_within_batch(service, parsed_doc):
    """교체 모드도 같은 배치 안의 발문 중복은 하나만 저장한다 (08-07 실측 결함)."""

    class EchoTwiceLLM(FakeLLM):
        async def generate(self, prompt: str, **kwargs: object) -> str:
            raw = await super().generate(prompt, **kwargs)
            if "출제 검수자" in prompt or "너는 수험생이다" in prompt:
                return raw
            # 생성 응답의 문항 배열을 통째로 두 번 — 배치 내 완전 중복 상황
            inner = raw[1:-1]
            return f"[{inner},{inner}]" if inner else raw

    service.llm = EchoTwiceLLM()
    result = await service.generate_bank(uuid.uuid4(), uuid.uuid4(), parsed_doc)
    assert result.saved > 0
    keys = [(r.type, r.data.get("statement")) for r in service.repo.rows]
    assert len(keys) == len(set(keys))  # 저장분엔 중복 없음
    assert any("같은 배치 내 발문 중복" in d for d in result.discarded)


def test_content_key_normalizes_whitespace_and_cloze():
    from app.features.quiz.service import _content_key

    # 공백만 다른 발문은 같은 문항 취급
    assert _content_key("mcq", {"question": "OSI 7계층은?"}) == _content_key(
        "mcq", {"question": "OSI  7계층은?"}
    )
    # cloze는 text 조각을 이어 붙여 비교 (빈칸 자리는 무시)
    assert _content_key(
        "cloze",
        {"segments": [{"kind": "text", "text": "최하위 계층은 "}, {"kind": "blank"}]},
    ) == _content_key("cloze", {"segments": [{"kind": "text", "text": "최하위계층은"}]})
    # 유형이 다르면 발문이 같아도 다른 문항
    assert _content_key("mcq", {"question": "q"}) != _content_key(
        "trueFalse", {"statement": "q"}
    )
