"""[3.Service] 정밀 진단 오케스트레이션.

명세 충실 구현:
  - 절(Concept) 단위 추적.
  - 세션 시작 시 모든 개념 문항을 배치 생성(비용 절감) → 풀에서 꺼내 사용.
  - 각 개념의 strength이 경계(>=HIGH / <=LOW)에 닿을 때까지 반복, 닿으면 확정.
  - 모든 개념이 확정되면 세션 종료. (피로도 무시 / 정확도 올인)
"""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.diagnostic import bkt, grading
from app.features.diagnostic.quiz_coerce import coerce_quiz_draft
from app.features.diagnostic.models import (
    ConceptMastery,
    DiagnosticQuestion,
    DiagnosticSession,
)
from app.features.diagnostic.repository import DiagnosticRepository
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
from app.features.documents.models import Concept

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


def _quiz_prompt(concept: Concept) -> str:
    return (
        f"개념 '{concept.name}'의 숙지 여부를 가장 잘 변별하는 진단 문항 1개를 한국어로 출제하라.\n"
        f"개념 설명: {concept.description}\n\n"
        "유형(qtype) 선택:\n"
        '- "mcq": 4지선다 — 보기는 options 배열에 4개. question 본문에 1.2.3.4. 목록 넣지 말 것.\n'
        '- "cloze": 빈칸 인출 — ____ 포함, 번호 선택지 금지.\n'
        '- "inverse": 역질문 자유 서술 — 4지선다·번호 목록 금지. (4지선다가 필요하면 mcq 사용)\n\n'
        "유형별 JSON:\n"
        '- mcq: {"qtype":"mcq","question":str,"options":[str×4],"answer_index":0~3,"explanation":str}\n'
        '- cloze: {"qtype":"cloze","question":"... ____ ...","expected_answer":str,'
        '"acceptable_answers":[str,...],"explanation":str}\n'
        '- inverse: {"qtype":"inverse","question":str,"expected_answer":str,"explanation":str}\n\n'
        "규칙: 정답 노출 금지. 4지선다는 반드시 mcq + options 배열."
    )


def _batch_quiz_prompt(concepts: list[Concept], per_concept: int) -> str:
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
        "개념 목록:\n",
    ]
    for c in concepts:
        lines.append(f'- concept_name="{c.name}": {c.description}\n')
    lines.append("\n규칙: 정답 노출 금지. 4지선다는 mcq + options 배열.")
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
    async def start(self, course_id: int) -> SessionState:
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
            # 메인(최상위) 개념 = 누구의 선수지식도 아닌 개념. 나머지(하위)는 잠금.
            sub_ids = self.repo.get_all_prerequisite_target_ids(concept_ids)
            main_concepts = [c for c in concepts if c.id not in sub_ids]
            self.repo.create_masteries(
                session_id=session.id,
                concept_ids=concept_ids,
                strength_init=settings.BKT_P_INIT,
                locked_ids=sub_ids,
            )
            # 비용 최소화: 시작 시엔 메인 개념 문항만 생성. 하위는 오답 시 지연 생성.
            await self._ensure_questions(session.id, main_concepts)
        else:
            self.repo.create_masteries(
                session_id=session.id,
                concept_ids=concept_ids,
                strength_init=settings.BKT_P_INIT,
            )
            await self._ensure_questions(session.id, concepts)

        self.db.flush()
        return await self._build_state(session)

    async def get_state(self, session_id: int) -> SessionState:
        session = self._require_session(session_id)
        return await self._build_state(session)

    async def answer(
        self,
        session_id: int,
        question_id: int,
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
        session_id: int,
        concept_id: int,
        updated_strength: float,
        correct: bool,
        _visited: set[int] | None = None,
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
    def _require_session(self, session_id: int) -> DiagnosticSession:
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
        self, session: DiagnosticSession, concepts: dict[int, Concept]
    ) -> DiagnosticQuestion | None:
        """활성 문항 → 풀에서 타겟 개념 문항 꺼내기. 타겟 없으면 종료."""
        active = self.repo.get_active_question(session.id)
        if active is not None:
            return active

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
        session_id: int,
        concept_id: int,
        mastery: ConceptMastery,
        correct: bool,
        concepts: dict[int, Concept],
    ) -> None:
        """채점 결과(=LLM 판단)로 라우팅. 한 문항으로 해당 개념을 판정한다.

        정답 → 이 개념의 하위(선수) 전체를 '안다'고 보고 자동 확정(출제 생략).
        오답 → 메인(최상위)일 때만 직접 하위(선수)를 잠금 해제해 결손 확인.
               이미 하위 단계인 개념은 '최대한 한 단계' 원칙에 따라 더 내려가지 않음.
        """
        # 게이티드 모드는 개념당 N문항(기본 1)으로 판정 → 문항 수 최소화.
        if mastery.answered_count >= settings.BKT_GATED_QUESTIONS_PER_CONCEPT:
            mastery.resolved = True
        self.db.flush()

        if correct:
            self._mark_subtree_known(session_id, concept_id)
            return

        # 오답: 이 개념이 메인(누구의 선수도 아님)일 때만 한 단계 내려간다.
        is_main = not self.repo.get_dependent_ids(concept_id)
        if not is_main:
            return

        prereq_ids = self.repo.get_prerequisite_ids(concept_id)
        if not prereq_ids:
            return

        for pid in prereq_ids:
            self.repo.unlock_mastery(session_id=session_id, concept_id=pid)

        # 잠금 해제된 하위 개념 문항을 지연 생성 (필요한 가지에만 비용 발생).
        prereq_concepts = [concepts[pid] for pid in prereq_ids if pid in concepts]
        await self._ensure_questions(session_id, prereq_concepts)

    def _mark_subtree_known(self, session_id: int, concept_id: int) -> None:
        """정답이면 그 개념의 선수지식 전체를 '안다'고 보고 확정(출제 생략)."""
        visited: set[int] = {concept_id}
        frontier = list(self.repo.get_prerequisite_ids(concept_id))
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

    async def _ensure_questions(
        self, session_id: int, concepts: list[Concept]
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

        for i in range(0, len(pending), chunk_size):
            chunk = pending[i : i + chunk_size]
            raw = await solar_client.generate_json(
                _batch_quiz_prompt(chunk, pool_size),
                system=_BATCH_QUIZ_SYSTEM,
                timeout=240.0,
            )
            try:
                batch = BatchQuizResponse.model_validate(raw)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=502,
                    detail=f"배치 문항 생성 JSON 검증 실패: {exc}",
                ) from exc

            for concept_set in batch.concepts:
                concept = name_to_concept.get(concept_set.concept_name)
                if concept is None:
                    continue
                for item in concept_set.items[:pool_size]:
                    self._persist_draft(session_id, concept.id, item)

        # 누락 개념은 단건 생성으로 보충 (드문 경우)
        for concept in pending:
            if not self.repo.has_questions_for_concept(session_id, concept.id):
                await self._generate_question(session_id, concept)

    def _persist_draft(
        self, session_id: int, concept_id: int, draft: QuizDraft
    ) -> DiagnosticQuestion:
        draft = coerce_quiz_draft(draft)
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

    async def _generate_question(
        self, session_id: int, concept: Concept
    ) -> DiagnosticQuestion:
        raw = await solar_client.generate_json(
            _quiz_prompt(concept), system=_QUIZ_SYSTEM
        )
        try:
            draft = QUIZ_ADAPTER.validate_python(raw)
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
        q: DiagnosticQuestion, concepts: dict[int, Concept]
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
