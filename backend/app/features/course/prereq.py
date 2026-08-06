"""16'단계 — 선수 항목이 정말 '책 밖'인지 거른다. Solar 1회(임베딩)뿐.

12.5단계가 뽑은 선수 후보를 **이 코스의 실제 자료들**과 대조한다.

**왜 걸러야 하나.** LLM이 그 책이 가르치는 것을 선수라고 뱉는다. 실측에서
정처기 필기 자료에 `데이터베이스 기초`가 나왔는데 목차 3번이 "데이터베이스
구축"이었다. AWS 슬라이드에는 `VPC CIDR 블록 정의`가 나왔는데 그게 정확히 그
슬라이드의 내용이다. 프롬프트로는 못 막는다 — 자료의 실제 개념과 대조해야 한다.

**왜 코스 단위인가.** PPT가 요구하는 선수를 같이 올린 교재가 이미 커버할 수
있다. 자료 조합이 바뀌면 답이 달라지므로 판정은 코스 소유다. (재료인
`documents.prereq_probe`는 문서 소유다 — 같은 책이면 항상 같은 후보가 나온다.)

**임베딩은 양 끝만 맞고 가운데는 틀린다.** 이건 실측으로 확인했다.

처음 정답을 아는 21개로 쟀을 때는 깨끗해 보였다(책 안 0.509~0.828 / 책 밖
0.344~0.468, 겹침 없음). 그런데 실제로 돌려 보니 항목이 늘면서 두 무리가
가운데에서 섞였다:

    0.783  CIDR 표기법        → CIDR 표기            가르친다 ✓
    0.765  AWS 리전 개념      → 리전(Region)         가르친다 ✓
    ── 여기부터 섞인다 ────────────────────────────────────
    0.645  라우팅 기초        → 라우팅               **전제한다** (오판)
    0.573  EC2 및 인스턴스 개념 → EC2 인스턴스 퍼블릭 IP  **전제한다** (오판)
    0.552  NAT 원리          → NAT 게이트웨이(NGW)    **전제한다** (오판)
    0.539  IP 주소 체계       → IP 주소 범위          **전제한다** (오판)
    ─────────────────────────────────────────────────────
    0.468  입출력 장치 관리     → UNIX 커널 기능        전제한다 ✓
    0.344  OSI 7계층 모델      → 프로토콜              전제한다 ✓

원인이 분명하다. 유사도는 **"비슷한 이름의 개념이 있나"**를 재지 **"이걸
가르치나"**를 못 잰다. `라우팅 기초`와 `라우팅`(AWS 라우팅 테이블)은 이름이
같고 범위가 다르다. 21개 표본이 깨끗했던 건 양 끝만 골랐기 때문이다.

**그래서 3단이다.** 양 끝은 임베딩이 확실하니 그대로 쓰고, 가운데만 LLM에
묻는다(18단계 개념 연결과 같은 구조).

    0.75 이상   기각. 자료가 확실히 가르친다
    0.50~0.75   LLM에게 "가르치나 전제하나"를 묻는다
    0.50 미만   통과. 확실히 책 밖

0.50 하한은 첫 실측의 경계(책 안 최소 0.509 / 책 밖 최대 0.468)에서 왔다.
LLM 호출이 실패하면 **통과 쪽으로 둔다** — 놓치는 것보다 목록이 조금 긴 게 낫다.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.course import prompts
from app.features.course.models import Course, CoursePrereq, PrereqStatus
from app.features.parsing.models import Concept, Document, DocTopic
from app.features.parsing.repository import ParsingRepository

_log = logging.getLogger("uvicorn.error")

# 최근접을 몇 개 받아서 그중 '설명이 있는' 첫 개념을 고를지.
# 설명 없는 개념(끊긴 고리)이 최근접에 끼는 일이 흔해 여유를 둔다.
_NEAREST_FETCH = 5


@dataclass
class Candidate:
    """대조하기 전의 선수 항목 하나."""

    subject: str
    item: str
    why: str
    ordered: bool
    seq: int


def collect(documents: list[Document]) -> list[Candidate]:
    """코스의 모든 자료에서 선수 후보를 모은다.

    같은 (과목, 항목)이 여러 자료에서 나오면 한 번만 담는다. 문자열 일치로만
    거른다 — 뜻 중복은 아래 `screen`이 임베딩으로 처리한다.
    """
    seen: set[tuple[str, str]] = set()
    out: list[Candidate] = []
    for document in documents:
        probe = document.prereq_probe or {}
        for subject in probe.get("prereq_subjects") or []:
            name = str(subject.get("name") or "").strip()
            if not name:
                continue
            ordered = bool(subject.get("ordered"))
            why = str(subject.get("why") or "").strip()
            for seq, item in enumerate(subject.get("subtopics") or []):
                item = str(item).strip()
                key = (name, item)
                if not item or key in seen:
                    continue
                seen.add(key)
                out.append(
                    Candidate(
                        subject=name, item=item, why=why, ordered=ordered, seq=seq
                    )
                )
    return out


class PrereqScreen:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ParsingRepository(db)

    def _has_taught_concepts(self, document_ids: list[uuid.UUID]) -> bool:
        """대조할 개념이 있기는 한가.

        `concept_segments`가 있는 것만 센다. 링크가 없는 개념은 원문에 설명이
        없다는 뜻이라 "이미 가르친다"의 근거가 될 수 없다.
        """
        return self.db.scalar(
            select(Concept.id)
            .where(
                Concept.document_id.in_(document_ids),
                Concept.embedding.is_not(None),
                Concept.segment_links.any(),
            )
            .limit(1)
        ) is not None

    @staticmethod
    def _dedup(
        candidates: list[Candidate], vectors: list[list[float]]
    ) -> tuple[list[Candidate], list[list[float]]]:
        """뜻이 같은 항목을 하나로. 먼저 나온 쪽을 남긴다.

        같은 항목이 둘로 남으면 판정이 서로 엇갈린다 — 실측에서 `라우팅 원리`는
        통과인데 `라우팅 기초`는 기각이 나왔다. 사용자가 보면 이해할 수 없다.
        """
        kept: list[Candidate] = []
        kept_vectors: list[list[float]] = []
        for candidate, vector in zip(candidates, vectors):
            norm = sum(x * x for x in vector) ** 0.5
            duplicate = False
            for seen in kept_vectors:
                seen_norm = sum(y * y for y in seen) ** 0.5
                dot = sum(x * y for x, y in zip(vector, seen))
                if norm and seen_norm and dot / (norm * seen_norm) >= settings.SUBTOPIC_DEDUP_SIM:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(candidate)
                kept_vectors.append(vector)
        if len(kept) < len(candidates):
            _log.info("선수 항목 중복 %d개 제거", len(candidates) - len(kept))
        return kept, kept_vectors

    def _nearest(
        self, vector: list[float], document_ids: list[uuid.UUID]
    ) -> tuple[Concept | None, float]:
        """코스 안에서 가장 가까운, **설명이 있는** 개념 하나.

        `search_concepts`를 그대로 쓴다 — 문서 경계를 넘고 `document_ids`로 코스
        범위를 자르는 조회가 이미 있다. 여기에 없는 건 "설명이 있는 것만" 조건
        하나뿐이라, 몇 개 넉넉히 받아서 파이썬에서 고른다.
        """
        for concept, similarity in self.repo.search_concepts(
            embedding=vector, limit=_NEAREST_FETCH, document_ids=document_ids
        ):
            if concept.segment_links:
                return concept, similarity
        return None, 0.0

    async def screen(self, course: Course) -> list[CoursePrereq]:
        """후보를 대조해 `course_prereqs`를 새로 만든다. 기존 행은 지운다.

        자료 구성이 바뀌면 판정이 통째로 달라지므로 증분 갱신하지 않는다.
        사용자 답(`known`)은 아직 24번이 없어 잃을 것이 없다 —
        24번이 들어오면 여기서 답을 보존하는 경로가 필요하다.
        """
        document_ids = [cd.document_id for cd in course.documents]
        documents = list(
            self.db.scalars(select(Document).where(Document.id.in_(document_ids)))
        )
        candidates = collect(documents)

        self.db.execute(
            delete(CoursePrereq).where(CoursePrereq.course_id == course.id)
        )
        if not candidates:
            _log.info("선수 후보 없음: %s", course.title)
            return []

        if not self._has_taught_concepts(document_ids):
            # 대조할 대상이 없다. 전부 통과시킨다 — 기각을 못 한다고 후보를
            # 버리면 정보가 사라진다.
            rows = [
                self._row(course.id, c, PrereqStatus.PASS, None, None)
                for c in candidates
            ]
            self.db.add_all(rows)
            return rows

        vectors = await solar_client.embed_batch(
            [c.item for c in candidates], purpose="query"
        )
        # 자료가 여럿이면 문서끼리도 항목이 겹친다(문서 안 중복은 12.5가 이미
        # 없앴다). 임베딩을 방금 만들었으니 여기서 한 번 더 거른다 — 추가
        # 호출이 없다.
        candidates, vectors = self._dedup(candidates, vectors)

        rows: list[CoursePrereq] = []
        gray: list[tuple[int, Candidate, Concept]] = []  # LLM에게 물을 것
        for candidate, vector in zip(candidates, vectors):
            concept, similarity = self._nearest(vector, document_ids)
            if similarity >= settings.PREREQ_REJECT_SIM:
                status = PrereqStatus.REJECTED
            elif similarity >= settings.PREREQ_JUDGE_SIM and concept is not None:
                status = PrereqStatus.GRAY
                gray.append((len(rows), candidate, concept))
            else:
                status = PrereqStatus.PASS
            rows.append(
                self._row(
                    course.id, candidate, status, similarity,
                    concept.name if concept else None,
                )
            )

        await self._judge_gray(course, documents, rows, gray)

        self.db.add_all(rows)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.status] = counts.get(row.status, 0) + 1
        _log.info(
            "선수 기각 검사: %s — 통과 %d · 회색 %d · 기각 %d (LLM 판정 %d)",
            course.title, counts.get("pass", 0), counts.get("gray", 0),
            counts.get("rejected", 0), len(gray),
        )
        return rows

    async def _judge_gray(
        self,
        course: Course,
        documents: list[Document],
        rows: list[CoursePrereq],
        gray: list[tuple[int, Candidate, Concept]],
    ) -> None:
        """회색지대에 LLM 의견을 얹는다. **지우지는 못한다.**

        처음엔 LLM 판정으로 기각까지 시켰는데, 같은 항목이 실행마다 뒤집혔다:
        `라우팅 원리`가 한 번은 통과, 한 번은 기각. `TCP/IP 프로토콜 스택`·
        `HTTP/HTTPS`·`REST API 개념`처럼 AWS 슬라이드가 분명히 안 가르치는
        것까지 기각됐다.

        그래서 LLM은 pass와 gray만 가른다. 기각은 임베딩 0.75 이상만 — 그건
        `CIDR 표기법`(0.783)처럼 확실한 것들이고 흔들리지 않는다.

            LLM이 "자료가 설명해 준다"  →  gray  (화면에 뜨되 표시가 붙는다)
            LLM이 "선수 지식이다"       →  pass  (그냥 뜬다)

        비용이 비대칭이라 이렇게 둔다. 항목 하나가 더 뜨는 건 사용자가 한 번
        훑으면 되지만, 안 뜬 항목은 **물어볼 기회 자체가 사라진다.** 호출이
        실패해도 같은 이유로 통과 쪽에 둔다.
        """
        if not gray:
            return
        gray = gray[: settings.PREREQ_MAX_JUDGE]
        titles = list(
            self.db.scalars(
                select(DocTopic.title)
                .where(DocTopic.document_id.in_([d.id for d in documents]))
                .order_by(DocTopic.document_id, DocTopic.seq)
            )
        )
        field_name = next((d.field for d in documents if d.field), "")

        for start in range(0, len(gray), settings.PREREQ_JUDGE_BATCH_SIZE):
            batch = gray[start : start + settings.PREREQ_JUDGE_BATCH_SIZE]
            try:
                raw = await solar_client.generate_json(
                    prompts.build_prompt(
                        field=field_name,
                        topics=titles,
                        items=[c.item for _, c, _ in batch],
                    ),
                    system=prompts.SYSTEM,
                )
                covered = {
                    int(x) for x in (raw.get("covered") or [])
                    if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
                }
            except Exception as exc:  # noqa: BLE001 — 통과 쪽으로 둔다
                _log.warning("선수 회색지대 판정 실패 — 전부 통과: %s", exc)
                covered = set()

            for offset, (index, _, _) in enumerate(batch):
                rows[index].status = (
                    PrereqStatus.GRAY.value
                    if offset in covered
                    else PrereqStatus.PASS.value
                )

    @staticmethod
    def _row(
        course_id: uuid.UUID,
        candidate: Candidate,
        status: PrereqStatus,
        similarity: float | None,
        rejected_by: str | None,
    ) -> CoursePrereq:
        return CoursePrereq(
            course_id=course_id,
            subject=candidate.subject,
            item=candidate.item,
            why=candidate.why,
            seq=candidate.seq,
            ordered=candidate.ordered,
            status=status.value,
            similarity=similarity,
            # 통과한 항목에도 남긴다 — 문턱을 옮길 때 "얼마나 아슬아슬했나"를
            # 봐야 하고, 화면이 근거를 보여줄 수도 있다.
            rejected_by=rejected_by,
        )
