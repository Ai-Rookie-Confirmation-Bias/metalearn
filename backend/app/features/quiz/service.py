"""[3.Service] 문제 생성 배치 + 서빙 로직 (docs/QUIZ.md §1 파이프라인).

배치: 수신검증 → 선별 → 계획 → 조각별 생성(LLM) → core/quality 검증
      (기계검사 → 심판 → 풀이 왕복 → 불합격 수정 1회) → verified만 저장(전체 교체).
서빙: DB 조회만 — LLM 호출 없음.
"""
import asyncio
import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.base import LLMClient
from app.core.quality import CandidateItem, QualityConfig, validate_items
from app.features.quiz import generation, grading, serving
from app.features.quiz.intake import validate_document
from app.features.quiz.models import QuizItem
from app.features.quiz.planning import plan_document
from app.features.quiz.prompts import build_generation_prompt
from app.features.quiz.repository import QuizRepository
from app.features.quiz.schemas import (
    AttemptResponse,
    ChunkWorkOrder,
    GeneratedItem,
    ParsedDocument,
    ParseReport,
    QuizBankSummary,
    QuizGenConfig,
    SessionItem,
    SessionResponse,
    TocSummary,
)
from app.features.quiz.selection import select_chunk

logger = logging.getLogger(__name__)


def _content_key(item_type: str, data: dict) -> tuple[str, str]:
    """문항 내용 동일성 키 — 리필 시 기존 은행과의 중복 대조용.

    발문(유형별 질문 텍스트)이 공백 제거 후 같으면 같은 문항으로 본다.
    선지·정답까지 보지 않는 이유: 같은 발문에 선지만 다른 문항은 풀이자에게
    사실상 같은 문제라 중복으로 치는 쪽이 안전하다.
    """
    if item_type == "cloze":
        text = "".join(
            str(s.get("text", ""))
            for s in data.get("segments", [])
            if isinstance(s, dict)
        )
    else:
        text = data.get("question") or data.get("statement") or data.get("prompt") or ""
    return item_type, re.sub(r"\s+", "", str(text))


class QuizGenerationResult:
    def __init__(self, report: ParseReport) -> None:
        self.report = report
        self.saved = 0
        self.discarded: list[str] = []  # "개념/유형: [단계] 사유"
        # 폐기 문항의 실제 내용 (품질 분석용 — API 응답에는 안 나감).
        # {"concept","type","reason","data"} — data가 없는 폐기(선별 제외·파싱 실패)는 미포함
        self.discarded_items: list[dict] = []


class QuizService:
    quality_config: QualityConfig = QualityConfig()  # __new__ 생성(테스트) 대비 기본값
    verify_llm: LLMClient | None = None  # 교차 검증 모델 (없으면 생성 모델이 검증까지)

    def __init__(
        self,
        db: Session,
        llm: LLMClient,
        quality_config: QualityConfig | None = None,
        verify_llm: LLMClient | None = None,
    ) -> None:
        self.repo = QuizRepository(db)
        self.llm = llm
        self.quality_config = quality_config or QualityConfig()
        self.verify_llm = verify_llm

    # ── 배치 (파싱 완료 트리거) ──────────────────────────

    async def generate_bank(
        self,
        course_id: uuid.UUID,
        document_id: uuid.UUID,
        doc: ParsedDocument,
        config: QuizGenConfig | None = None,
        exam_frequency: dict[str, int] | None = None,
        stem_patterns: list[str] | None = None,
        append: bool = False,
    ) -> QuizGenerationResult:
        """append=False(기본)는 이 문서의 은행을 통째로 교체, append=True는
        리필 — 기존 은행을 유지한 채 새 문항만 추가한다 (발문 중복은 폐기).
        """
        config = config or QuizGenConfig()

        report = validate_document(doc, config)
        result = QuizGenerationResult(report)
        if not report.ok:
            return result

        selections = {c.index: select_chunk(c) for c in doc.chunks}
        for sel in selections.values():
            for name, reason in sel.excluded_concepts.items():
                result.discarded.append(f"{name}: {reason}")

        orders = plan_document(doc, selections, config, exam_frequency)
        chunk_by_index = {c.index: c for c in doc.chunks}
        toc_title = {t.index: t.title for t in doc.tocs}

        # 조각 사이에는 의존성이 없어 동시에 돌린다 (실측 888초 → 직렬이 병목).
        # 동시 폭은 LLM 분당 제한을 넘지 않게 세마포어로 묶고, gather가 orders
        # 순서를 보존하므로 저장 순서는 직렬 때와 동일하다.
        sem = asyncio.Semaphore(config.gen_concurrency)

        async def _run_chunk(order: ChunkWorkOrder) -> list[QuizItem]:
            chunk = chunk_by_index[order.chunk_index]
            async with sem:
                verified_items = await self._generate_and_verify(
                    order, chunk, stem_patterns, result
                )
            return [
                QuizItem(
                    course_id=course_id,
                    document_id=document_id,
                    toc_index=order.toc_index,
                    toc_title=toc_title.get(order.toc_index, ""),
                    type=item.type,
                    concept_name=item.concept,
                    data=item.data,
                    evidence=generation.resolve_evidence(item, chunk),
                    difficulty=item.difficulty,
                    verified=True,
                )
                for item in verified_items
            ]

        rows: list[QuizItem] = [
            row
            for chunk_rows in await asyncio.gather(*(_run_chunk(o) for o in orders))
            for row in chunk_rows
        ]

        # 발문 중복 제거 — 리필(append)은 기존 은행까지, 교체는 이번 배치 안에서.
        # 같은 개념 풀에서 생성하므로 중복이 나오는 게 정상 경로다 (교체 모드도
        # 배치 내 중복이 실제로 났었음: 08-07 최초 생성분에서 3쌍 실측).
        seen: set[tuple[str, str]] = (
            {
                _content_key(r.type, r.data)
                for r in self.repo.list_document_items(course_id, document_id)
            }
            if append
            else set()
        )
        unique_rows: list[QuizItem] = []
        for row in rows:
            key = _content_key(row.type, row.data)
            if key in seen:
                against = "기존 은행과 발문 중복 (리필 대조)" if append else "같은 배치 내 발문 중복"
                result.discarded.append(f"{row.concept_name}/{row.type}: {against}")
                continue
            seen.add(key)
            unique_rows.append(row)

        if append:
            self.repo.append_document_items(unique_rows)
        else:
            self.repo.replace_document_items(course_id, document_id, unique_rows)
        result.saved = len(unique_rows)
        return result

    async def _generate_and_verify(
        self, order: ChunkWorkOrder, chunk, stem_patterns, result: QuizGenerationResult
    ) -> list[GeneratedItem]:
        # LLM 응답 1회 실패(파싱 불가·빈 응답)는 "만들 문항 없음"과 다르다 —
        # 조각 단위 1회 재시도 후에도 비면 리포트에 남긴다 (QUIZ_TUNING §4).
        prompt = build_generation_prompt(order, chunk, stem_patterns)
        items: list[GeneratedItem] = []
        for attempt in range(2):
            # 모델 명시 + json_mode: pro3는 자유 출력에서 배열 대신 객체를
            # 이어붙여 답한다(QUIZ_TUNING §12) — response_format=json_object로
            # 원천 고정하고 프롬프트는 {"items":[...]} 래퍼를 요구한다.
            raw = await self.llm.generate(
                prompt, model=settings.QUIZ_CHAT_MODEL, json_mode=True
            )
            items = generation.parse_generation_response(raw)
            if items:
                break
            logger.warning(
                "조각 #%s 생성 응답에서 문항 0개 (시도 %d/2)", chunk.index, attempt + 1
            )
        if not items and order.concept_plans:
            result.discarded.append(
                f"조각 #{chunk.index}: 생성 응답 파싱 실패 — 재시도 후에도 문항 0개"
            )
            return []

        # quiz 고유 사전 검사: cloze 조립(코드 생성) → 근거 번호 실존 → 후보 이탈 차단
        checked: list[GeneratedItem] = []
        for item in items:
            reason = None
            if item.type == "cloze":
                reason = generation.build_cloze_segments(item, chunk)
            reason = (
                reason
                or generation.evidence_ids_reason(item, chunk)
                or generation.evidence_scope_reason(item, order)
            )
            if reason:
                result.discarded.append(f"{item.concept}/{item.type}: {reason}")
                result.discarded_items.append(
                    {"concept": item.concept, "type": item.type, "reason": reason, "data": item.data}
                )
            else:
                checked.append(item)

        # core 공통 검증기: 기계 → 심판 → 풀이 왕복 → 불합격 수정 1회 → 재검사.
        # 학습 페이지(JIT·형성평가) 생성도 같은 validate_items를 쓰게 된다.
        candidates = [
            CandidateItem(
                type=item.type,
                data=item.data,
                evidence_text=generation.evidence_text(item, chunk),
            )
            for item in checked
        ]
        # 배심원단: 1차 심판·풀이 = 생성 모델(Solar), 2차 = verify_llm(EXAONE).
        # 어느 한쪽이 잡으면 탈락, 2차 판독 불가는 기권. 수정은 생성 모델.
        verdicts = await validate_items(
            candidates,
            self.llm,
            self.quality_config,
            revise_llm=self.llm,
            second_llm=self.verify_llm,
        )

        passed: list[GeneratedItem] = []
        for item, verdict in zip(checked, verdicts):
            if verdict.ok:
                item.data = verdict.item.data  # polish·수정 반영본
                generation.augment_notations(item, chunk)  # 한/영 병기 인정 표기 보강
                passed.append(item)
            else:
                result.discarded.append(
                    f"{item.concept}/{item.type}: [{verdict.stage}] {verdict.reason}"
                )
                result.discarded_items.append(
                    {
                        "concept": item.concept,
                        "type": item.type,
                        "reason": f"[{verdict.stage}] {verdict.reason}",
                        "data": verdict.item.data,  # 수정 루프를 거쳤다면 최종본
                    }
                )
        return passed

    # ── 서빙 (LLM 없음) ──────────────────────────────────

    def bank_summary(
        self, course_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> list[QuizBankSummary]:
        rows = self.repo.toc_summary(course_id)
        by_doc: dict[uuid.UUID, list[TocSummary]] = {}
        for document_id, toc_index, toc_title, count in rows:
            by_doc.setdefault(document_id, []).append(
                TocSummary(toc_index=toc_index, title=toc_title or "", item_count=count)
            )

        # 학습함 라벨 — 사용자별 진도에서 단원 제목 매칭 (실패 시 빈 집합)
        from app.features.quiz import bridge as _bridge

        for doc_id, tocs in by_doc.items():
            if user_id is None:
                break
            studied = _bridge.studied_toc_titles(self.repo.db, doc_id, user_id)
            if not studied:
                continue
            for t in tocs:
                if t.title.strip() in studied:
                    t.studied = True

        return [
            QuizBankSummary(
                course_id=str(course_id),
                document_id=str(doc_id),
                tocs=tocs,
                total=sum(t.item_count for t in tocs),
            )
            for doc_id, tocs in by_doc.items()
        ]

    def start_session(
        self,
        course_id: uuid.UUID,
        document_id: uuid.UUID,
        toc_indexes: list[int],
        count: int,
        exclude_ids: list[uuid.UUID] | None = None,
    ) -> SessionResponse:
        items, recycled = self.repo.sample_items(
            course_id, document_id, toc_indexes, count, exclude_ids
        )
        return SessionResponse(
            items=[
                SessionItem(
                    id=str(i.id),
                    toc_index=i.toc_index,
                    type=i.type,
                    data=serving.strip_answers(i.type, i.data),
                )
                for i in items
            ],
            recycled=recycled,
        )

    def submit_attempt(
        self, item_id: uuid.UUID, user_input, user_id: uuid.UUID | None = None
    ) -> AttemptResponse | None:
        item = self.repo.get_item(item_id)
        if item is None:
            return None
        correct = grading.grade(item.type, item.data, user_input)
        self.repo.record_attempt(item.id, correct, user_input, user_id)
        return AttemptResponse(
            correct=correct,
            answer=grading.answer_payload(item.type, item.data),
            explanation=grading.chosen_explanation(item.type, item.data, user_input, correct),
            evidence=item.evidence,
        )
