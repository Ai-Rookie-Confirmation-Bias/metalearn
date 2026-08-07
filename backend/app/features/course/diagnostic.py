"""24 진단 — **시험이 아니라 설정이다.**

한 번 앉아서 1분 30초. 끝나면 커리큘럼이 그 사람 것이 된다.

    ① 왜 배우나        goal · deadline_weeks   → 분량(plan)
    ② 분야 맞나        documents.field 확인    → 12.5의 유일한 검증 창구
    ③ 카드 4장         style                   → 설명 생성 프롬프트
    ④ 선수 체크        course_prereqs.known    → 보강 단원의 근거
    ⑤ 확인 문항        course_prereqs.verified → known이 정말인지

## 왜 체크리스트인가

문항 자동 생성이 못 쓸 수준이다(실측: 책 밖 1/6 · 책 안 1/4 — 정답 번호 오류,
정답 둘, 코드 없는 코드 문제). 그래서 **묻는 방식은 체크리스트**이고, 문항은
"안다"가 정말인지 재는 데만 쓴다. 오답만 생성하는 방식은 14/15로 쓸 만하다
(`prompts/probe.py` 참고).

## 왜 자기평가 진술문을 안 쓰나

"나는 비유로 설명하면 잘 이해한다" 같은 문항은 실측 4/6이었고, 무엇보다
**사람들이 자기 스타일을 잘 모른다.** 그래서 ③은 진술문이 아니라 같은 개념을
네 가지로 실제로 써 보여주고 고르게 한다.

⚠️ 스타일 맞춤에 **학습 효과 근거는 없다**(meshing hypothesis, Pashler 2008).
이건 성취가 아니라 **이탈**을 막는 장치다. 읽기 싫은 형식이면 안 읽는다.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.llm.solar import solar_client
from app.features.course.models import Course, CoursePrereq, PrereqStatus
from app.features.course.prompts import cards, probe
from app.features.parsing.models import Concept, ConceptSegment, Document, DocSegment

_log = logging.getLogger("uvicorn.error")


class Known:
    """④에서 학습자가 고른 것."""

    KNOWN = "known"    # 안다
    HEARD = "heard"    # 들어봤다
    UNKNOWN = "unknown"  # 모른다

    ALL = frozenset({KNOWN, HEARD, UNKNOWN})


class Goal:
    EXAM = "exam"
    WORK = "work"
    INTEREST = "interest"

    ALL = frozenset({EXAM, WORK, INTEREST})


class Style:
    METAPHOR = "metaphor"      # 비유
    DEFINITION = "definition"  # 정의
    TABLE = "table"            # 표
    WHY = "why"                # 왜 쓰나

    ALL = frozenset({METAPHOR, DEFINITION, TABLE, WHY})


@dataclass
class Question:
    """확인 문항 하나. 정답은 우리가 알고 있고 LLM은 오답만 만들었다."""

    prereq_id: uuid.UUID
    subject: str
    item: str
    stem: str
    choices: list[str] = dc_field(default_factory=list)
    answer_index: int = 0


# ── ⑤ 확인 문항을 몇 개 낼 것인가 ────────────────────────────────
#
# **고정 개수가 아니다.** 이건 점수를 내는 시험이 아니라 "자기 말이 믿을 만한가"를
# 재는 표본이라, 자기 말이 많을수록 몇 개 더 본다. 대신 상한을 둔다 —
# 진단이 길어지면 시험처럼 느껴지고, 그 순간 이 화면의 목적이 깨진다.
#
#   "안다" 1~3개   → 1문항
#   4~8개          → 2문항
#   9~15개         → 3문항
#   16개 이상      → 4문항 (상한)
#
# 틀리면 그 **과목 전체**를 heard로 낮춘다. 문항 하나로 항목 하나를 판정하는 게
# 아니라, 그 사람의 자기평가가 후한지를 보는 것이다.
PROBE_DIVISOR = 4
PROBE_MIN = 1
PROBE_MAX = 4

# 오답 유사도 채택 구간. 실측:
#   0.98  정답을 말만 바꿔 옮김 → 정답이 둘이 된다   버림
#   0.83  한 군데만 뒤집음                            채택
#   0.77  같은 결이지만 뜻이 다름                     채택
#   0.25  딴소리 → 아무나 골라낸다                    버림
DISTRACTOR_MIN_SIM = 0.60
DISTRACTOR_MAX_SIM = 0.95

# 책 밖 항목의 정답을 만들 때, 두 번 생성한 답이 이만큼 닮아야 쓴다.
# 실측 일치 시 0.84~0.91.
DEFINE_AGREE_SIM = 0.75


def probe_count(known_items: int) -> int:
    """확인 문항 수. 0이면 물을 게 없다."""
    if known_items <= 0:
        return 0
    return max(PROBE_MIN, min(PROBE_MAX, math.ceil(known_items / PROBE_DIVISOR)))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class DiagnosticService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 화면 ①~④에 내려줄 것 ──────────────────────────────────
    def setup(self, course: Course) -> dict:
        """진단 화면이 필요한 것 전부. LLM을 안 부른다 — 즉시 뜬다."""
        documents = list(
            self.db.scalars(
                select(Document).where(
                    Document.id.in_([cd.document_id for cd in course.documents])
                )
            )
        )
        rows = self._prereqs(course.id)

        subjects: dict[str, list[CoursePrereq]] = {}
        for row in rows:
            subjects.setdefault(row.subject, []).append(row)

        return {
            "course_id": course.id,
            "field": next((d.field for d in documents if d.field), None),
            "documents": [d.filename for d in documents],
            "goal": course.goal,
            "deadline_weeks": course.deadline_weeks,
            "style": course.style,
            "diagnosed_at": course.diagnosed_at,
            "subjects": [
                {
                    "subject": name,
                    # 순서가 강제되는 과목이면 보강 '단원', 아니면 한 '꼭지'.
                    "ordered": any(r.ordered for r in items),
                    "items": [
                        {
                            "id": r.id,
                            "item": r.item,
                            "why": r.why,
                            "status": r.status,
                            "known": r.known,
                        }
                        for r in sorted(items, key=lambda r: r.seq)
                    ],
                }
                for name, items in subjects.items()
            ],
        }

    def _prereqs(self, course_id: uuid.UUID) -> list[CoursePrereq]:
        """진단이 물어볼 것 — 기각된 항목은 뺀다.

        rejected는 "이 코스의 자료가 이미 가르친다"는 뜻이라 물어볼 값어치가
        없다. gray는 애매한 것이라 묻되 화면이 표시해 준다.
        """
        return list(
            self.db.scalars(
                select(CoursePrereq)
                .where(
                    CoursePrereq.course_id == course_id,
                    CoursePrereq.status != PrereqStatus.REJECTED.value,
                )
                .order_by(CoursePrereq.subject, CoursePrereq.seq)
            )
        )

    # ── ③ 카드 4장 ───────────────────────────────────────────
    async def cards(self, course: Course) -> dict:
        """같은 개념을 네 형식으로. 학습자가 고른 것이 `style`이 된다.

        **이 코스에서 실제로 배울 개념**으로 만든다. 예시용 가짜 개념을 쓰면
        형식이 아니라 그 개념의 친숙함을 고르게 된다.
        """
        concept = self._representative(course)
        if concept is None:
            return {"concept": None, "cards": {}}

        source = self._source_of(concept)
        try:
            raw = await solar_client.generate_json(
                cards.build_prompt(
                    concept=concept.name,
                    definition=concept.definition or "",
                    source=source,
                ),
                system=cards.SYSTEM,
            )
        except Exception as exc:  # noqa: BLE001 — 카드 없이도 진단은 돈다
            _log.warning("성향 카드 생성 실패 (%s): %s", concept.name, exc)
            return {"concept": concept.name, "cards": {}}

        return {
            "concept": concept.name,
            "cards": {k: str(raw.get(k) or "").strip() for k in cards.STYLES},
        }

    def _representative(self, course: Course) -> Concept | None:
        """뼈대 자료에서 **원문에 가장 많이 걸린 개념** 하나.

        많이 걸렸다는 건 그 자료가 그만큼 다룬다는 뜻이라, 네 형식으로 쓸
        재료가 있고 학습자에게도 낯설지 않다.
        """
        document_ids = [cd.document_id for cd in course.documents]
        if not document_ids:
            return None
        row = self.db.execute(
            select(Concept)
            .join(ConceptSegment, ConceptSegment.concept_id == Concept.id)
            .where(
                Concept.document_id.in_(document_ids),
                Concept.topic_id.isnot(None),  # 끊긴 고리는 원문이 없다
            )
            .group_by(Concept.id)
            .order_by(func.count(ConceptSegment.id).desc(), Concept.name)
            .limit(1)
        ).scalars().first()
        return row

    def _source_of(self, concept: Concept) -> str:
        """그 개념이 걸린 조각 하나. 카드가 지어내지 않게 하는 근거다."""
        row = self.db.execute(
            select(DocSegment)
            .join(ConceptSegment, ConceptSegment.segment_id == DocSegment.id)
            .where(ConceptSegment.concept_id == concept.id)
            .order_by(DocSegment.seq)
            .limit(1)
        ).scalars().first()
        return row.content if row else ""

    # ── ④ 선수 체크 — 과목 먼저, 모르는 것만 펼친다 ────────────
    #
    # 항목을 전부 물으면 실측 54개다(필기+실기 코스, 과목 15). 그걸 하나씩
    # 찍게 하면 진단이 시험이 된다. 그리고 애초에 우리가 찾으려던 건 **과목
    # 수준의 결손**이지 항목 하나하나가 아니다.
    #
    #   과목 "안다"        → 항목 전부 known. 안 펼친다
    #   과목 "들어봤다"    → 펼친다. 항목마다 다시 묻는다
    #   과목 "모른다"      → 항목 전부 unknown. 안 펼친다 (보강 단원으로 통째로 간다)
    #
    # "들어봤다"만 펼치는 이유: 아는 것과 모르는 것은 더 물어봐야 얻을 게 없다.
    # 애매한 것만 갈라내면 되고, 그게 보통 두세 과목이다.
    def record_subjects(self, course: Course, *, answers: dict[str, str]) -> list[str]:
        """`{과목명: known|heard|unknown}`. 펼쳐야 할 과목 이름을 돌려준다."""
        rows = self._prereqs(course.id)
        expand: list[str] = []
        for subject, value in answers.items():
            if value not in Known.ALL:
                continue
            if value == Known.HEARD:
                expand.append(subject)
                continue
            for row in rows:
                if row.subject == subject:
                    row.known = value
                    row.verified = None
        return sorted(set(expand))

    def record(self, course: Course, *, answers: dict[uuid.UUID, str]) -> int:
        """펼친 과목의 항목별 답. `{prereq_id: known|heard|unknown}`."""
        rows = {r.id: r for r in self._prereqs(course.id)}
        n = 0
        for prereq_id, value in answers.items():
            row = rows.get(prereq_id)
            if row is None or value not in Known.ALL:
                continue
            row.known = value
            row.verified = None  # 답이 바뀌면 이전 확인 결과는 버린다
            n += 1
        return n

    # ── ⑤ 확인 문항 ──────────────────────────────────────────
    async def probes(self, course: Course) -> list[Question]:
        """"안다"고 한 것 중 몇 개만 실제로 물어본다.

        고르는 방식은 **무작위**다. 어려운 것만 고르면 그 사람이 후한지가
        아니라 그 항목이 어려운지를 재게 된다.
        """
        claimed = [r for r in self._prereqs(course.id) if r.known == Known.KNOWN]
        n = probe_count(len(claimed))
        if n == 0:
            return []

        picked = random.sample(claimed, min(n, len(claimed)))
        out: list[Question] = []
        for row in picked:
            question = await self._build(row)
            if question is not None:
                out.append(question)
        return out

    async def _build(self, row: CoursePrereq) -> Question | None:
        """문항 하나. 정답을 못 세우면 **문항을 안 낸다.**

        확인 문항이 없어도 `known`이 그대로 남을 뿐이라 손해가 작다. 반대로
        정답이 불확실한 문항을 내면 아는 사람을 모른다고 판정한다 — 그게 훨씬 나쁘다.
        """
        answer = await self._answer_of(row)
        if not answer:
            return None

        try:
            raw = await solar_client.generate_json(
                probe.build_prompt(subject=row.subject, item=row.item, answer=answer),
                system=probe.SYSTEM,
            )
            candidates = [
                str(x).strip() for x in (raw.get("distractors") or []) if str(x).strip()
            ]
        except Exception as exc:  # noqa: BLE001 — 문항을 안 낼 뿐이다
            _log.warning("확인 문항 오답 생성 실패 (%s): %s", row.item, exc)
            return None

        usable = await self._usable(answer, candidates)
        if len(usable) < 2:  # 보기 3개는 돼야 찍기를 거른다
            _log.info("확인 문항 버림 — 쓸 만한 오답 %d개 (%s)", len(usable), row.item)
            return None

        choices = [answer, *usable[: probe.DISTRACTORS]]
        random.shuffle(choices)
        return Question(
            prereq_id=row.id,
            subject=row.subject,
            item=row.item,
            stem=f"'{row.item}'에 대한 설명으로 옳은 것은?",
            choices=choices,
            answer_index=choices.index(answer),
        )

    async def _answer_of(self, row: CoursePrereq) -> str:
        """정답 문장. **LLM이 정하게 두지 않는다.**

        선수 항목은 코스 자료 밖의 것이라(그게 선수의 정의다) 원문에서 가져올
        수 없다. 그래서 생성하되 혼자 믿지 않는다 — 같은 물음을 두 번 던져
        두 답이 충분히 닮았을 때만 쓴다.
        """
        try:
            first, second = await asyncio.gather(
                self._define(row), self._define(row)
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("정답 생성 실패 (%s): %s", row.item, exc)
            return ""
        if not first or not second:
            return ""

        vectors = await solar_client.embed_batch([first, second], purpose="query")
        agreement = _cosine(vectors[0], vectors[1])
        if agreement < DEFINE_AGREE_SIM:
            _log.info(
                "정답 버림 — 두 답이 안 맞음 %.3f (%s)", agreement, row.item
            )
            return ""
        return first

    async def _define(self, row: CoursePrereq) -> str:
        raw = await solar_client.generate_json(
            probe.build_define_prompt(subject=row.subject, item=row.item),
            system=probe.DEFINE_SYSTEM,
        )
        return str(raw.get("definition") or "").strip()

    async def _usable(self, answer: str, candidates: list[str]) -> list[str]:
        """정답과 너무 닮았거나 너무 먼 오답을 버린다."""
        if not candidates:
            return []
        vectors = await solar_client.embed_batch(
            [answer, *candidates], purpose="query"
        )
        base = vectors[0]
        out = []
        for text, vector in zip(candidates, vectors[1:]):
            sim = _cosine(base, vector)
            if DISTRACTOR_MIN_SIM <= sim <= DISTRACTOR_MAX_SIM:
                out.append(text)
            else:
                _log.debug("오답 버림 %.3f: %s", sim, text[:40])
        return out

    def grade(self, course: Course, *, results: dict[uuid.UUID, bool]) -> dict:
        """확인 문항 채점. 틀리면 그 **과목 전체**를 heard로 낮춘다.

        문항 하나로 항목 하나를 판정하는 게 아니다 — 표본으로 그 사람의
        자기평가가 후한지를 보는 것이다. 그래서 번지는 범위가 과목이다.
        """
        rows = self._prereqs(course.id)
        by_id = {r.id: r for r in rows}
        demoted: set[str] = set()

        for prereq_id, correct in results.items():
            row = by_id.get(prereq_id)
            if row is None:
                continue
            row.verified = bool(correct)
            if not correct:
                demoted.add(row.subject)

        n = 0
        for row in rows:
            if row.subject in demoted and row.known == Known.KNOWN:
                row.known = Known.HEARD
                n += 1
        return {"demoted_subjects": sorted(demoted), "demoted_items": n}

    # ── ①③ 설정 저장 ────────────────────────────────────────
    def configure(
        self,
        course: Course,
        *,
        goal: str | None = None,
        deadline_weeks: int | None = None,
        style: str | None = None,
    ) -> None:
        if goal in Goal.ALL:
            course.goal = goal
        if deadline_weeks is not None and deadline_weeks > 0:
            course.deadline_weeks = deadline_weeks
        if style in Style.ALL:
            course.style = style
        course.diagnosed_at = datetime.now(UTC)
