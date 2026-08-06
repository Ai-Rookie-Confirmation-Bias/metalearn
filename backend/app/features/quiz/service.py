"""[3.Service] 문제 생성 배치 + 서빙 로직 (docs/QUIZ.md §1 파이프라인).

배치: 수신검증 → 선별 → 계획 → 조각별 생성(LLM) → core/quality 검증
      (기계검사 → 심판 → 풀이 왕복 → 불합격 수정 1회) → verified만 저장(전체 교체).
서빙: DB 조회만 — LLM 호출 없음.
"""
import logging
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


class QuizGenerationResult:
    def __init__(self, report: ParseReport) -> None:
        self.report = report
        self.saved = 0
        self.discarded: list[str] = []  # "개념/유형: [단계] 사유"


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
    ) -> QuizGenerationResult:
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

        rows: list[QuizItem] = []
        for order in orders:
            chunk = chunk_by_index[order.chunk_index]
            verified_items = await self._generate_and_verify(
                order, chunk, stem_patterns, result
            )
            for item in verified_items:
                rows.append(
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
                )

        self.repo.replace_document_items(course_id, document_id, rows)
        result.saved = len(rows)
        return result

    async def _generate_and_verify(
        self, order: ChunkWorkOrder, chunk, stem_patterns, result: QuizGenerationResult
    ) -> list[GeneratedItem]:
        # LLM 응답 1회 실패(파싱 불가·빈 응답)는 "만들 문항 없음"과 다르다 —
        # 조각 단위 1회 재시도 후에도 비면 리포트에 남긴다 (QUIZ_TUNING §4).
        prompt = build_generation_prompt(order, chunk, stem_patterns)
        items: list[GeneratedItem] = []
        for attempt in range(2):
            # ⚠️ 모델을 명시한다. 통합 전 이 호출은 solar 클라이언트가 하드코딩한
            #    solar-pro2로 나갔는데, 파싱 쪽 클라이언트로 합쳐지며 기본이
            #    solar-pro3가 됐고 **문항이 0개가 됐다** — pro3는 배열이 아니라
            #    객체를 이어붙여 답해서 parse_generation_response가 못 읽는다.
            #    config.QUIZ_CHAT_MODEL 주석에 실측을 남겼다.
            raw = await self.llm.generate(prompt, model=settings.QUIZ_CHAT_MODEL)
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

        # quiz 고유 사전 검사: 근거 문장 번호 실존 + 선별 후보 이탈 차단 (§9-①)
        checked: list[GeneratedItem] = []
        for item in items:
            reason = generation.evidence_ids_reason(
                item, chunk
            ) or generation.evidence_scope_reason(item, order)
            if reason:
                result.discarded.append(f"{item.concept}/{item.type}: {reason}")
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
                passed.append(item)
            else:
                result.discarded.append(
                    f"{item.concept}/{item.type}: [{verdict.stage}] {verdict.reason}"
                )
        return passed

    # ── 서빙 (LLM 없음) ──────────────────────────────────

    def bank_summary(self, course_id: uuid.UUID) -> list[QuizBankSummary]:
        rows = self.repo.toc_summary(course_id)
        by_doc: dict[uuid.UUID, list[TocSummary]] = {}
        for document_id, toc_index, toc_title, count in rows:
            by_doc.setdefault(document_id, []).append(
                TocSummary(toc_index=toc_index, title=toc_title or "", item_count=count)
            )
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
        self, course_id: uuid.UUID, document_id: uuid.UUID, toc_indexes: list[int], count: int
    ) -> SessionResponse:
        items = self.repo.sample_items(course_id, document_id, toc_indexes, count)
        return SessionResponse(
            items=[
                SessionItem(
                    id=str(i.id),
                    toc_index=i.toc_index,
                    type=i.type,
                    data=serving.strip_answers(i.type, i.data),
                )
                for i in items
            ]
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
