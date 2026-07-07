"""[3.Service] 정밀 진단 오케스트레이션.

명세 충실 구현:
  - 절(Concept) 단위 추적.
  - 세션 시작 시 모든 개념 문항을 배치 생성(비용 절감) → 풀에서 꺼내 사용.
  - 각 개념의 strength이 경계(>=HIGH / <=LOW)에 닿을 때까지 반복, 닿으면 확정.
  - 모든 개념이 확정되면 세션 종료. (피로도 무시 / 정확도 올인)
"""
import logging
import re
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.diagnostic import bkt, grading
from app.features.diagnostic.quiz_coerce import coerce_quiz_draft
from app.features.diagnostic.models import DiagnosticQuestion, DiagnosticSession
from app.features.diagnostic.repository import DiagnosticRepository
from app.features.learning.models import ConceptMastery
from app.features.diagnostic.schemas import (
    QUIZ_ADAPTER,
    AnswerResult,
    BatchQuizResponse,
    ClozeDraft,
    InverseDraft,
    JudgeVerdict,
    MasteryOut,
    McqDraft,
    Progress,
    QuestionOut,
    QuizDraft,
    SessionState,
)
from app.features.seed.models import Concept

_log = logging.getLogger("uvicorn.error")

_QUIZ_SYSTEM = (
    "너는 특정 개념의 숙지 여부를 변별하는 진단 문항 출제기다. "
    "개념 특성에 맞는 최적의 문항 유형을 스스로 고른다. "
    "출력은 지정한 JSON 스키마만 따른다. 사족/마크다운 펜스 금지."
)

_BATCH_QUIZ_SYSTEM = (
    "너는 여러 개념에 대한 진단 문항을 한 번에 출제하는 출제기다. "
    "각 개념마다 지정된 개수의 문항을 다양한 유형으로 만든다. "
    "concept_name은 입력 목록과 정확히 일치해야 한다. "
    "출력은 지정한 JSON 스키마만 따른다. 사족/마크다운 펜스 금지."
)

_JUDGE_SYSTEM = (
    "너는 엄정한 채점관이다. 학습자 답이 모범답안과 '의미상' 일치하는지만 판정한다. "
    "출력은 JSON만."
)

_VERIFY_SYSTEM = (
    "너는 진단 문항 검수자다. 각 문항의 정답이 실제로 옳은지만 검사한다. "
    "출력은 지정한 JSON 스키마만 따른다."
)


def _verify_prompt(drafts: list) -> str:
    """생성 문항 셀프체크 프롬프트 (ISSUE-016 ① — mcq 수학 오류 차단).

    "훑고 판정"은 오류를 놓친다(실측: 오답 mcq 통과). 문항마다 자기 답을
    '먼저 도출해 적게' 강제하고 마킹과 비교시키는 구조화 검증.
    """
    lines = [
        "아래 진단 문항들을 검수하라. 각 문항마다:\n",
        "1. 출제 정보(answer_index/expected_answer)를 보지 말고 문제를 직접 풀어 "
        "my_answer에 너의 정답을 적어라. 수학 문항은 계산을 거친 최종값만. "
        "mcq는 보기 문구와 같은 형식으로 적어라 (예: 'y = 3x - 1').\n",
        "2. cloze/inverse: expected_answer가 my_answer와 의미상 일치하면 "
        "valid=true, 아니면 false. mcq의 valid는 항상 true로 두라 "
        "(mcq 대조는 시스템이 수행한다).\n",
        '출력 JSON: {"reviews": [{"i": 문항번호, "my_answer": str, "valid": bool}, ...]} '
        "— 모든 문항에 대해 하나씩.\n\n",
    ]
    for i, (_concept, d) in enumerate(drafts):
        lines.append(f"[{i}] ({d.qtype}) {d.question}\n")
        options = getattr(d, "options", None)
        if options is not None:
            lines.append(
                f"    options={options}, answer_index={getattr(d, 'answer_index', None)}\n"
            )
        else:
            lines.append(f"    expected_answer={getattr(d, 'expected_answer', '')}\n")
    return "".join(lines)


# 문항 근거로 주입하는 교재 원문 발췌 상한 (프롬프트 폭주 방지).
_EXCERPT_MAX_CHARS = 1500

# ── 해설 정리 (ISSUE-016 ②) ─────────────────────────────────────────
_EXPLANATION_MAX_CHARS = 350
# 추론 모델의 자기교정 독백이 해설에 새는 신호 — 마커부터 잘라낸다
# (실측 session 21: "다시 계산: … 문제 오류 가능성 …" 수백 자 노출).
_MONOLOGUE_MARKERS = ("다시 계산", "다시 확인", "재검토", "문제 오류", "옵션에 없")
_INTERNAL_REF_RE = re.compile(r"원문\s*\d+")


def _norm_answer(text: str) -> str:
    """mcq 답 대조용 정규화: 공백 제거 + 소문자."""
    return re.sub(r"\s+", "", text).lower()


def _answers_match(a: str, b: str) -> bool:
    """정규화된 두 답이 같은가 — 표기 여유(y= 접두 유무 등)는 포함 관계로 흡수."""
    if a == b:
        return True
    return len(a) >= 3 and len(b) >= 3 and (a in b or b in a)


def _clean_explanation(text: str | None) -> str:
    """해설 후처리: 내부 참조 치환 + 자기교정 독백 컷 + 길이 상한."""
    cleaned = _INTERNAL_REF_RE.sub("교재", text or "")
    positions = [cleaned.find(m) for m in _MONOLOGUE_MARKERS if m in cleaned]
    if positions:
        cleaned = cleaned[: min(positions)].rstrip(" ,.;:·—-")
    return cleaned[:_EXPLANATION_MAX_CHARS].strip()


def _quiz_prompt(concept: Concept, excerpt: str | None = None) -> str:
    grounding = (
        "\n\n=== 교재 원문 발췌 (이 개념의 출처) ===\n"
        f"{excerpt[:_EXCERPT_MAX_CHARS]}\n"
        "=== 발췌 끝 ===\n"
        "규칙: 문항·정답·해설은 위 원문 내용에 근거할 것. "
        "원문과 어긋나는 사실을 지어내지 말 것.\n"
        if excerpt
        else ""
    )
    return (
        f"개념 '{concept.name}'의 숙지 여부를 가장 잘 변별하는 진단 문항 1개를 한국어로 출제하라.\n"
        f"개념 설명: {concept.description}\n"
        f"{grounding}\n"
        "유형(qtype) 선택:\n"
        '- "mcq": 4지선다 — 보기는 options 배열에 4개. question 본문에 1.2.3.4. 목록 넣지 말 것.\n'
        '- "cloze": 빈칸 인출 — ____ 포함, 번호 선택지 금지.\n'
        '- "inverse": 역질문 자유 서술 — 4지선다·번호 목록 금지. (4지선다가 필요하면 mcq 사용)\n\n'
        "유형별 JSON:\n"
        '- mcq: {"qtype":"mcq","question":str,"options":[str×4],"answer_index":0~3,"explanation":str}\n'
        '- cloze: {"qtype":"cloze","question":"... ____ ...","expected_answer":str,'
        '"acceptable_answers":[str,...],"explanation":str}\n'
        '- inverse: {"qtype":"inverse","question":str,"expected_answer":str,"explanation":str}\n\n'
        "규칙: 정답 노출 금지. 4지선다는 반드시 mcq + options 배열. "
        "explanation은 정답 근거 1~2문장만 — 계산 재검토·자기 교정 과정·"
        "'원문 N' 같은 내부 참조 금지."
    )


def _batch_quiz_prompt(
    concepts: list[Concept],
    per_concept: int,
    excerpts: dict[uuid.UUID, str] | None = None,
) -> str:
    excerpts = excerpts or {}
    lines = [
        f"아래 {len(concepts)}개 개념 각각에 대해 진단 문항 {per_concept}개씩 한국어로 출제하라.\n",
        f'출력 JSON: {{"concepts":[{{"concept_name":str,"items":[문항,...]}}]}}\n',
        f"각 concept_name은 아래 목록과 정확히 일치해야 한다. items는 정확히 {per_concept}개.\n",
        "문항 유형: mcq / cloze / inverse. 4지선다는 반드시 mcq(options 배열), "
        "inverse/cloze에 1.2.3.4. 번호 목록 금지.\n",
        "유형별 items 원소:\n",
        '- mcq: {"qtype":"mcq","question":str,"options":[str×4],"answer_index":0~3,"explanation":str}\n',
        '- cloze: {"qtype":"cloze","question":"... ____ ...","expected_answer":str,'
        '"acceptable_answers":[str,...],"explanation":str}\n',
        '- inverse: {"qtype":"inverse","question":str,"expected_answer":str,"explanation":str}\n\n',
    ]
    # 같은 청크를 공유하는 개념이 많으므로(섹션 대표+하위) 원문은 한 번만 싣고
    # 개념 줄에서 태그로 참조 — 프롬프트 중복 방지.
    ref_of: dict[uuid.UUID, int] = {}  # chunk_id → 원문 번호
    for c in concepts:
        cid = c.source_chunk_id
        if cid is not None and cid in excerpts and cid not in ref_of:
            ref_of[cid] = len(ref_of) + 1
    if ref_of:
        lines.append("=== 교재 원문 발췌 ===\n")
        for cid, n in ref_of.items():
            lines.append(f"[원문 {n}]\n{excerpts[cid][:_EXCERPT_MAX_CHARS]}\n\n")
        lines.append(
            "규칙: 원문 태그가 붙은 개념의 문항·정답·해설은 해당 원문에 근거할 것. "
            "원문과 어긋나는 사실 금지.\n\n"
        )
    lines.append("개념 목록:\n")
    for c in concepts:
        tag = ""
        if c.source_chunk_id in ref_of:
            tag = f" (원문 {ref_of[c.source_chunk_id]})"
        lines.append(f'- concept_name="{c.name}"{tag}: {c.description}\n')
    lines.append(
        "\n규칙: 정답 노출 금지. 4지선다는 mcq + options 배열. "
        "explanation은 정답 근거 1~2문장만 — 계산 재검토·자기 교정 과정·"
        "'원문 N' 같은 내부 참조 금지."
    )
    return "".join(lines)


def _judge_prompt(question: str, expected: str, answer: str) -> str:
    return (
        f"문항: {question}\n"
        f"모범답안: {expected}\n"
        f"학습자 답: {answer}\n\n"
        "의미가 본질적으로 일치하면 correct=true. 표현/어순/사소한 오타 차이는 허용. "
        "핵심 개념이 틀리거나 비어 있으면 false.\n"
        'JSON: {"correct": true|false, "rationale": str}'
    )


class DiagnosticService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DiagnosticRepository(db)

    def _params(self, qtype: str) -> bkt.BKTParams:
        guess = {
            "mcq": settings.BKT_GUESS_MCQ,
            "cloze": settings.BKT_GUESS_CLOZE,
            "inverse": settings.BKT_GUESS_INVERSE,
        }.get(qtype, settings.BKT_P_GUESS)
        return bkt.BKTParams(
            p_init=settings.BKT_P_INIT,
            p_transit=settings.BKT_P_TRANSIT,
            p_slip=settings.BKT_P_SLIP,
            p_guess=guess,
        )

    # ── 공개 API ──────────────────────────────────────────────
    async def start(self, course_id: uuid.UUID) -> SessionState:
        course = self.repo.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")

        concepts = self.repo.list_concepts(course_id)
        if not concepts:
            raise HTTPException(
                status_code=400,
                detail="진단할 개념이 없습니다. 먼저 자료를 섭취(ingest)하세요.",
            )

        session = self.repo.create_session(course_id=course_id)
        self.repo.set_enrollment_diag_status(
            user_id=course.user_id, course_id=course_id, status="in_progress"
        )
        concept_ids = [c.id for c in concepts]

        if settings.BKT_GATED_MODE:
            # 메인(최상위) = 누구의 선수(prerequisite)도, 섹션 하위(contains)도
            # 아닌 개념. 나머지는 잠금 — 섹션 계층 문서에선 섹션 노드만 메인이 된다.
            sub_ids = self.repo.get_all_sub_ids(concept_ids)
            main_concepts = [c for c in concepts if c.id not in sub_ids]
            # 진단 스코핑(회의 2026-07-05, parsing 리뷰 대상): 초반 메인 +
            # 선수 방향 기반지식만 타겟. 타겟 외 개념은 전부 잠금(출제 제외)
            # — mastery는 사전값/전파 로직 그대로 둔다.
            targets = self._select_diag_targets(
                main_concepts, {c.id: c for c in concepts}
            )
            target_ids = {c.id for c in targets}
            locked_ids = {cid for cid in concept_ids if cid not in target_ids}
            self.repo.create_masteries(
                user_id=course.user_id,
                session_id=session.id,
                concept_ids=concept_ids,
                strength_init=settings.BKT_P_INIT,
                locked_ids=locked_ids,
            )
            # 비용 최소화: 시작 시엔 타겟 문항만 생성. 하위는 오답 시 지연 생성.
            await self._ensure_questions(session.id, targets)
        else:
            self.repo.create_masteries(
                user_id=course.user_id,
                session_id=session.id,
                concept_ids=concept_ids,
                strength_init=settings.BKT_P_INIT,
            )
            await self._ensure_questions(session.id, concepts)

        self.db.flush()
        return await self._build_state(session)

    async def get_state(self, session_id: uuid.UUID) -> SessionState:
        session = self._require_session(session_id)
        return await self._build_state(session)

    async def answer(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        *,
        selected_index: int | None,
        answer_text: str | None,
    ) -> AnswerResult:
        session = self._require_session(session_id)
        question = self.repo.get_question(question_id)
        if question is None or question.session_id != session_id:
            raise HTTPException(status_code=404, detail="문항을 찾을 수 없습니다.")
        if question.answered:
            raise HTTPException(status_code=409, detail="이미 채점된 문항입니다.")

        is_correct = await self._grade(question, selected_index, answer_text)

        question.answered = True
        question.selected_index = selected_index
        question.answer_text = answer_text
        question.is_correct = is_correct

        mastery = self.repo.get_mastery(
            session_id=session_id, concept_id=question.concept_id
        )
        if mastery is None:  # 방어적: 정상 흐름에선 발생하지 않음
            raise HTTPException(status_code=500, detail="숙련도 상태가 없습니다.")

        mastery.strength = bkt.update(
            mastery.strength, correct=is_correct, params=self._params(question.qtype)
        )
        mastery.answered_count += 1

        course = self.repo.get_course(session.course_id)
        if course is not None:
            self.repo.increment_diag_q_count(user_id=course.user_id, course_id=course.id)

        concepts = {c.id: c for c in self.repo.list_concepts(session.course_id)}

        if settings.BKT_GATED_MODE:
            await self._gate_after_answer(
                session_id=session_id,
                concept_id=question.concept_id,
                mastery=mastery,
                correct=is_correct,
                concepts=concepts,
            )
        else:
            if bkt.is_resolved(
                mastery.strength,
                high=settings.BKT_RESOLVE_HIGH,
                low=settings.BKT_RESOLVE_LOW,
            ) or mastery.answered_count >= settings.BKT_MAX_QUESTIONS_PER_CONCEPT:
                mastery.resolved = True
            self.db.flush()
            self._propagate(
                session_id=session_id,
                concept_id=question.concept_id,
                updated_strength=mastery.strength,
                correct=is_correct,
            )

        next_q = await self._advance(session, concepts)
        masteries = self.repo.list_masteries(session_id)
        progress = self._progress(masteries)
        self.db.commit()

        return AnswerResult(
            is_correct=is_correct,
            correct_index=question.answer_index if question.qtype == "mcq" else None,
            correct_answer=question.expected_answer if question.qtype != "mcq" else None,
            explanation=question.explanation,
            mastery=self._mastery_out(mastery, concepts[question.concept_id].name),
            done=next_q is None,
            progress=progress,
            next_question=self._question_out(next_q, concepts) if next_q else None,
        )

    # ── 그래프 전파 ───────────────────────────────────────────
    def _propagate(
        self,
        *,
        session_id: uuid.UUID,
        concept_id: uuid.UUID,
        updated_strength: float,
        correct: bool,
        _visited: set[uuid.UUID] | None = None,
        _hop: int = 1,
    ) -> None:
        """정/오답에서 선수/후속 개념으로 strength을 전파한다 (BFS, 최대 2-hop).

        정답 → 선수(prerequisites) 상향 전파:
          "이걸 맞혔다면 선수도 알 가능성 ↑"
        오답 → 후속(dependents) 하향 전파:
          "이걸 틀렸다면 이를 전제로 하는 개념도 모를 가능성 ↑"
        """
        if _visited is None:
            _visited = {concept_id}

        decay = settings.BKT_PROPAGATION_DECAY
        max_hop = 2  # 2-hop 이상은 신호가 너무 약해 효과 미미

        if _hop > max_hop:
            return

        neighbor_ids = (
            self.repo.get_prerequisite_ids(concept_id)
            if correct
            else self.repo.get_dependent_ids(concept_id)
        )

        for nid in neighbor_ids:
            if nid in _visited:
                continue
            _visited.add(nid)

            neighbor = self.repo.get_mastery(session_id=session_id, concept_id=nid)
            if neighbor is None or neighbor.resolved:
                continue

            old_p = neighbor.strength
            if correct:
                new_p = bkt.propagate_up(
                    answered_p=updated_strength, prereq_p=old_p, decay=decay, hop=_hop
                )
            else:
                new_p = bkt.propagate_down(
                    answered_p=updated_strength, dependent_p=old_p, decay=decay, hop=_hop
                )

            new_p = max(0.01, min(0.99, new_p))
            neighbor.strength = new_p

            # 전파로 확정 경계를 넘었고 최소 1문항 이상 직접 풀었으면 확정
            if (
                bkt.is_resolved(
                    new_p,
                    high=settings.BKT_RESOLVE_HIGH,
                    low=settings.BKT_RESOLVE_LOW,
                )
                and neighbor.answered_count >= settings.BKT_PROPAGATION_MIN_QUESTIONS
            ):
                neighbor.resolved = True

            self.db.flush()

            # 재귀적으로 다음 hop 전파
            self._propagate(
                session_id=session_id,
                concept_id=nid,
                updated_strength=new_p,
                correct=correct,
                _visited=_visited,
                _hop=_hop + 1,
            )

    # ── 채점 ──────────────────────────────────────────────────
    async def _grade(
        self,
        question: DiagnosticQuestion,
        selected_index: int | None,
        answer_text: str | None,
    ) -> bool:
        if question.qtype == "mcq":
            if selected_index is None:
                raise HTTPException(status_code=400, detail="객관식: selected_index 필요.")
            return selected_index == question.answer_index

        text = (answer_text or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="인출형: answer_text 필요.")
        expected = question.expected_answer or ""

        if question.qtype == "cloze" and grading.exact_match(
            text, expected, question.acceptable_answers
        ):
            return True  # 정규화 정확매칭 빠른 경로
        return (await self._judge(question.question, expected, text)).correct

    async def _judge(self, question: str, expected: str, answer: str) -> JudgeVerdict:
        raw = await solar_client.generate_json(
            _judge_prompt(question, expected, answer), system=_JUDGE_SYSTEM
        )
        try:
            return JudgeVerdict.model_validate(raw)
        except ValidationError:
            # 심판 출력이 깨지면 보수적으로 오답 처리(정확도 우선).
            return JudgeVerdict(correct=False, rationale="채점 결과 파싱 실패")

    # ── 내부 로직 ─────────────────────────────────────────────
    def _require_session(self, session_id: uuid.UUID) -> DiagnosticSession:
        session = self.repo.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        return session

    async def _build_state(self, session: DiagnosticSession) -> SessionState:
        concepts = {c.id: c for c in self.repo.list_concepts(session.course_id)}
        question = await self._advance(session, concepts)
        masteries = self.repo.list_masteries(session.id)
        self.db.commit()
        return SessionState(
            session_id=session.id,
            status=session.status,
            done=question is None,
            progress=self._progress(masteries),
            question=self._question_out(question, concepts) if question else None,
            masteries=[
                self._mastery_out(m, concepts[m.concept_id].name) for m in masteries
            ],
        )

    async def _advance(
        self, session: DiagnosticSession, concepts: dict[uuid.UUID, Concept]
    ) -> DiagnosticQuestion | None:
        """활성 문항 → 풀에서 타겟 개념 문항 꺼내기. 타겟 없으면 종료."""
        active = self.repo.get_active_question(session.id)
        if active is not None:
            return active

        # 진단 스코핑(회의 2026-07-05, parsing 리뷰 대상): 세션 총 문항 하드캡.
        # 캡 도달 시 새 문항을 내지 않고 종료 — 남은 미확정 개념은 이미 반영된
        # 그래프 전파/사전값(P_INIT)으로 마무리한다 (억지 확정 없음).
        if (
            self.repo.count_answered_questions(session.id)
            >= settings.DIAG_MAX_TOTAL_QUESTIONS
        ):
            if session.status != "completed":
                self.repo.complete_session(session)
            return None

        sole = self.repo.get_sole_unanswered(session.id)
        if sole is not None and not sole.is_active:
            sole.is_active = True
            self.db.flush()
            return sole

        target = self._pick_target(self.repo.list_masteries(session.id))
        if target is None:
            if session.status != "completed":
                self.repo.complete_session(session)
            return None

        pool_q = self.repo.get_pool_question(
            session_id=session.id, concept_id=target.concept_id
        )
        if pool_q is None:
            target.resolved = True
            self.db.flush()
            return await self._advance(session, concepts)

        pool_q.is_active = True
        self.db.flush()
        return pool_q

    def _select_diag_targets(
        self,
        main_concepts: list[Concept],
        concepts_by_id: dict[uuid.UUID, Concept],
    ) -> list[Concept]:
        """진단 시작 타겟 선정 — 회의 결정(2026-07-05) 구현 제안, parsing 리뷰 대상.

        진단의 목적 = 시작점(floor) 찾기 + 학습 전 기반지식 결손 확인:
          - 커리큘럼 진행선 '앞부분' 메인 개념 순서대로 (뒷부분은 출제 안 함 —
            시작점 판정에 불필요, ceiling은 기본 문서 끝)
          - + 그 메인들의 선수 방향(depth_level 큰 쪽 = 더 기초) 개념 소수:
            "이 문서를 배우기 전에 알아야 할 기반지식" 프록시
        메인 수가 상한 이하인 소형 코스는 전원 출제(기존 동작으로 퇴화).
        """
        cap = min(settings.DIAG_MAX_MAIN_CONCEPTS, settings.DIAG_MAX_TOTAL_QUESTIONS)
        if len(main_concepts) <= cap:
            return list(main_concepts)

        probe_quota = min(settings.DIAG_PREREQ_PROBE_COUNT, max(cap - 1, 0))
        front_quota = cap - probe_quota
        front_mains = main_concepts[:front_quota]
        seen = {c.id for c in front_mains}

        # 선수 방향 후보: 초반 메인의 직접 선수(prerequisite).
        # depth_level 큰(더 기초) 순으로 우선 — 기반지식 결손을 먼저 찌른다.
        probes: list[Concept] = []
        for main in front_mains:
            for pid in self.repo.get_prerequisite_ids(main.id):
                candidate = concepts_by_id.get(pid)
                if candidate is None or candidate.id in seen:
                    continue
                seen.add(candidate.id)
                probes.append(candidate)
        probes.sort(key=lambda c: -(c.depth_level or 0))
        targets = front_mains + probes[:probe_quota]

        # 선수 엣지가 부족하면 커리큘럼 초반 메인으로 상한까지 채운다.
        for c in main_concepts[front_quota:]:
            if len(targets) >= cap:
                break
            if c.id not in seen:
                seen.add(c.id)
                targets.append(c)
        return targets

    def _pick_target(self, masteries: list[ConceptMastery]) -> ConceptMastery | None:
        """미확정·미잠금 개념 중 불확실성(p≈0.5)이 가장 큰 노드.

        잠긴(locked) 하위 개념은 상위 오답으로 해제되기 전까지 출제 대상에서 제외된다.
        """
        candidates = [m for m in masteries if not m.resolved and not m.locked]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda m: (bkt.uncertainty(m.strength), -m.answered_count),
        )

    # ── 게이티드 라우팅 (메인 우선 → 오답 시 하위 파고들기) ────────
    async def _gate_after_answer(
        self,
        *,
        session_id: uuid.UUID,
        concept_id: uuid.UUID,
        mastery: ConceptMastery,
        correct: bool,
        concepts: dict[uuid.UUID, Concept],
    ) -> None:
        """채점 결과(=LLM 판단)로 라우팅. 한 문항으로 해당 개념을 판정한다.

        정답 → 이 개념의 하위(선수 + 섹션 하위) 전체를 '안다'고 보고 자동 확정.
        오답 → 메인(최상위)일 때만 한 단계 내려간다:
               - 직접 선수(prerequisite)는 전부 잠금 해제
               - 섹션 하위(contains)는 대표 N개만 잠금 해제 출제, 나머지는
                 오답 신호를 하향 전파만 받고 잠금 유지 (ISSUE-009 — 학습 중
                 확인 루프가 나중에 정밀화)
               이미 하위 단계인 개념은 '최대한 한 단계' 원칙에 따라 더 내려가지 않음.
        """
        # 게이티드 모드는 개념당 N문항(기본 1)으로 판정 → 문항 수 최소화.
        if mastery.answered_count >= settings.BKT_GATED_QUESTIONS_PER_CONCEPT:
            mastery.resolved = True
        self.db.flush()

        if correct:
            self._mark_subtree_known(session_id, concept_id)
            return

        # 오답: 메인(누구의 선수도, 어느 섹션의 하위도 아님)일 때만 내려간다.
        is_main = not self.repo.get_dependent_ids(concept_id) and not self.repo.get_container_ids(concept_id)
        if not is_main:
            return

        prereq_ids = self.repo.get_prerequisite_ids(concept_id)
        child_ids = self.repo.get_contains_child_ids(concept_id)
        sample_ids = child_ids[: settings.BKT_GATED_CONTAINS_SAMPLE]

        # 진단 스코핑(회의 2026-07-05, parsing 리뷰 대상): 총 문항 캡의 잔여분
        # 만큼만 하위를 잠금 해제 — 어차피 못 물어볼 문항은 생성(LLM 비용)도
        # 하지 않는다. 해제되지 못한 하위의 mastery는 기존 하향 전파/사전값
        # 로직 그대로.
        remaining_budget = max(
            0,
            settings.DIAG_MAX_TOTAL_QUESTIONS
            - self.repo.count_answered_questions(session_id),
        )
        unlock_ids = (prereq_ids + sample_ids)[:remaining_budget]
        unlocked = set(unlock_ids)
        # 출제되지 않는 섹션 하위(대표 샘플 탈락 + 캡 탈락) → 하향 전파만.
        rest_ids = [cid for cid in child_ids if cid not in unlocked]

        if not unlock_ids and not rest_ids:
            return

        for uid in unlock_ids:
            self.repo.unlock_mastery(session_id=session_id, concept_id=uid)

        # 샘플에서 빠진 섹션 하위: 출제 없이 오답 신호만 하향 반영(거친 씨앗).
        # 잠금 유지 → 학습 중 확인 루프(ISSUE-005)가 이후 정밀화한다.
        for rid in rest_ids:
            m = self.repo.get_mastery(session_id=session_id, concept_id=rid)
            if m is None or m.resolved:
                continue
            m.strength = max(
                0.01,
                min(
                    0.99,
                    bkt.propagate_down(
                        answered_p=mastery.strength,
                        dependent_p=m.strength,
                        decay=settings.BKT_PROPAGATION_DECAY,
                        hop=1,
                    ),
                ),
            )
        self.db.flush()

        # 잠금 해제된 하위 개념 문항을 지연 생성 (필요한 가지에만 비용 발생).
        unlock_concepts = [concepts[uid] for uid in unlock_ids if uid in concepts]
        await self._ensure_questions(session_id, unlock_concepts)

    def _mark_subtree_known(
        self, session_id: uuid.UUID, concept_id: uuid.UUID
    ) -> None:
        """정답이면 그 개념의 하위 전체(선수 + 섹션 하위)를 '안다'고 보고 확정."""
        visited: set[uuid.UUID] = {concept_id}
        frontier = self.repo.get_prerequisite_ids(concept_id) + self.repo.get_contains_child_ids(concept_id)
        while frontier:
            pid = frontier.pop()
            if pid in visited:
                continue
            visited.add(pid)

            m = self.repo.get_mastery(session_id=session_id, concept_id=pid)
            if m is not None and not m.resolved:
                m.strength = max(m.strength, settings.BKT_RESOLVE_HIGH)
                m.resolved = True
                self.db.flush()

            frontier.extend(self.repo.get_prerequisite_ids(pid))
            frontier.extend(self.repo.get_contains_child_ids(pid))

    async def _ensure_questions(
        self, session_id: uuid.UUID, concepts: list[Concept]
    ) -> None:
        """주어진 개념들의 문항을 배치 생성해 풀에 저장. 이미 있는 개념은 건너뜀.

        시작 시엔 메인 개념만, 오답으로 하위가 잠금 해제될 때 그 하위만 호출 →
        실제로 필요한 개념만 생성해 토큰/비용을 최소화한다.
        """
        pending = [
            c
            for c in concepts
            if not self.repo.has_questions_for_concept(session_id, c.id)
        ]
        if not pending:
            return

        pool_size = settings.BKT_POOL_SIZE_PER_CONCEPT
        chunk_size = settings.BKT_BATCH_CONCEPT_CHUNK
        name_to_concept = {c.name: c for c in pending}
        # 원문 근거 주입 (RAG): 개념의 출처 청크 원문을 문항 프롬프트에 싣는다.
        excerpts = self.repo.get_chunk_contents(
            {c.source_chunk_id for c in pending if c.source_chunk_id is not None}
        )

        async def generate_batch(chunk: list[Concept]) -> BatchQuizResponse:
            raw = await solar_client.generate_json(
                _batch_quiz_prompt(chunk, pool_size, excerpts),
                system=_BATCH_QUIZ_SYSTEM,
                timeout=240.0,
            )
            return BatchQuizResponse.model_validate(raw)

        for i in range(0, len(pending), chunk_size):
            chunk = pending[i : i + chunk_size]
            # LLM 출력 플레이크 1회 재시도 (추출 경로와 동일 패턴).
            # ValueError는 JSON 절단(JSONDecodeError 포함) — 실측: 스키마 오형
            # (ValidationError)과 응답 절단 두 유형 모두 발생.
            try:
                batch = await generate_batch(chunk)
            except (ValidationError, ValueError):
                _log.warning("배치 문항 생성 실패, 재시도: %d~", i)
                try:
                    batch = await generate_batch(chunk)
                except (ValidationError, ValueError) as exc:
                    raise HTTPException(
                        status_code=502,
                        detail=f"배치 문항 생성 실패: {exc}",
                    ) from exc

            drafts: list[tuple[Concept, QuizDraft]] = []
            for concept_set in batch.concepts:
                concept = name_to_concept.get(concept_set.concept_name)
                if concept is None:
                    continue
                for item in concept_set.items[:pool_size]:
                    drafts.append((concept, item))

            # 검증 패스 (ISSUE-016): 정답 오류 문항은 단건 재생성으로 교체.
            invalid = await self._verify_drafts(drafts) if drafts else set()
            regen: list[tuple[Concept, QuizDraft]] = []
            for j, (concept, item) in enumerate(drafts):
                if j not in invalid:
                    self._persist_draft(session_id, concept.id, item)
                    continue
                _log.info("문항 검증 불합격 → 재생성: %s", concept.name)
                try:
                    regen.append((concept, await self._generate_draft(concept)))
                except (ValidationError, ValueError):
                    _log.warning("재생성 실패 — 원본 문항 유지: %s", concept.name)
                    self._persist_draft(session_id, concept.id, item)
            if regen:
                # 재생성분도 1회 재검증 (실측: 미검증 재생성에서 오류 재유입).
                # 2회째도 불합격이면 로그 남기고 사용 — 무한 루프 방지.
                still = await self._verify_drafts(regen)
                for j, (concept, item) in enumerate(regen):
                    if j in still:
                        _log.warning("재생성 문항도 검증 불합격, 그대로 사용: %s", concept.name)
                    self._persist_draft(session_id, concept.id, item)

        # 누락 개념은 단건 생성으로 보충 (드문 경우)
        for concept in pending:
            if not self.repo.has_questions_for_concept(session_id, concept.id):
                await self._generate_question(session_id, concept)

    async def _verify_drafts(
        self, drafts: list[tuple[Concept, QuizDraft]]
    ) -> set[int]:
        """생성 문항 셀프체크 — 불합격 인덱스 집합. 검증 호출 실패는 비치명."""
        try:
            raw = await solar_client.generate_json(
                _verify_prompt(drafts), system=_VERIFY_SYSTEM, timeout=240.0
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("문항 검증 호출 실패 — 검증 생략: %s", exc)
            return set()
        invalid: set[int] = set()
        for review in raw.get("reviews") or []:
            if not isinstance(review, dict):
                continue
            i = review.get("i")
            if not (isinstance(i, int) and 0 <= i < len(drafts)):
                continue
            _concept, draft = drafts[i]
            options = getattr(draft, "options", None)
            if options:
                # mcq 대조는 코드가 한다 — 실측: 검수 LLM이 정답을 옳게
                # 계산해 놓고도 answer_index 비교에서 valid=true 오판.
                my = _norm_answer(str(review.get("my_answer") or ""))
                if not my:
                    continue
                matches = [
                    k for k, opt in enumerate(options)
                    if _answers_match(my, _norm_answer(str(opt)))
                ]
                if getattr(draft, "answer_index", None) in matches:
                    continue
                invalid.add(i)
                _log.info(
                    "문항 검증 불합격 [%d] mcq: 검수자 답=%r ↔ 마킹=%r",
                    i, review.get("my_answer"),
                    options[draft.answer_index] if 0 <= draft.answer_index < len(options) else None,
                )
            elif review.get("valid") is False:
                invalid.add(i)
                _log.info(
                    "문항 검증 불합격 [%d]: 검수자 답=%r", i, review.get("my_answer")
                )
        if invalid:
            _log.info("문항 검증: %d/%d 불합격", len(invalid), len(drafts))
        return invalid

    def _persist_draft(
        self, session_id: uuid.UUID, concept_id: uuid.UUID, draft: QuizDraft
    ) -> DiagnosticQuestion:
        draft = coerce_quiz_draft(draft)
        draft.explanation = _clean_explanation(draft.explanation)
        if isinstance(draft, McqDraft):
            return self.repo.create_question(
                session_id=session_id,
                concept_id=concept_id,
                qtype="mcq",
                question=draft.question,
                explanation=draft.explanation,
                options=draft.options,
                answer_index=draft.answer_index,
            )
        if isinstance(draft, ClozeDraft):
            return self.repo.create_question(
                session_id=session_id,
                concept_id=concept_id,
                qtype="cloze",
                question=draft.question,
                explanation=draft.explanation,
                expected_answer=draft.expected_answer,
                acceptable_answers=draft.acceptable_answers,
            )
        return self.repo.create_question(
            session_id=session_id,
            concept_id=concept_id,
            qtype="inverse",
            question=draft.question,
            explanation=draft.explanation,
            expected_answer=draft.expected_answer,
        )

    async def _generate_draft(self, concept: Concept) -> QuizDraft:
        """단건 문항 생성 (저장 없이 초안 반환 — 재생성·검증 경로용)."""
        excerpt = None
        if concept.source_chunk_id is not None:
            excerpt = self.repo.get_chunk_contents({concept.source_chunk_id}).get(
                concept.source_chunk_id
            )
        raw = await solar_client.generate_json(
            _quiz_prompt(concept, excerpt), system=_QUIZ_SYSTEM
        )
        return QUIZ_ADAPTER.validate_python(raw)

    async def _generate_question(
        self, session_id: uuid.UUID, concept: Concept
    ) -> DiagnosticQuestion:
        try:
            draft = await self._generate_draft(concept)
        except ValidationError as exc:
            raise HTTPException(
                status_code=502, detail=f"문항 생성 JSON 검증 실패: {exc}"
            ) from exc

        return self._persist_draft(session_id, concept.id, draft)

    @staticmethod
    def _progress(masteries: list[ConceptMastery]) -> Progress:
        return Progress(
            total=len(masteries),
            resolved=sum(1 for m in masteries if m.resolved),
        )

    @staticmethod
    def _question_out(
        q: DiagnosticQuestion, concepts: dict[uuid.UUID, Concept]
    ) -> QuestionOut:
        return QuestionOut(
            id=q.id,
            concept_id=q.concept_id,
            concept_name=concepts[q.concept_id].name,
            qtype=q.qtype,  # type: ignore[arg-type]
            question=q.question,
            options=list(q.options) if q.options else [],
        )

    @staticmethod
    def _mastery_out(m: ConceptMastery, concept_name: str) -> MasteryOut:
        return MasteryOut(
            concept_id=m.concept_id,
            concept_name=concept_name,
            strength=round(m.strength, 4),
            resolved=m.resolved,
            answered_count=m.answered_count,
        )
