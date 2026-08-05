"""7단계 — 목차 분류. ⭐ 이 파이프라인의 핵심. Solar 1~2회.

기존 코드에는 대응물이 없다. 기존은 정제 스캔이 뽑은 '파트'를 챕터로 썼는데
방향이 반대다.

  기존 — 개념을 뽑고, 개념이 원문을 가리킨다.
         아무도 안 가리키는 원문이 생겨도 **알 방법이 없다.**

  신규 — 조각을 전부 목차에 분류한다.
         조각 40개를 넣었으면 목차별 합계도 40개여야 한다.
         **누락이 산술적으로 걸린다.**

원문은 한 글자도 건드리지 않는다. 라벨만 붙인다.

방어 3중:
  ① 응답 형태를 관대하게 읽는다 — 키 이름과 숫자 타입이 실행마다 흔들린다
  ② 미배정 조각은 앞 조각의 목차로 회수한다
  ③ 그래도 못 쓰겠으면 순서 기반으로 균등 분할한다 (원문은 절대 안 버린다)
"""
from __future__ import annotations

import logging

from app.core.llm.solar import solar_client
from app.features.parsing.prompts import topics as prompt
from app.features.parsing.schemas import Segment, TopicAssignment, TopicDraft

_log = logging.getLogger("uvicorn.error")

# 프롬프트 길이 상한(문자). 넘으면 조각 미리보기를 줄여 다시 만든다.
_MAX_PROMPT_CHARS = 60_000
_MIN_PREVIEW_CHARS = 60

# 응답 키 흔들림 흡수. 실측에서 LLM이 segments 대신 다른 이름을 쓰는 일이 있다.
_TOPICS_KEYS = ("topics", "목차", "result", "items")
_SEGMENTS_KEYS = ("segments", "segment_seqs", "segment_ids", "indices", "ids", "조각")
_TITLE_KEYS = ("title", "name", "제목")


async def classify(
    segments: list[Segment],
    max_topics: int,
    toc: list[dict[str, object]] | None = None,
    page_sections: dict[int, str] | None = None,
    body_sections: list[dict[str, object]] | None = None,
) -> TopicAssignment:
    """조각들을 목차로 분류한다.

    **자료가 답을 알고 있으면 LLM을 부르지 않는다.** 우선순위:

      ① 본문 단원 표기 — "1과목 소프트웨어 설계". 경계가 요소 번호라 가장 정확.
      ② 러닝 헤더 — 페이지마다 단원명. 페이지 단위라 한 칸 밀릴 수 있다.
      ③ 목차 페이지 — 인쇄 페이지가 PDF 페이지와 어긋날 수 있다(실측: 3 차이).
      ④ LLM 2패스 — 위 셋이 다 없을 때만.

    실측: ③만 쓰면 앞쪽 조각마다 목차를 하나씩 만들고 뒤쪽 8개를 엉뚱한
    목차에 몰아넣었다. 자료에 답이 적혀 있는데 지어내게 시킨 탓이다.
    """
    if not segments:
        raise ValueError("분류할 조각이 없습니다.")

    assignment = _from_body_sections(segments, body_sections or [])
    if assignment is None:
        assignment = _from_page_sections(segments, page_sections or {})
    if assignment is None and toc:
        assignment = _from_toc(segments, toc)
    if assignment is not None:
        _verify(assignment)
        _log_result(assignment)
        return assignment

    # ③ LLM — 2패스. 짓기와 배정을 나눈다.
    assignment = await _two_pass(segments, max_topics)
    if assignment is None or not _is_balanced(assignment):
        if assignment is not None:
            _log.warning("목차 분포가 치우침 — 다시 짓습니다: %s", _shape(assignment))
        retry = await _two_pass(segments, max_topics)
        # 더 고르게 나뉜 쪽을 남긴다. 재시도가 더 나쁠 수도 있다
        # (실측: [3,3,3,4,2,3] → [7,1,2,1,1,1,1,1,1,2]).
        if retry is not None and (
            assignment is None or _imbalance(retry) < _imbalance(assignment)
        ):
            assignment = retry

    if assignment is None:
        # 2패스가 두 번 다 안 되면 단일 호출 경로로 내려간다.
        topics = await _ask(segments, max_topics) or _fallback(segments, max_topics)
        assignment = TopicAssignment(topics=topics, total_segments=len(segments))

    if not assignment.is_complete:
        await _assign_orphans(assignment, segments)
    if not assignment.is_complete:
        _repair(assignment, segments)

    _enforce_contiguity(assignment)
    _verify(assignment)
    if not _is_balanced(assignment):
        _log.warning("목차 분포가 여전히 치우침: %s — 그대로 진행", _shape(assignment))
    _log_result(assignment)
    return assignment


# ── 2패스: 짓기 → 배정 ──────────────────────────────────────────


async def _two_pass(
    segments: list[Segment], max_topics: int
) -> TopicAssignment | None:
    """1패스로 단원을 짓고, 2패스로 전체 조각을 배정한다. Solar 2회."""
    try:
        outline = await solar_client.generate_json(
            prompt.build_outline_prompt(segments, max_topics), system=prompt.SYSTEM
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("단원 생성 실패: %s", exc)
        return None

    titles = [
        str(t).strip()[:200]
        for t in (outline.get("topics") or [])
        if isinstance(t, str) and str(t).strip()
    ][:max_topics]
    if len(titles) < 2:
        _log.warning("단원 생성 실패: 나온 단원 %d개", len(titles))
        return None

    _log.info(
        "단원 생성(%s · %s): %s",
        outline.get("source"), outline.get("subject"), titles,
    )

    try:
        raw = await solar_client.generate_json(
            prompt.build_assign_prompt(segments, titles, full=True),
            system=prompt.SYSTEM,
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("단원 배정 실패: %s", exc)
        return None

    buckets: dict[int, list[int]] = {}
    valid = {s.seq for s in segments}
    for item in raw.get("assignments") or []:
        if not isinstance(item, dict):
            continue
        seq, index = _as_seq(item.get("segment")), _as_seq(item.get("topic"))
        if seq is None or index is None or seq not in valid:
            continue
        if not 0 <= index < len(titles) or any(seq in v for v in buckets.values()):
            continue
        buckets.setdefault(index, []).append(seq)

    topics = [
        TopicDraft(seq=n, title=titles[i], segment_seqs=sorted(buckets[i]))
        for n, i in enumerate(sorted(buckets))
    ]
    if not topics:
        return None
    return TopicAssignment(topics=topics, total_segments=len(segments))


# ── 분포 검증 ───────────────────────────────────────────────────

# 한 단원이 이 비율을 넘게 가져가면 나눈 게 아니라 몰아넣은 것이다.
_MAX_TOPIC_SHARE = 0.40
# 조각 1개짜리 단원이 이 비율을 넘으면 단원이 아니라 소제목을 나열한 것이다.
# 실측 3회: [3,3,3,4,2,3] 0/6 · [7,1,2,1,1,1,1,1,1,2] 7/10 · [2,3,2,1,2,3,1,2,1,1] 4/10.
# 0.50으로 두면 세 번째(40%)가 통과하는데 목차로 쓰기엔 부실하다.
_MAX_SINGLETON_RATIO = 0.30


def _imbalance(assignment: TopicAssignment) -> float:
    """치우친 정도. 낮을수록 좋다. 두 후보 중 나은 쪽을 고를 때 쓴다."""
    if not assignment.topics:
        return 99.0
    total = assignment.total_segments or 1
    sizes = [len(t.segment_seqs) for t in assignment.topics]
    max_share = max(sizes) / total
    singleton_ratio = sum(1 for n in sizes if n <= 1) / len(sizes)
    return max_share + singleton_ratio


def _is_balanced(assignment: TopicAssignment) -> bool:
    """단원답게 나뉘었는가.

    개수만 세는 검산은 이걸 못 잡는다. 실측: 조각 19개가
    [6,1,2,1,1,1,1,1,1,4]로 나뉘어 검산은 통과했지만, 첫 단원이 32%를
    가져가고 1개짜리가 6개라 목차 구실을 못 했다.
    """
    if len(assignment.topics) < 2:
        return False
    total = assignment.total_segments or 1
    sizes = [len(t.segment_seqs) for t in assignment.topics]
    if max(sizes) / total > _MAX_TOPIC_SHARE:
        return False
    singletons = sum(1 for n in sizes if n <= 1)
    return singletons / len(sizes) <= _MAX_SINGLETON_RATIO


def _shape(assignment: TopicAssignment) -> str:
    return str([len(t.segment_seqs) for t in assignment.topics])


def _log_result(assignment: TopicAssignment) -> None:
    _log.info(
        "목차 분류: 조각 %d개 → 목차 %d개 %s",
        assignment.total_segments,
        len(assignment.topics),
        [f"{t.title}({len(t.segment_seqs)})" for t in assignment.topics],
    )


# ── 자료의 목차로 배정 (호출 0회) ───────────────────────────────


def _from_body_sections(
    segments: list[Segment], markers: list[dict[str, object]]
) -> TopicAssignment | None:
    """본문 단원 표기로 조각을 가른다. 경계가 요소 번호라 가장 정확하다.

    러닝 헤더는 페이지 단위라 단원이 페이지 중간에서 바뀌면 한 칸 밀린다.
    본문 표기는 그 지점을 정확히 짚는다.
    """
    if not markers:
        return None

    bounds = [(int(m["index"]), f"{m['no']}. {m['title']}") for m in markers]
    buckets: dict[int, list[int]] = {}

    for segment in segments:
        start = segment.element_from
        if start is None:
            return None
        index = 0
        for i, (element_index, _) in enumerate(bounds):
            if start >= element_index:
                index = i
            else:
                break
        buckets.setdefault(index, []).append(segment.seq)

    used = sorted(buckets)
    if len(used) < 2:
        _log.warning("본문 단원 배정 실패: 조각이 단원 %d개에만 걸림", len(used))
        return None

    topics = [
        TopicDraft(seq=n, title=bounds[i][1], segment_seqs=sorted(buckets[i]))
        for n, i in enumerate(used)
    ]
    _log.info("목차 배정: 본문 단원 표기 %d개 사용 (Solar 0회)", len(topics))
    return TopicAssignment(topics=topics, total_segments=len(segments))


def _from_page_sections(
    segments: list[Segment], page_sections: dict[int, str]
) -> TopicAssignment | None:
    """러닝 헤더의 단원명으로 조각을 가른다. 추론 없음.

    조각이 단원 경계에 걸치면 시작 페이지의 단원에 넣는다 — 조각을 쪼개면
    원문이 잘리고, 조각은 이미 제목 경계로 끊겨 있어 걸치는 폭이 작다.
    """
    if not page_sections:
        return None

    # JSONB를 거치면 키가 문자열이 된다.
    sections = {int(page): title for page, title in page_sections.items()}
    pages = sorted(sections)
    # 헤더가 붙기 전 구간(표지·목차·머리말)은 첫 단원에 합친다.
    # 여기서 포기하면 러닝 헤더라는 가장 정확한 근거를 통째로 버리게 된다.
    first_title = sections[pages[0]]

    order: list[str] = []
    buckets: dict[str, list[int]] = {}

    for segment in sorted(segments, key=lambda s: s.seq):
        page = segment.page_from
        if page is None:
            return None
        # 그 페이지에 헤더가 없으면(단원 시작 페이지 등) 가장 가까운 앞 페이지를 본다.
        title = sections.get(page) or next(
            (sections[p] for p in reversed(pages) if p <= page), first_title
        )
        if title not in buckets:
            buckets[title] = []
            order.append(title)
        buckets[title].append(segment.seq)

    if len(order) < 2:
        _log.warning("러닝 헤더 배정 실패: 단원이 %d개뿐 — 다음 근거로", len(order))
        return None

    topics = [
        TopicDraft(seq=i, title=title, segment_seqs=sorted(buckets[title]))
        for i, title in enumerate(order)
    ]
    _log.info("목차 배정: 러닝 헤더 기준 %d개 단원 (Solar 0회)", len(topics))
    return TopicAssignment(topics=topics, total_segments=len(segments))


def _from_toc(
    segments: list[Segment], toc: list[dict[str, object]]
) -> TopicAssignment | None:
    """목차 항목의 시작 페이지로 조각을 가른다.

    각 조각은 시작 페이지가 자기 페이지 이하인 마지막 목차 항목에 속한다.
    조각이 목차 경계에 걸치면(예: p.5-6, 경계 p.6) 시작 페이지 기준으로
    앞 목차에 넣는다 — 조각을 쪼개면 원문이 잘린다.

    페이지 정보가 없거나 결과가 한 목차로 뭉치면 None을 돌려 LLM으로 넘긴다.
    """
    if any(s.page_from is None for s in segments):
        _log.info("목차 배정 건너뜀: 조각에 페이지 정보가 없음")
        return None

    entries = sorted(toc, key=lambda e: int(e["page"]))
    buckets: dict[int, list[int]] = {i: [] for i in range(len(entries))}

    for segment in segments:
        page = int(segment.page_from or 0)
        index = 0
        for i, entry in enumerate(entries):
            if page >= int(entry["page"]):
                index = i
            else:
                break
        buckets[index].append(segment.seq)

    used = [(i, seqs) for i, seqs in buckets.items() if seqs]
    if len(used) < 2:
        _log.warning("목차 배정 실패: 조각이 목차 %d개에만 걸림 — LLM으로", len(used))
        return None

    topics = [
        TopicDraft(seq=n, title=str(entries[i]["title"]), segment_seqs=sorted(seqs))
        for n, (i, seqs) in enumerate(used)
    ]
    _log.info("목차 배정: 자료의 목차 %d개 사용 (Solar 0회)", len(topics))
    return TopicAssignment(topics=topics, total_segments=len(segments))


# ── 연속성 강제 ─────────────────────────────────────────────────


def _enforce_contiguity(assignment: TopicAssignment) -> None:
    """목차는 연속된 조각을 묶어야 한다.

    교재는 순서대로 쓰여 있으므로 목차 하나가 조각 [0, 13, 14, …, 20]처럼
    떨어진 구간을 갖는 건 구조적으로 틀렸다. 개수만 세는 검산은 이걸 통과시킨다
    (실측: 1페이지 조각과 15~22페이지 조각이 한 목차에 묶였는데 검산 통과).

    떨어진 조각은 **번호가 인접한 목차**로 옮긴다. 원문은 하나도 안 버린다.
    """
    if len(assignment.topics) < 2:
        return

    # 각 목차의 대표 위치 = 조각 번호의 중앙값
    def anchor(topic: TopicDraft) -> float:
        seqs = sorted(topic.segment_seqs)
        return seqs[len(seqs) // 2] if seqs else 0.0

    order = sorted(assignment.topics, key=anchor)
    moved = 0

    for topic in list(order):
        seqs = sorted(topic.segment_seqs)
        if len(seqs) < 2:
            continue
        # 중앙값에서 연속으로 이어지는 구간만 남긴다.
        center = seqs.index(seqs[len(seqs) // 2])
        keep = {seqs[center]}
        for i in range(center - 1, -1, -1):
            if seqs[i] + 1 in keep:
                keep.add(seqs[i])
            else:
                break
        for i in range(center + 1, len(seqs)):
            if seqs[i] - 1 in keep:
                keep.add(seqs[i])
            else:
                break

        strays = [s for s in seqs if s not in keep]
        if not strays:
            continue
        topic.segment_seqs = sorted(keep)
        for seq in strays:
            target = min(
                (t for t in order if t is not topic),
                key=lambda t: abs(anchor(t) - seq),
            )
            target.segment_seqs.append(seq)
            moved += 1

    for topic in assignment.topics:
        topic.segment_seqs.sort()
    # 조각이 하나도 안 남은 목차는 버린다.
    assignment.topics = [t for t in assignment.topics if t.segment_seqs]
    assignment.topics.sort(key=anchor)
    for i, topic in enumerate(assignment.topics):
        topic.seq = i

    if moved:
        _log.warning(
            "목차 연속성 보정: 떨어진 조각 %d개를 인접 목차로 이동", moved
        )


async def _ask(segments: list[Segment], max_topics: int) -> list[TopicDraft]:
    raw = await solar_client.generate_json(
        _build_prompt(segments, max_topics), system=prompt.SYSTEM
    )
    topics = _sanitize(raw, segments, max_topics)
    if not topics:
        _log.warning("목차 분류 응답에서 목차를 못 뽑음. 원본: %.500s", raw)
    return topics


def _build_prompt(segments: list[Segment], max_topics: int) -> str:
    """프롬프트가 상한을 넘으면 조각 미리보기를 줄여가며 다시 만든다.

    조각을 배치로 쪼개지 않는 이유: 목차 10개 이내는 **문서 전체**에 걸린
    제약이라, 배치로 나누면 배치마다 목차 10개가 나와 버린다.
    """
    preview = prompt.PREVIEW_CHARS
    while True:
        text = prompt.build_prompt(segments, max_topics, preview_chars=preview)
        if len(text) <= _MAX_PROMPT_CHARS:
            return text
        if preview <= _MIN_PREVIEW_CHARS:
            _log.warning(
                "목차 분류 프롬프트가 상한 초과: %d자 (조각 %d개) — 그대로 진행",
                len(text), len(segments),
            )
            return text
        preview = max(_MIN_PREVIEW_CHARS, preview // 2)


def _first(source: dict, keys: tuple[str, ...]) -> object:
    for key in keys:
        if key in source:
            return source[key]
    return None


def _as_seq(value: object) -> int | None:
    """조각 번호를 관대하게 읽는다.

    실측: 프롬프트가 조각을 "[0] p.1 제목" 형태로 보여주니 LLM이 번호를
    "[0]" 문자열로 그대로 돌려준다. 예측 가능한 패턴이라 여기서 흡수한다 —
    안 그러면 멀쩡한 응답을 버리고 재시도 1회를 그냥 날린다.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        digits = value.strip().strip("[]()#<> \t").lstrip("#")
        if digits.isdigit():
            return int(digits)
    return None


def _sanitize(raw: dict, segments: list[Segment], max_topics: int) -> list[TopicDraft]:
    """LLM 응답을 신뢰하지 않고 걸러낸다.

    - 존재하지 않는 조각 번호는 버린다
    - 한 조각이 여러 목차에 배정되면 **처음 것만** 남긴다
    - 목차가 상한을 넘으면 뒤쪽을 잘라낸다 (조각은 _repair가 회수한다)
    - 조각이 하나도 없는 목차는 버린다
    """
    items = _first(raw, _TOPICS_KEYS)
    if not isinstance(items, list):
        return []

    valid_seqs = {s.seq for s in segments}
    seen: set[int] = set()
    topics: list[TopicDraft] = []

    for item in items:
        if not isinstance(item, dict) or len(topics) >= max_topics:
            continue
        title = str(_first(item, _TITLE_KEYS) or "").strip()[:200]
        if not title:
            continue

        raw_seqs = _first(item, _SEGMENTS_KEYS)
        seqs: list[int] = []
        for value in raw_seqs if isinstance(raw_seqs, list) else []:
            seq = _as_seq(value)
            if seq is None or seq not in valid_seqs or seq in seen:
                continue
            seen.add(seq)
            seqs.append(seq)

        if seqs:
            topics.append(
                TopicDraft(seq=len(topics), title=title, segment_seqs=sorted(seqs))
            )

    return topics


def _fallback(segments: list[Segment], max_topics: int) -> list[TopicDraft]:
    """LLM을 못 쓸 때의 순서 기반 균등 분할.

    품질은 떨어지지만 **원문은 한 조각도 잃지 않는다.** 목차 이름을 잘못
    붙이는 것과 원문을 잃는 것은 피해가 비교가 안 된다.
    """
    count = min(max_topics, len(segments))
    size = -(-len(segments) // count)  # 올림 나눗셈

    topics: list[TopicDraft] = []
    for i in range(0, len(segments), size):
        group = segments[i : i + size]
        title = next((s.heading for s in group if s.heading), None)
        topics.append(
            TopicDraft(
                seq=len(topics),
                title=title or f"구간 {len(topics) + 1}",
                segment_seqs=[s.seq for s in group],
            )
        )

    _log.warning(
        "목차 분류 폴백: LLM 응답을 두 번 다 못 씀 → 순서대로 %d개 구간으로 분할",
        len(topics),
    )
    return topics


def _orphans(assignment: TopicAssignment, segments: list[Segment]) -> list[Segment]:
    assigned = {seq for topic in assignment.topics for seq in topic.segment_seqs}
    return [s for s in segments if s.seq not in assigned]


async def _assign_orphans(
    assignment: TopicAssignment, segments: list[Segment]
) -> None:
    """빠진 조각만 모아 한 번 더 묻는다. Solar 1회."""
    if not assignment.topics:
        return
    orphans = _orphans(assignment, segments)
    if not orphans:
        return

    _log.warning("목차 미배정 조각 %d개 — 2차 배정 요청", len(orphans))
    try:
        raw = await solar_client.generate_json(
            prompt.build_assign_prompt(
                orphans, [t.title for t in assignment.topics]
            ),
            system=prompt.SYSTEM,
        )
    except Exception as exc:  # noqa: BLE001 — 실패해도 _repair가 받는다
        _log.warning("2차 배정 실패: %s", exc)
        return

    orphan_seqs = {s.seq for s in orphans}
    placed = 0
    for item in raw.get("assignments") or []:
        if not isinstance(item, dict):
            continue
        seq = _as_seq(item.get("segment"))
        index = _as_seq(item.get("topic"))
        if seq is None or index is None:
            continue
        if seq not in orphan_seqs or not 0 <= index < len(assignment.topics):
            continue
        assignment.topics[index].segment_seqs.append(seq)
        orphan_seqs.discard(seq)
        placed += 1

    for topic in assignment.topics:
        topic.segment_seqs.sort()
    _log.info("2차 배정: %d개 배정, %d개 남음", placed, len(orphan_seqs))


def _repair(assignment: TopicAssignment, segments: list[Segment]) -> None:
    """배정되지 않은 조각을 회수한다.

    검산의 목적은 '누락을 발견하는 것'이지 '파이프라인을 죽이는 것'이 아니다.
    조각은 원본 순서를 가지고 있으므로, 미배정 조각은 **바로 앞 조각이 속한
    목차**에 넣으면 원문 흐름을 해치지 않는다. 앞이 없으면 첫 목차로 보낸다.

    회수는 조용히 하지 않는다 — 몇 개를 어디로 보냈는지 로그에 남긴다.
    """
    if not assignment.topics:
        return

    owner: dict[int, TopicDraft] = {
        seq: topic for topic in assignment.topics for seq in topic.segment_seqs
    }
    orphans = [s.seq for s in segments if s.seq not in owner]
    if not orphans:
        return

    for seq in sorted(orphans):
        target = next(
            (owner[prev] for prev in range(seq - 1, -1, -1) if prev in owner),
            assignment.topics[0],
        )
        target.segment_seqs.append(seq)
        owner[seq] = target

    for topic in assignment.topics:
        topic.segment_seqs.sort()

    _log.warning(
        "목차 미배정 조각 %d개 회수: %s (LLM 응답이 조각을 빠뜨림)",
        len(orphans), orphans[:20],
    )


def _verify(assignment: TopicAssignment) -> None:
    """검산 — 이게 원문 무손실의 유일한 보증이다."""
    if not assignment.topics:
        raise ValueError("목차 분류 실패: 목차가 하나도 나오지 않았습니다.")
    if not assignment.is_complete:
        raise ValueError(
            f"목차 분류 검산 실패: 조각 {assignment.total_segments}개 중 "
            f"{assignment.assigned_count}개만 배정됐습니다."
        )
