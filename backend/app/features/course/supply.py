"""26·27 — 모자란 것을 마련하고 목차에 끼운다.

24가 "이 과목을 모른다"까지 정해 놨다. 그걸 받는 자리가 여기다.

    26  조달   과목마다 보강 자료를 마련한다 (있으면 재사용, 없으면 명세를 쓴다)
    27  삽입   그 자료를 코스 목차 **앞**에 끼우고 분량을 정한다

## 만드는 것의 주인은 사용자가 아니다

보강 자료는 **(분야, 과목) 소유**다. `자료구조`를 한 번 만들면 같은 분야를
배우는 다음 사람이 그대로 쓴다. 그래서 두 가지가 따라온다.

  ① **과목을 통째로 만든다.** 지금 이 사람이 모르는 항목만 담으면 다음 사람이
     못 쓴다 — 그 사람은 다른 항목을 모른다.
  ② **사람마다 다른 건 자료가 아니라 `plan`이 들고 있다.**

        모른다고 판정된 과목  →  plan='brief'  화면에 나온다
        안다고 판정된 과목    →  plan='skip'   안 나온다. 자료만 있다

     `skip`이 24의 ④다. 진단이 순서를 지어내지 않게 바꾼 대가로 "안다"가
     추정으로 남는 항목이 생기는데, 자료를 미리 만들어 꺼 두면 나중에 학습
     중에 틀렸을 때 **한 칸 바꿔서** 되살릴 수 있다. 없으면 붙일 게 없다.

## 내용은 안 만든다

`Concept.definition`에 명세만 넣고 조각(`DocSegment`)은 안 만든다. 설명은
학습층이 성향·진도에 맞춰 쓴다 — 원문이 없으면 `definition`을 근거로 삼는
경로가 이미 있다(`curriculum/service.py`). 여기서 쓰면 두 번 만드는 꼴이다.

## 이미 있는 자료는 안 덮어쓴다

② DB 조회로 "이 항목을 이미 가르치는 자료가 있나"를 찾지만 **자동으로 바꿔치지
않고 `note`에만 적는다.** 잘못 걸리면 엉뚱한 단원이 통째로 들어가는데, 실측
히트율이 28개 중 2개라 얻는 것보다 잃는 게 크다. 화면이 그 표시를 보고
사용자에게 "이 자료로 대신할까요"를 물으면 된다.
"""
from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.solar import solar_client
from app.features.course.models import (
    Course,
    CoursePrereq,
    CourseTopic,
    PrereqStatus,
    TopicOrigin,
    TopicPlan,
)
from app.features.course.prompts import supply as supply_prompt
from app.features.course.search import KNOWN, UNKNOWN
from app.features.parsing.models import (
    PARSER_VERSION,
    Concept,
    DocStatus,
    DocTopic,
    Document,
)
from app.features.parsing.repository import ParsingRepository

# `concepts.source` — 원문에 설명이 있으면 book, 선수개념으로만 등장하면 이것.
# 보강 자료의 개념은 전부 후자다(조각이 없다).
AI_PREREQ = "ai_prereq"

_log = logging.getLogger("uvicorn.error")

# 보강 자료의 `source_format`. 파일에서 온 게 아니라 만든 것이고, 책장 목록이
# 이 값으로 걸러 낸다 — 보강 자료가 "읽을 책"으로 뜨면 안 된다.
GENERATED = "generated"

# 지문 규격. 같은 (분야, 과목)이면 같은 지문 → 문서가 하나만 생긴다.
# 명세 형식이 바뀌면 v를 올려 새로 만들게 한다.
_FINGERPRINT_VERSION = "v1"

# 항목 이름이 기존 자료의 개념과 이만큼 닮으면 "이미 가르치는 자료가 있다"고
# 표시한다.
#
# **0.75에서 0.65로 내렸다.** 16'의 기각 문턱을 그대로 빌려 썼는데, 그건
# "지운다"는 결정이라 보수적이어야 하고 여기는 "보여준다"라 사정이 다르다.
# 실측에서 0.75는 **글자까지 거의 같은 짝도 못 넘겼다**:
#
#     부동소수점 오차   → 부동 소수점 한계   0.728   맞다
#     난수 생성과 시드  → 난수 생성         0.682   맞다
#     평균과 중앙값     → 중앙값            0.657   맞다
#     ──────────────── 0.65 ────────────────
#     축(axis) 연산    → 소수점 연산        0.492   아니다
#     기댓값과 분산     → 평균값            0.494   아니다
#
# 원래 주석의 "실측 히트율 28개 중 2개"가 이 문턱 때문이었다.
#
# ⚠️ **이름만 같은 다른 것이 섞인다.** 실측: `브로드캐스팅`(NumPy)이 정처기
#    교재의 `브로드캐스트`(네트워크)에 0.686으로 걸린다. 그래서 확정 화면이
#    **어떤 개념에 얼마나 걸렸는지까지 보여주고 사용자가 끈다.** 자동으로
#    바꿔치지 않는 이유가 이것이다.
_HIT_SIM = 0.65

# 히트를 `note` 안에서 도로 찾아내는 표식. **만드는 쪽과 읽는 쪽이 같은 상수를
# 봐야 한다** — 한쪽 문구만 고치면 화면에서 조용히 사라진다(`covered_by`).
HIT_PREFIX = "이미 있는 자료: "


def _fingerprint(field: str, subject: str) -> str:
    raw = f"prereq:{_FINGERPRINT_VERSION}:{field}:{subject}"
    return hashlib.sha256(raw.encode()).hexdigest()


class SupplyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ParsingRepository(db)

    # ── 바깥문 ────────────────────────────────────────────────────
    async def preview(self, course: Course) -> dict:
        """확정 화면(⑥)이 쓸 것 전부. **LLM을 안 부른다.**

        조달을 미리보기와 확정으로 가른 이유가 이것이다. 명세 생성은 과목당
        몇 초라, 미리보기에서 만들면 사용자가 **뺄 과목까지 만들어 놓고**
        기다리게 된다. 여기서 드는 건 과목 이름 임베딩 1콜뿐이다.

        `source`가 화면의 본론이다:

            book       원문 있는 책이 이걸 가르친다 — 그 책으로 설명한다
            ready      전에 만들어 둔 명세가 있다 (같은 분야·과목)
            generate   아무것도 없다 — 확정하면 그때 만든다
        """
        field = self._field_of(course)
        groups = self._groups(course.id)
        if not groups:
            return {"field": field, "subjects": [], "topics_before": len(course.topics)}

        hits = await self._existing_hits(course, groups)

        subjects = []
        for subject, rows in groups.items():
            hit = hits.get(subject)
            made = self.db.scalar(
                select(Document.id).where(
                    Document.fingerprint == _fingerprint(field, subject)
                )
            )
            plan = _plan_of(rows)
            subjects.append(
                {
                    "subject": subject,
                    "items": [r.item for r in rows],
                    "why": next((r.why for r in rows if r.why), None),
                    "known": sum(1 for r in rows if r.known == KNOWN),
                    "unknown": sum(1 for r in rows if r.known == UNKNOWN),
                    "asked": sum(1 for r in rows if r.verified is not None),
                    "plan": plan,
                    # 뺐던 과목은 꺼진 채로 보여준다 — 지난번 선택을 기억한다.
                    "selected": plan != TopicPlan.SKIP.value
                    and not any(r.excluded for r in rows),
                    "source": "book" if hit else ("ready" if made else "generate"),
                    "evidence": hit,
                }
            )
        return {
            "field": field,
            "subjects": subjects,
            "topics_before": len(course.topics),
        }

    async def run(
        self,
        course: Course,
        *,
        refresh: bool = False,
        exclude: list[str] | None = None,
    ) -> dict:
        """26·27을 한 번에. 이미 끼워진 코스는 `plan`만 다시 맞춘다.

        진단을 다시 하면 판정이 바뀐다. 그때 단원을 지웠다 다시 만들면 사용자가
        고친 순서가 날아가므로, **자료는 그대로 두고 `plan`만 고친다.**

        `exclude`는 확정 화면(⑥)에서 사용자가 뺀 과목이다. 뺀 과목은 명세도
        안 만들고 목차에도 안 넣는다 — **LLM 호출이 그만큼 줄어든다.**
        """
        field = self._field_of(course)
        groups = self._groups(course.id)
        if exclude is not None:
            groups = self._exclude(course.id, groups, exclude)
        if not groups:
            return {"subjects": 0, "made": 0, "reused": 0, "inserted": 0, "updated": 0}

        hits = await self._existing_hits(course, groups)

        made = reused = 0
        documents: dict[str, Document] = {}
        for subject, rows in groups.items():
            document, fresh = await self._document_for(field, subject, rows)
            if document is None:
                continue
            documents[subject] = document
            made += fresh
            reused += not fresh

        inserted, updated = self._insert(
            course, groups, documents, hits, refresh=refresh
        )
        self.db.flush()
        _log.info(
            "26·27 조달: %s — 과목 %d (새로 %d · 재사용 %d) · 끼움 %d · 갱신 %d",
            course.title, len(groups), made, reused, inserted, updated,
        )
        return {
            "subjects": len(groups),
            "made": made,
            "reused": reused,
            "inserted": inserted,
            "updated": updated,
        }

    # ── 재료 ──────────────────────────────────────────────────────
    def _field_of(self, course: Course) -> str:
        """12.5가 판정한 분야. 명세를 쓸 때 맥락으로 쓴다.

        `정규화`가 데이터베이스에서는 중복 제거고 머신러닝에서는 값 범위 맞추기다.
        분야가 없으면 코스 제목으로 대신한다 — 없는 것보다 낫다.
        """
        rows = self.db.scalars(
            select(Document.field).where(
                Document.id.in_([cd.document_id for cd in course.documents])
            )
        ).all()
        return next((f for f in rows if f), course.title)

    def _groups(self, course_id: uuid.UUID) -> dict[str, list[CoursePrereq]]:
        """과목별 선수 항목. 기각된 것은 뺀다 — 코스 자료가 이미 가르친다."""
        rows = self.db.scalars(
            select(CoursePrereq)
            .where(
                CoursePrereq.course_id == course_id,
                CoursePrereq.status != PrereqStatus.REJECTED.value,
            )
            .order_by(CoursePrereq.subject, CoursePrereq.seq)
        ).all()
        groups: dict[str, list[CoursePrereq]] = {}
        for row in rows:
            groups.setdefault(row.subject, []).append(row)
        return groups

    def _exclude(
        self,
        course_id: uuid.UUID,
        groups: dict[str, list[CoursePrereq]],
        exclude: list[str],
    ) -> dict[str, list[CoursePrereq]]:
        """뺀 과목을 도장 찍고 목록에서 뺀다.

        **지우지 않는다.** 선수 판정은 자료에서 나오므로 행을 지우면 다음
        계산이 같은 과목을 되살린다. 뺐다는 사실만 남긴다.
        """
        dropped = set(exclude)
        for subject, rows in groups.items():
            for row in rows:
                row.excluded = subject in dropped
        self.db.flush()
        if dropped:
            _log.info("확정 화면에서 뺀 과목: %s", ", ".join(sorted(dropped)))
        return {s: rows for s, rows in groups.items() if s not in dropped}

    # ── 26 조달 ───────────────────────────────────────────────────
    async def _document_for(
        self, field: str, subject: str, rows: list[CoursePrereq]
    ) -> tuple[Document | None, bool]:
        """`(문서, 새로 만들었나)`. 같은 (분야, 과목)이면 한 번만 만든다."""
        fingerprint = _fingerprint(field, subject)
        existing = self.db.scalar(
            select(Document).where(Document.fingerprint == fingerprint)
        )
        if existing is not None:
            return existing, False

        specs = await self._specs(field, subject, [r.item for r in rows])
        if not specs:
            _log.warning("보강 명세를 못 만들었다 — 건너뛴다: [%s] %s", field, subject)
            return None, False

        document = Document(
            fingerprint=fingerprint,
            filename=f"[보강] {subject}",
            source_format=GENERATED,
            visibility="public",   # 주인이 없다. 같은 분야를 배우는 누구나 쓴다
            status=DocStatus.READY.value,
            parser_version=PARSER_VERSION,
            field=field,
        )
        self.db.add(document)
        self.db.flush()

        topic = DocTopic(document_id=document.id, seq=0, title=subject)
        self.db.add(topic)
        self.db.flush()

        for seq, row in enumerate(rows):
            spec = specs.get(seq)
            if spec is None:
                continue
            self.db.add(
                Concept(
                    document_id=document.id,
                    topic_id=topic.id,
                    name=row.item,
                    normalized_name=row.item.strip().lower(),
                    definition=spec,
                    # 원문에서 뽑은 게 아니다. 조각도 없다.
                    source=AI_PREREQ,
                )
            )
        self.db.flush()
        return document, True

    async def _specs(self, field: str, subject: str, items: list[str]) -> dict[int, str]:
        """`{번호: "가르칠 것 — 키워드, 키워드"}`. 못 쓰면 안 들어간다."""
        try:
            raw = await solar_client.generate_json(
                supply_prompt.build_prompt(field=field, subject=subject, items=items),
                system=supply_prompt.SYSTEM,
            )
        except Exception as exc:  # noqa: BLE001 — 이 과목만 건너뛴다
            _log.warning("보강 명세 생성 실패 [%s]: %s", subject, exc)
            return {}

        out: dict[int, str] = {}
        for key, value in (raw.get("specs") or {}).items():
            index = _as_index(key, len(items))
            if index is None or not isinstance(value, dict):
                continue
            teach = str(value.get("teach") or "").strip()
            if not teach:
                continue  # "확실하지 않으면 빈 문자열" — 지어낸 것보다 낫다
            words = [
                str(w).strip()
                for w in (value.get("keywords") or [])
                if str(w).strip()
            ]
            out[index] = f"{teach} (핵심어: {', '.join(words)})" if words else teach
        return out

    # ── ② 이미 있는 자료 찾기 — 표시만 한다 ──────────────────────
    async def _existing_hits(
        self, course: Course, groups: dict[str, list[CoursePrereq]]
    ) -> dict[str, dict]:
        """`{과목: {filename, concept, similarity, document_id}}`. 임베딩 1콜.

        **과목 이름이 아니라 하위 항목으로 찾는다.** 과목 이름은 임베딩이 못
        가른다 — 실측에서 `데이터베이스 기초`의 최근접이 `데이터베이스`인데도
        0.650이라 문턱 근처에도 못 갔다. 반면 하위 항목은 구체적인 명사구라
        잘 듣는다:

            데이터베이스 기초        → 데이터베이스        0.650   ✗ 못 걸린다
            트랜잭션과 ACID 속성     → 트랜잭션 특성       0.765   ✓
            유선/무선 네트워크 표준   → 무선 LAN 표준      0.789   ✓

        문턱을 낮추는 대신 **묻는 걸 바꿨다.** 항목 하나라도 걸리면 그 책이
        그 과목을 다룬다고 본다.

        **바꿔치지 않는다.** 잘못 걸리면 엉뚱한 단원이 통째로 들어가는데 실측
        히트율이 28개 중 2개라, 자동화해서 얻는 것보다 잃는 게 크다. 확정
        화면(⑥)이 이걸 보여주고 **사용자가 고른다.**

        세 가지는 걸러야 쓸모가 있다.

            코스 자기 자료   16'이 "이 자료는 이걸 안 가르친다"고 이미 판정했다.
                            그걸 다시 추천하면 그 판정을 뒤집는 셈이다
            보강 자료        우리가 만든 명세끼리 서로 가리키면 아무 값도 없다
            원문 없는 개념   `ai_prereq`거나 조각이 안 붙은 개념은 이름만 있다.
                            "이 자료로 대신 배우세요"의 근거가 못 된다
        """
        pairs = [(subject, row.item) for subject, rows in groups.items() for row in rows]
        if not pairs:
            return {}
        try:
            vectors = await solar_client.embed_batch(
                [item for _, item in pairs], purpose="query"
            )
        except Exception as exc:  # noqa: BLE001 — 표시가 없을 뿐이다
            _log.warning("보강 대체 자료 조회 실패: %s", exc)
            return {}

        mine = {cd.document_id for cd in course.documents}
        out: dict[str, dict] = {}
        for (subject, item), vector in zip(pairs, vectors):
            # 최근접 하나만 보면 거를 것들에 자리를 뺏긴다. 몇 개 보고 고른다.
            for concept, similarity in self.repo.search_concepts(
                embedding=vector, limit=5, min_sim=_HIT_SIM
            ):
                if concept.document_id in mine or concept.source != "book":
                    continue
                if not concept.segment_links:
                    continue
                document = self.repo.get_document(concept.document_id)
                if document is None or document.source_format == GENERATED:
                    continue
                # 과목마다 가장 닮은 항목 하나만 남긴다 — 화면에 한 줄이다.
                best = out.get(subject)
                if best is None or similarity > best["similarity"]:
                    out[subject] = {
                        "document_id": str(document.id),
                        "filename": document.filename,
                        "concept": concept.name,
                        "item": item,
                        "similarity": round(float(similarity), 3),
                    }
                break
        return out

    # ── 27 삽입 ───────────────────────────────────────────────────
    def _insert(
        self,
        course: Course,
        groups: dict[str, list[CoursePrereq]],
        documents: dict[str, Document],
        hits: dict[str, dict],
        *,
        refresh: bool,
    ) -> tuple[int, int]:
        """보강 단원을 목차 **앞**에 끼운다. `(새로 끼움, plan만 갱신)`.

        앞에 두는 이유는 하나다 — 선수는 먼저 배운다. 어느 단원 바로 앞인지까지
        정하려면 "이 항목이 몇 번 단원에서 필요한가"를 알아야 하는데, 그건 12.5가
        과목 단위로만 주는 값이라 지금은 근거가 없다.
        """
        by_source = {t.source_topic_id: t for t in course.topics if t.source_topic_id}
        updated = 0
        fresh: list[tuple[str, DocTopic, str, str]] = []

        for subject, rows in groups.items():
            document = documents.get(subject)
            if document is None:
                continue
            topic = self.db.scalar(
                select(DocTopic).where(DocTopic.document_id == document.id)
            )
            if topic is None:
                continue
            plan = _plan_of(rows)
            note = _note_of(rows, hits.get(subject))
            already = by_source.get(topic.id)
            if already is not None:
                # `note`도 같이 고친다. 판정을 설명하는 문장이라 판정이 바뀌면
                # 같이 바뀌어야 한다 — 안 그러면 화면이 옛날 근거를 보여준다.
                if already.plan != plan or already.note != note or refresh:
                    already.plan, already.note = plan, note
                    updated += 1
                continue
            fresh.append((subject, topic, plan, note))

        if not fresh:
            return 0, updated

        # `(course_id, seq)`가 유니크라 자리를 한 번에 못 옮긴다. 기존 단원을
        # 임시 음수로 비켜 두고, 보강을 앞에 깐 뒤, 기존을 뒤에 다시 매긴다.
        existing = sorted(course.topics, key=lambda t: t.seq)
        for i, topic in enumerate(existing):
            topic.seq = -1 - i
        self.db.flush()

        for seq, (subject, source, plan, note) in enumerate(fresh):
            self.db.add(
                CourseTopic(
                    course_id=course.id,
                    seq=seq,
                    title=subject,
                    source_topic_id=source.id,
                    origin=TopicOrigin.INSERTED.value,
                    plan=plan,
                    note=note,
                )
            )
        self.db.flush()

        for i, topic in enumerate(existing):
            topic.seq = len(fresh) + i
        self.db.flush()
        return len(fresh), updated


def _plan_of(rows: list[CoursePrereq]) -> str:
    """이 과목을 화면에 낼까 말까.

    **안다고 확인된 것만 숨긴다.** 전부 `known`일 때만 `skip`이고, 하나라도
    모른다거나 **아직 안 물어봤으면**(`known`이 비어 있으면) 낸다.

    비어 있는 걸 숨기면 진단을 안 한 사람이 보강을 하나도 못 받는다 — 실측에서
    AWS 코스가 그렇게 6과목 전부 `skip`으로 깔렸다. 선수는 정의상 코스 자료가
    안 가르치는 것이라, 모르면 주는 쪽이 맞다.

    `skip`도 자료는 남는다. 24의 판정이 추정일 수 있어서, 학습 중에 틀리면
    여기를 `brief`로 바꿔 되살린다.
    """
    if rows and all(r.known == KNOWN for r in rows):
        return TopicPlan.SKIP.value
    return TopicPlan.BRIEF.value


def covered_by(note: str | None) -> str | None:
    """`note`에서 **"이 선수 개념은 이미 있는 자료에 있다"** 부분만 떼어낸다.

    `note`는 진단 통계와 히트가 한 줄에 붙어 있다. 앞부분("진단: 5항목 중
    안다 3…")은 왜 이 단원이 생겼는지를 적은 디버그 문장이라 학습자에게
    보여줄 것이 아니고, 뒷부분만 화면에 값이 있다.

    문자열을 자르는 게 마음에 안 들지만 컬럼을 쪼개려면 마이그레이션이 필요하고,
    형식을 아는 곳이 여기(`_note_of`가 만든다)라 여기 둔다. 접두사를 상수로
    묶어 둔 이유도 그것이다 — 한쪽만 고치면 조용히 안 잡힌다.
    """
    if not note or HIT_PREFIX not in note:
        return None
    return note.split(HIT_PREFIX, 1)[1].strip() or None


def _note_of(rows: list[CoursePrereq], hit: dict | None) -> str:
    """왜 이 단원이 생겼는지 한 줄. 화면이 그대로 보여준다.

    히트는 이제 구조체(확정 화면이 쓴다)지만 **여기서 펴는 문자열 형식은 그대로
    두어야 한다** — `covered_by()`가 이 문장을 도로 잘라서 학습 화면에 쓴다.
    """
    known = sum(1 for r in rows if r.known == KNOWN)
    unknown = sum(1 for r in rows if r.known == UNKNOWN)
    asked = sum(1 for r in rows if r.verified is not None)
    note = f"진단: {len(rows)}항목 중 안다 {known} · 모른다 {unknown} · 확인 문항 {asked}"
    if len(rows) - known - unknown:
        note += f" · 미확인 {len(rows) - known - unknown}"
    if not hit:
        return note
    return (
        f"{note} · {HIT_PREFIX}{hit['filename']} — "
        f"{hit['concept']} ({hit['similarity']:.2f})"
    )


def _as_index(value, size: int) -> int | None:
    """LLM이 준 번호. 문자열로 오거나 범위를 벗어날 수 있다."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, int) and 0 <= value < size:
        return value
    return None
