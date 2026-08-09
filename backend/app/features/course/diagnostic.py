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
import re
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.course import search
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


# ── ⑤ 판정 — 임베딩으로 거르고 LLM이 정한다 ──────────────────────
#
# **새 문턱을 만들지 않는다.** 여기 쓰는 값은 `CONCEPT_DEDUP_SIM_THRESHOLD`
# (0.92) 하나뿐이고, 그건 "동일 개념 병합"으로 이미 실측된 보수적인 값이다.
# 그 이상이면 명백하니 LLM을 안 부르고, **그 아래는 전부 LLM이 견준다.**
#
#   정의 2회 생성   0.92 이상 → 같다        아래 → LLM "같은 말인가?"
#   오답            0.92 이상 → 정답 베낌   아래 → LLM "같은 말인가 / 상관없나?"
#
# 한때 0.75 · 0.60~0.95 같은 선을 그었는데 표본 4개로 그은 값이라 뺐다.
# 비교 과제는 18단계 회색지대에서 14/14로 검증됐다(§prompts/probe.py).


def _as_index(value, size: int) -> int | None:
    """LLM이 준 번호. 문자열로 오거나 범위를 벗어날 수 있다."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, int) and 0 <= value < size:
        return value
    return None


def _plain(text: str) -> str:
    """보기에서 서식을 벗긴다.

    LLM이 바꾼 자리를 `**하드웨어**`처럼 강조해서 보낼 때가 있다. 정답에는
    강조가 없으니 **그것만 보고 오답을 고를 수 있다.** 문항이 통째로 무의미해진다.
    """
    return re.sub(r"\s+", " ", text.replace("*", "").replace("_", "")).strip()


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
            # "들어봤다"도 항목에 적어 둔다. ②를 건너뛰거나 창을 닫아도 화면이
            # 복원되고, 나중에 항목별 답이 덮이면 그 차이가 곧 "펼쳤다"는 표시가
            # 된다(§search._expanded).
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

    # ── ⑤ 확인 문항 — 과목을 넣나 마나 ─────────────────────────
    #
    # 한 번에 다 내지 않는다. 답을 받아야 다음이 정해지기 때문이다.
    # 화면은 빈 배열이 올 때까지 `GET → POST`를 반복한다.
    #
    #   1라운드  과목마다 문항 하나 (전 과목. 모른다고 한 사람도 묻는다)
    #   2라운드  1라운드를 맞힌 과목만 한 번 더 — 찍어서 맞은 걸 거른다
    #
    # 판정 규칙은 `search.py`에 있다. 틀리면 한 번으로 모른다, 맞으면 두 번을 본다.
    # 상태는 `course_prereqs.known/verified`가 그대로 들고 있다. 세션 테이블이
    # 없으므로 중간에 창을 닫아도 이어진다.
    async def probes(self, course: Course) -> list[Question]:
        """이번 라운드에 물을 문항들. **빈 목록이면 진단이 끝났다.**

        빈 목록에는 두 가지가 섞여 있다 — "더 물을 게 없다"와 "만들려다 다
        버렸다". 앞은 정상이고 뒤는 사고다. 뒤일 때만 한 번 더 만들어 본다.
        """
        pending: list[tuple[str, list[search.Item], search.Item]] = []
        for subject, items in self._subject_states(course.id):
            target = search.next_item(items)
            if target is not None:
                pending.append((subject, items, target))
        if not pending:
            return []  # 더 물을 게 없다. 정상적인 끝

        out = await self._make(course, pending)
        if out:
            return out

        # **한 번만 다시 만든다.** 같은 프롬프트를 던져도 실행마다 결과가 달라서
        # 재시도가 실제로 먹힌다(실측: 같은 요청 3회에 4·6·0문항). 버리는 쪽이
        # 과한 게 아니라 생성이 흔들리는 것이라, 검사를 느슨하게 하는 대신
        # 다시 만든다 — 그쪽을 풀면 정답이 둘인 문항이 사용자에게 나간다.
        #
        # 두 번까지만 한다. 세 번째도 빈손이면 그날 그 모델이 안 되는 것이고,
        # 자기신고가 그대로 남아 보강은 정상적으로 나간다.
        _log.info("확인 문항 다시 만든다 — 첫 판이 빈손 (%s)", course.title)
        return await self._make(course, pending)

    async def _make(
        self,
        course: Course,
        pending: list[tuple[str, list[search.Item], search.Item]],
    ) -> list[Question]:
        """고른 항목들로 문항을 만든다. 못 만든 것은 조용히 빠진다."""
        targets = [(subject, target) for subject, _, target in pending]
        answers = await self._answers_of(targets)

        usable = [
            (subject, row, answers[row.key])
            for subject, row in targets
            if answers.get(row.key)
        ]
        # 정답을 하나도 못 세웠으면 오답을 만들 것도 없다. 빈 목록으로 부르면
        # 항목 0개짜리 프롬프트가 나가므로 그때만 건너뛴다.
        choices = await self._choices_of(usable) if usable else {}
        out: list[Question] = []
        for subject, row, answer in usable:
            options = choices.get(row.key)
            if not options:
                continue
            picks = [answer, *options[: probe.DISTRACTORS]]
            random.shuffle(picks)
            out.append(
                Question(
                    prereq_id=uuid.UUID(row.key),
                    subject=subject,
                    item=row.item,
                    stem=f"'{row.item}'에 대한 설명으로 옳은 것은?",
                    choices=picks,
                    answer_index=picks.index(answer),
                )
            )

        # **문항을 못 낸 것을 적는 자리는 여기 하나뿐이다.** 예전엔 "정답을 하나도
        # 못 세운" 경우를 따로 빠져나가면서 같은 함수를 다른 모양으로 불렀고,
        # 그 경로만 안 지나가다가 실제로 터졌다(ValueError: expected 3, got 2).
        made = {str(q.prereq_id) for q in out}
        self._give_up(
            [(s, t, "정답 없음" if not answers.get(t.key) else "오답 없음")
             for s, _, t in pending if t.key not in made]
        )
        if not out:
            _log.info("확인 문항 없음 — 이 판은 빈손이다 (%s)", course.title)
        return out

    def _subject_states(
        self, course_id: uuid.UUID
    ) -> list[tuple[str, list[search.Item]]]:
        """과목별 상태. 항목은 `seq` 순 — 어느 걸 먼저 물을지에만 쓴다.

        `seq`를 선후관계로 안 읽는다. 병합된 과목은 원본마다 0부터 다시 세는
        값이 섞여 있어서 순서가 아니다(§search 머리말).
        """
        rows = self._prereqs(course_id)
        grouped: dict[str, list[CoursePrereq]] = {}
        for row in rows:
            grouped.setdefault(row.subject, []).append(row)

        out = []
        for subject, items in grouped.items():
            items.sort(key=lambda r: r.seq)
            out.append(
                (
                    subject,
                    [
                        search.Item(
                            key=str(r.id), item=r.item, known=r.known, verified=r.verified
                        )
                        for r in items
                    ],
                )
            )
        return out

    def _give_up(self, missed: list[tuple[str, search.Item, str]]) -> None:
        """문항을 못 낸 항목을 기록만 한다.

        `verified`를 건드리면 "틀렸다"가 되어 과목이 통째로 탈락한다. 그래서
        **아무것도 안 바꾼다.** 다음 라운드에 다시 시도하고(LLM이라 될 수도
        있다), 끝내 못 내면 그 과목은 자기신고가 그대로 남는다. 진단이 문항
        생성 실패로 멈춰서도, 안 물어본 것을 모른다고 단정해서도 안 된다.
        """
        for subject, row, why in missed:
            _log.info("확인 문항 생략 — %s: [%s] %s", why, subject, row.item)

    # ── 정답 세우기 — LLM이 정답을 정하지 않는다 ────────────────
    async def _answers_of(
        self, targets: list[tuple[str, search.Item]]
    ) -> dict[str, str]:
        """`{prereq_id: 정답 문장}`. 못 세운 항목은 안 들어간다.

        선수 항목은 코스 자료 밖의 것이라(그게 선수의 정의다) 원문에서 가져올
        수 없다. 그래서 생성하되 혼자 믿지 않는다 — **같은 물음을 두 번 던져
        두 답이 같은 말일 때만** 쓴다.
        """
        if not targets:
            return {}
        payload = [(subject, row.item) for subject, row in targets]
        try:
            first, second = await asyncio.gather(
                self._define(payload), self._define(payload)
            )
        except Exception as exc:  # noqa: BLE001 — 문항을 안 낼 뿐이다
            _log.warning("정답 생성 실패: %s", exc)
            return {}

        pairs = [
            (row.item, first.get(i, ""), second.get(i, ""))
            for i, (_, row) in enumerate(targets)
        ]
        agreed = await self._agree(pairs)
        return {
            targets[i][1].key: pairs[i][1] for i in agreed if pairs[i][1]
        }

    async def _define(self, payload: list[tuple[str, str]]) -> dict[int, str]:
        raw = await solar_client.generate_json(
            probe.build_define_prompt(items=payload), system=probe.DEFINE_SYSTEM
        )
        out: dict[int, str] = {}
        for key, value in (raw.get("definitions") or {}).items():
            index = _as_index(key, len(payload))
            text = str(value or "").strip()
            if index is not None and text:
                out[index] = text
        return out

    async def _agree(self, pairs: list[tuple[str, str, str]]) -> set[int]:
        """쓸 수 있는 번호들 — **모순이 아닌 것.**

        기본값이 "쓸 수 있다"다. 지어낸 답을 막는 게 목적이고, 지어내면 두 답이
        서로 어긋난다. 표현이 갈리는 건 정상이라 그것까지 막으면 문항이 다
        사라진다(실측: "같은 말인가"로 물었더니 7개 중 0개 통과).

        임베딩은 명백히 같은 것만 먼저 통과시켜 LLM 콜을 아낀다
        (`CONCEPT_DEDUP_SIM_THRESHOLD` 0.92 — 새로 만든 숫자가 아니다).
        """
        both = [(i, a, b) for i, (_, a, b) in enumerate(pairs) if a and b]
        if not both:
            return set()

        texts: list[str] = []
        for _, a, b in both:
            texts.extend([a, b])
        try:
            vectors = await solar_client.embed_batch(texts, purpose="query")
        except Exception as exc:  # noqa: BLE001
            _log.warning("정답 비교 임베딩 실패 — 전부 LLM에게: %s", exc)
            vectors = []

        obvious: set[int] = set()
        unclear: list[int] = []
        for offset, (index, _, _) in enumerate(both):
            if not vectors:
                unclear.append(index)
                continue
            sim = _cosine(vectors[offset * 2], vectors[offset * 2 + 1])
            if sim >= settings.CONCEPT_DEDUP_SIM_THRESHOLD:
                obvious.add(index)
            else:
                unclear.append(index)

        if not unclear:
            return obvious
        try:
            raw = await solar_client.generate_json(
                probe.build_agree_prompt(pairs=[pairs[i] for i in unclear]),
                system=probe.COMPARE_SYSTEM,
            )
        except Exception as exc:  # noqa: BLE001 — 기본값이 "쓸 수 있다"다
            _log.warning("정답 모순 검사 실패 — 그대로 쓴다: %s", exc)
            return obvious | set(unclear)
        conflict = {
            unclear[i]
            for i in (_as_index(x, len(unclear)) for x in (raw.get("conflict") or []))
            if i is not None
        }
        if conflict:
            _log.info("정답 버림 — 두 답이 모순: %s", [pairs[i][0] for i in conflict])
        return obvious | (set(unclear) - conflict)

    # ── 오답 만들기 ────────────────────────────────────────────
    async def _choices_of(
        self, usable: list[tuple[str, search.Item, str]]
    ) -> dict[str, list[str]]:
        """`{prereq_id: [쓸 만한 오답...]}`. 두 개 미만이면 안 들어간다."""
        payload = [(row.item, answer) for _, row, answer in usable]
        try:
            raw = await solar_client.generate_json(
                probe.build_distractor_prompt(items=payload),
                system=probe.DISTRACTOR_SYSTEM,
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("오답 생성 실패: %s", exc)
            return {}

        candidates: dict[int, list[str]] = {}
        for key, value in (raw.get("distractors") or {}).items():
            index = _as_index(key, len(payload))
            if index is None or not isinstance(value, list):
                continue
            texts = [str(x).strip() for x in value if str(x).strip()]
            if texts:
                candidates[index] = texts

        kept = self._drop_bad(payload, candidates)
        out: dict[str, list[str]] = {}
        for index, texts in kept.items():
            # 보기 3개는 돼야 찍기를 거른다.
            if len(texts) >= 2:
                out[usable[index][1].key] = texts
        if len(kept) != len(candidates) or any(
            len(v) != len(candidates[i]) for i, v in kept.items()
        ):
            # 문항이 왜 안 나왔는지 되짚는 유일한 자리다. 멀쩡할 땐 안 찍는다.
            _log.info(
                "오답 %s → %s",
                {payload[i][0]: len(v) for i, v in sorted(candidates.items())},
                {payload[i][0]: len(v) for i, v in sorted(kept.items())},
            )
        return out

    @staticmethod
    def _drop_bad(
        payload: list[tuple[str, str]], candidates: dict[int, list[str]]
    ) -> dict[int, list[str]]:
        """보기를 다듬는다. **글자만 본다 — LLM도 임베딩도 안 부른다.**

        하는 일은 셋뿐이다. `**강조`를 벗기고, 정답과 글자가 같은 보기를 빼고,
        서로 겹치는 보기를 뺀다.

        ## 왜 LLM에게 안 맡기나

        "실수로 맞게 써진 보기가 있나"를 물었다. **3번에 1번 전부를 버렸다**
        (실측). 묶음 하나면 3/3 깨끗한데 5~7묶음이면 가끔
        `[[0,0],[0,1],...[4,4]]`로 뒤집혀 25개를 통째로 버리고, 그러면 그
        라운드 문항이 전부 사라진다. 문구를 두 번 갈아엎어도 남았다.

        ## 왜 유사도로 안 자르나

        **좋은 오답일수록 정답과 닮는다.** 프롬프트가 "딱 한 군데만 틀리게"를
        요구하니 나머지는 그대로 베껴 온다. 실측:

            정답  ... 검색을 위한 소프트웨어 구조로, 사용자 또는 응용 프로그램과 ...
            오답  ... 검색을 위한  하드웨어  구조로, 사용자 또는 응용 프로그램과 ...
                                                              코사인 1.000

        한 라운드에서 30개 중 28개가 0.94 이상이었다. 0.92로 자르면 **가장 좋은
        오답부터 사라진다.** 반대로 문장을 통째로 다시 쓴 오답은 0.58~0.67로
        내려간다 — 같은 모델이 실행마다 두 방식을 오간다. 문턱을 세울 자리가 없다.

        ## 그럼 정답이 둘 되는 건 누가 막나

        생성 프롬프트의 "말만 바꿔 옮기지 마라"와 여기의 글자 비교뿐이다.
        뚫리면 맞은 사람이 틀린 판정을 받는다 — 그 방향은 **보강을 더 받는
        쪽**이라 덜 해롭다. 진단 하나 때문에 라운드를 통째로 날리는 것보다 낫다.
        """
        out: dict[int, list[str]] = {}
        for index, items in candidates.items():
            answer = _plain(payload[index][1])
            seen = {answer}
            kept: list[str] = []
            for text in items:
                clean = _plain(text)
                if not clean or clean in seen:
                    continue
                seen.add(clean)
                kept.append(clean)
            if kept:
                # **정답과 길이가 비슷한 것부터 세운다.** 버리는 게 아니라
                # 고르는 것이라 문항이 사라지지 않는다.
                #
                # 실측에서 오답이 정답에 절을 덧붙이는 식으로 나와 정답만 혼자
                # 짧았다 — 내용을 몰라도 제일 짧은 걸 고르면 맞는다.
                kept.sort(key=lambda t: abs(len(t) - len(answer)))
                out[index] = kept
        return out

    # ── 채점 ───────────────────────────────────────────────────
    def grade(self, course: Course, *, results: dict[uuid.UUID, bool]) -> dict:
        """답을 반영하고 과목 판정을 한 칸 진행한다.

        판정이 확정된 과목만 `known`을 쓴다. 진행 중에 건드리면 다음 라운드가
        자기신고 대신 중간 결과를 읽게 되고, 보강 범위를 좁힐 근거가 사라진다.

        `verified`는 **실제로 문항에 나간 항목만** True/False다. 나머지가 비어
        있는 건 "안 물어봤다"는 뜻이고, 그 항목의 `known`은 과목 판정을 내린
        값이지 그 항목을 잰 값이 아니다.
        """
        rows = {r.id: r for r in self._prereqs(course.id)}
        graded = 0
        for _, items in self._subject_states(course.id):
            changed = False
            for row in items:
                key = uuid.UUID(row.key)
                if key in results:
                    search.apply(items, row.key, bool(results[key]))
                    changed = True
                    graded += 1
            if not changed:
                continue
            search.finalize(items)
            for row in items:
                target = rows.get(uuid.UUID(row.key))
                if target is not None:
                    target.known = row.known
                    target.verified = row.verified

        remaining = sum(
            1 for _, items in self._subject_states(course.id) if not search.done(items)
        )
        if remaining == 0:
            self.finish(course)
        return {"graded": graded, "subjects_left": remaining}

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
        # ⚠️ **여기서 `diagnosed_at`을 찍지 않는다.** 그건 "설정을 저장했다"가
        # 아니라 "진단을 끝냈다"는 뜻이고, 화면이 그 값으로 진단 안내를 감춘다.
        #
        # 실측 — 책장이 코스를 만들자마자 목표를 저장하려고 이 문을 지난다.
        # 여기서 찍으면 사용자가 진단을 한 번도 안 했는데 배너가 "🔎 진단 다시
        # 하기"(작은 회색 글씨)로 바뀌어, 책만 넣으면 끝나는 것처럼 보인다.
        # 실제로 찍는 자리는 §finish — 모든 과목이 판정된 뒤다.

    def finish(self, course: Course) -> None:
        """진단이 끝났다고 도장을 찍는다. **끝났을 때만 부른다.**"""
        if course.diagnosed_at is None:
            course.diagnosed_at = datetime.now(UTC)
