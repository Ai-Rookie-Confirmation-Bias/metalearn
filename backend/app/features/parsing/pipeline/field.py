"""12.5단계 — 분야 판정. Solar 2회 + 임베딩 1회.

"이 자료는 무슨 분야고, 펴기 전에 뭘 알아야 하는가"를 문서에 새긴다.

**왜 문서 소유인가.** 이 판정이 파이프라인에서 LLM이 흔들리는 유일한 지점이다.
문서에 붙여 두면 지문 재사용이 그대로 먹어서 같은 책은 누가 올리든 같은 판정을
받는다. 코스마다 다시 물으면 사람마다 다른 답이 나온다.

**왜 2회 부르고 합집합인가.** 처음엔 교집합으로 헛것을 거르려 했는데, 재보니
과목 이름은 임베딩으로 못 가른다. 결정적 반례:

    AWS 기본 개념   ↔ AWS 기본 서비스   (같은 것)  하위포함 0.540 · 이름만 0.806
    네트워크 보안 기초 ↔ 네트워크 기초      (다른 것)  하위포함 0.514 · 이름만 0.866

두 값이 완전히 겹친다. 이름만 쓰면 "네트워크"라는 공통 어휘에 붙고, 하위 항목을
넣으면 회차마다 하위가 달라 같은 과목이 떨어진다. 어느 쪽도 안 된다.

그래서 **교집합을 포기하고 합집합을 취한다.** 근거는 비용 비대칭이다:

  · 놓치면 복구가 안 된다 — 교집합으로 돌렸을 때 network의 `Linux 기초`가
    사라졌다. AWS 슬라이드는 리눅스를 전제하는데 물어볼 기회 자체가 없어진다.
  · 헛것은 뒤에서 걸린다 — 16'단계의 임베딩 기각 검사가 정답 21개로 21/21을
    받았고, 그래도 남으면 24번의 사용자 확인 화면이 거른다.

**검증된 필터가 뒤에 있는데 검증 안 되는 필터를 앞에 세울 이유가 없다.**

회차가 개수부터 다르다(pilgi 6개 vs 2개)는 것도 확인됐다. 이 질문에 대한 LLM의
출력은 애초에 안정적이지 않다. 2회는 재현성이 아니라 **회수율**을 위한 것이다.

판정 단위는 과목이 아니라 **하위 항목**이다(course_prereqs가 (subject, item)
단위). 그래서 중복 제거도 하위 항목 수준에서 한다 — 과목 이름이 좀 겹쳐도
문제가 안 된다.

여기서 거른 뒤에도 "그 책이 가르치는 것"이 남는다(정처기 필기에 `데이터베이스
기초`가 나오는데 목차 3번이 "데이터베이스 구축"). 그건 프롬프트로 완전히 못
막는다 — 16'단계가 코스의 실제 개념과 대조해 다시 거른다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.parsing.prompts import field as prompt

_log = logging.getLogger("uvicorn.error")


@dataclass
class Subject:
    """선수 과목 하나."""

    name: str
    why: str = ""
    subtopics: list[str] = dc_field(default_factory=list)
    # 하위 항목 사이 순서가 강제되는가. 보강 **단원**이냐 한 **꼭지**냐를 가른다.
    ordered: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "why": self.why,
            "subtopics": self.subtopics,
            "ordered": self.ordered,
        }



@dataclass
class FieldProbe:
    field: str = ""
    level: str = ""
    subjects: list[Subject] = dc_field(default_factory=list)
    # 되짚기용 — 회차별 원본. 판정이 이상할 때 어느 회차가 튀었는지 본다.
    runs: list[dict] = dc_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "level": self.level,
            "prereq_subjects": [s.as_dict() for s in self.subjects],
            "runs": self.runs,
        }


def _parse(raw: dict) -> tuple[str, str, list[Subject]]:
    """LLM 응답을 관대하게 읽는다.

    형식 이탈 흡수는 이 코드베이스의 일관된 방침이다(schemas._coerce_evidence
    참조). 과목 하나가 문자열로 와도 버리지 않는다.
    """
    subjects: list[Subject] = []
    for item in raw.get("prereq_subjects") or []:
        if isinstance(item, str):
            subjects.append(Subject(name=item.strip()))
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        subs = [
            str(s).strip()
            for s in (item.get("subtopics") or [])
            if isinstance(s, (str, int, float)) and str(s).strip()
        ]
        subjects.append(
            Subject(
                name=name,
                why=str(item.get("why") or "").strip(),
                subtopics=subs,
                ordered=bool(item.get("ordered")),
            )
        )
    return (
        str(raw.get("field") or "").strip(),
        str(raw.get("level") or "").strip(),
        subjects,
    )


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


async def _merge(runs: list[list[Subject]]) -> list[Subject]:
    """회차들의 합집합. 중복은 **하위 항목 수준**에서 없앤다.

    과목 이름으로 합치지 않는 이유는 모듈 주석에 있다 — 이름 유사도로는
    `AWS 기본 개념`↔`AWS 기본 서비스`(같음, 0.806)와 `네트워크 보안 기초`↔
    `네트워크 기초`(다름, 0.866)를 못 가른다.

    하위 항목은 다르다. 구체적인 명사구라 임베딩이 잘 듣고, 판정 단위이기도
    하다. 같은 뜻의 항목이 두 과목에 걸쳐 나오면 먼저 나온 쪽에 남긴다.
    """
    flat: list[tuple[Subject, str]] = []  # (소속 과목, 하위 항목)
    subjects: list[Subject] = []
    for run in runs:
        for source in run:
            merged = Subject(
                name=source.name, why=source.why, ordered=source.ordered
            )
            subjects.append(merged)
            for item in source.subtopics:
                flat.append((merged, item))

    if not flat:
        # 하위 항목이 하나도 없으면 과목 이름만으로 돌려준다. 흔치는 않다.
        return [s for s in subjects if s.name]

    vectors = await solar_client.embed_batch([item for _, item in flat], purpose="query")

    kept_vectors: list[list[float]] = []
    dropped = 0
    for (owner, item), vector in zip(flat, vectors):
        duplicate = any(
            _cosine(vector, seen) >= settings.SUBTOPIC_DEDUP_SIM
            for seen in kept_vectors
        )
        if duplicate:
            dropped += 1
            continue
        kept_vectors.append(vector)
        owner.subtopics.append(item)

    if dropped:
        _log.info("분야 판정 — 중복 하위 항목 %d개 제거", dropped)
    # 하위 항목이 전부 중복으로 빠진 과목은 이미 다른 과목이 담고 있다.
    return [s for s in subjects if s.subtopics]


async def probe(
    *,
    filename: str,
    topics: list[str],
    concepts: list[str],
    dangling: list[str],
    runs: int | None = None,
) -> FieldProbe:
    """분야와 선수 과목을 판정한다.

    선수 과목이 **하나도 없는 게 정상인 자료가 있다.** 정처기 필기처럼 밑바닥
    부터 다 가르치는 책이 그렇다(실측: 3개 이하). 빈 결과를 실패로 보지 않는다.
    """
    total = runs or settings.FIELD_PROBE_RUNS
    text = prompt.build_prompt(
        filename=filename, topics=topics, concepts=concepts, dangling=dangling
    )

    parsed: list[list[Subject]] = []
    fields: list[str] = []
    levels: list[str] = []
    raws: list[dict] = []
    for _ in range(total):
        raw = await solar_client.generate_json(text, system=prompt.SYSTEM)
        name, level, subjects = _parse(raw)
        raws.append(raw)
        if name:
            fields.append(name)
        if level:
            levels.append(level)
        parsed.append(subjects)

    kept = await _merge(parsed) if parsed else []
    result = FieldProbe(
        field=fields[0] if fields else "",
        level=levels[0] if levels else "",
        subjects=kept,
        runs=raws,
    )
    _log.info(
        "분야 판정: %r — 선수 과목 %d개 (회차별 %s)",
        result.field, len(kept), [len(p) for p in parsed],
    )
    return result
