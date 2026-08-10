"""드래그해서 물어보기 — **그 화면을 만든 원문을 그대로 근거로 쓴다.**

근거가 두 층이고, 순서가 곧 신뢰도다:

    ① 이 화면의 **교재 원문**      그 설명을 생성할 때 쓴 바로 그 조각
    ② 이 화면의 **개념 정의**      파싱이 원문에서 뽑아 둔 것
    ③ 다른 자리에서 찾은 것        임베딩 검색 — 다른 단원, 📕 도서관의 다른 책

①이 주 근거다. 공짜고, 정확하고, 항상 있다. 찾을 필요가 없다 — **이미 서버에
들고 있다**(`Section.source`, 중앙값 362자). ③은 "더 볼 곳"이지 주 근거가 아니다.

## 화면에서 긁어온 문단을 근거로 쓰지 않는다

처음엔 프론트가 DOM에서 긁어온 문단만 넘겼는데, 학습 화면 본문은 **생성된
설명**이다. 그걸 근거로 다시 생성하면 AI가 쓴 글 위에 AI가 쓰는 꼴이고,
"AI가 지어낸 해설이 아니라 교재의 그 문장"이라는 근거가 무너진다.

그 문단은 지금도 넘어오지만 **역할이 다르다** — 학습자가 어느 대목을 보고 있었나를
알려줄 뿐이라 프롬프트에서도 그렇게 라벨을 단다. 사실의 출처는 ①이다.

## 어디서 찾는가 — 여기가 사고 나기 쉬운 자리다

`search_concepts`는 `document_ids`를 안 주면 **DB의 모든 문서**를 뒤진다.
남이 올린 사적인 교재까지 포함이다. 그대로 쓰면 드래그 한 번으로 남의 책
문장이 화면에 뜬다. 그래서 범위를 두 가지로 못 박는다:

    지금 읽는 문서   내 것이니 당연히 된다
    공개 문서        도서관에 꽂힌 책. 누구에게나 보이는 것들

`[보강]` 생성 자료는 뺀다 — 원문이 없는 명세라 "교재의 그 문장"으로 못 쓴다.

## 숙련도에 기록하지 않는다

물어본 건 문항을 틀린 게 아니라 **다시 본 것**이다. 정답률에 섞으면 오측정이다
(`SectionPage`의 ⚡ 다시 설명이 같은 이유로 기록을 안 남긴다).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.parsing.models import Document, DocStatus
from app.features.parsing.service import ParsingService

_log = logging.getLogger("uvicorn.error")

# 원문을 근거로 붙일 최저 유사도.
#
# 『점프 투 파이썬』(개념 158개)에 대고 실측했다. 맞는 것과 딴것이 안 겹친다:
#
#     0.728  부동소수점 오차   → 부동 소수점 한계      맞음
#     0.696  난수 생성과 시드   → 난수                맞음
#     0.656  평균과 중앙값     → 중앙값              맞음
#     ──────────────────── 0.58 ────────────────────
#     없음   종속 변수와 독립 변수                    이 책에 없는 주제
#     없음   스택과 큐                              이 책에 없는 주제
#     없음   오늘 점심                              말도 안 되는 질의
#
# 딴 주제를 끌어도 억지 근거가 안 붙는다. 이웃한 값들과도 결이 맞는다 —
# 개념끼리는 0.70 미만이 못 쓸 구간이고(link.py) 선수 항목↔개념은 0.65다
# (supply). 여기는 "끌어 놓은 몇 글자"↔개념이라 질의가 더 짧고 거칠어 낮다.
#
# 낮춰서 생기는 손해가 작은 자리이기도 하다. 틀린 근거가 붙어도 원문과 출처와
# 유사도가 화면에 그대로 찍혀 학습자가 바로 안다. 반대로 높이면 "교재에 있는데
# 못 찾는" 쪽인데 그건 아무 흔적도 안 남는다.
_CITE_SIM = 0.58

# 근거는 셋까지. 더 붙이면 프롬프트가 길어지고 화면도 읽을 게 아니라 훑을 게 된다.
_MAX_SOURCES = 3

# 교재 원문 상한. 절별 원문은 중앙값 362자라 대개 통째로 들어가지만, 개념이
# 많이 묶인 화면은 길어진다. 잘라도 앞쪽이 그 화면의 주제다.
_MAX_PASSAGE = 2000

# 이어묻기 이력. 길게 물려도 앞쪽은 이미 답에 녹아 있어 값이 적고 토큰만 는다.
_MAX_HISTORY = 6


@dataclass
class Source:
    """교재에서 찾은 근거 한 줄. **원문 그대로**이지 요약이 아니다."""

    document_id: uuid.UUID
    filename: str
    concept: str
    definition: str
    topic_title: str | None
    page: str | None
    similarity: float
    # 도서관 책인가(내가 지금 읽는 자료가 아닌). 화면이 출처를 다르게 말한다.
    shared: bool


@dataclass
class Answer:
    text: str
    sources: list[Source] = field(default_factory=list)


def _citable_document_ids(db: Session, current: uuid.UUID | None) -> list[uuid.UUID]:
    """근거로 인용해도 되는 문서. **범위를 넓히지 않는다** — 모듈 주석 참조."""
    rows = db.scalars(
        select(Document.id).where(
            Document.status == DocStatus.READY.value,
            Document.visibility == "public",
            Document.source_format != "generated",
        )
    ).all()
    ids = list(rows)
    if current is not None and current not in ids:
        ids.append(current)
    return ids


def _as_uuid(value: str) -> uuid.UUID | None:
    """커리큘럼 문서 id는 파싱 문서 UUID이거나 픽스처 슬러그다."""
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


async def find_sources(
    db: Session, *, doc_id: str, selection: str, covered: set[str] | None = None
) -> list[Source]:
    """끌어 놓은 말이 **다른 자리**에도 있나 찾는다. 없으면 빈 목록 — 그것도 답이다.

    `covered`는 이 화면이 이미 가르치는 개념 이름이다. 같은 문서에서 그 이름이
    걸리면 버린다 — 그건 새 정보가 아니라 ①(교재 원문)의 되풀이다. **다른
    문서에서 걸린 같은 이름은 남긴다.** 『선형대수』에도 같은 개념이 있다는 게
    바로 여기서 나오는 값이라, 이름이 같다고 지우면 그 값이 사라진다.
    """
    current = _as_uuid(doc_id)
    document_ids = _citable_document_ids(db, current)
    if not document_ids:
        return []

    try:
        hits = await ParsingService(db).search_concepts(
            selection,
            limit=_MAX_SOURCES,
            document_ids=document_ids,
            min_sim=_CITE_SIM,
        )
    except Exception as exc:  # noqa: BLE001 — 근거를 못 찾아도 설명은 해야 한다
        _log.warning("[ask] 근거 검색 실패 — 근거 없이 간다: %s", exc)
        return []

    already = covered or set()
    sources: list[Source] = []
    for hit in hits:
        if hit.document_id == current and hit.name in already:
            continue
        pages = [e.page_from for e in hit.evidence if e.page_from]
        sources.append(
            Source(
                document_id=hit.document_id,
                filename=hit.filename,
                concept=hit.name,
                definition=hit.definition or "",
                topic_title=hit.topic_title,
                page=f"p.{min(pages)}" if pages else None,
                similarity=round(hit.similarity, 3),
                shared=current is None or hit.document_id != current,
            )
        )
    return sources


def build_prompt(
    *,
    selection: str,
    context: str,
    section_title: str,
    concepts: list[tuple[str, str]],
    passage: str,
    page: str,
    sources: list[Source],
    history: list[tuple[str, str]],
    question: str | None,
) -> str:
    """설명 프롬프트. **교재 원문이 맨 앞이다.**

    순서가 곧 우선순위다. 근거를 뒤에 붙이면 모델이 앞의 지시를 따라가면서
    근거를 장식으로 쓴다(`agents/explanation`에서 겪은 것과 같은 밀어냄이다).

    조건은 적게 준다. 설명 생성은 실측에서 4/4로 안전했고 그때 조건은
    "거짓말하지 말라" 하나였다.
    """
    lines = [
        "너는 지금 학습자가 읽고 있는 교재를 함께 보는 튜터다.",
        "",
        f"[학습자가 읽는 화면] {section_title}",
    ]

    grounded = bool(passage.strip())
    if grounded:
        where = f" ({page})" if page else ""
        lines += [
            "",
            f"[이 화면의 교재 원문{where} — **사실은 여기서 가져온다**]",
            passage.strip()[:_MAX_PASSAGE],
        ]
    if concepts:
        lines += ["", "[이 화면의 개념 — 교재에서 뽑아 둔 정의]"]
        for key, definition in concepts:
            lines.append(f"- {key}: {definition}" if definition else f"- {key}")

    if context:
        # ⚠️ 이건 **생성된 설명**이다. 사실의 출처가 아니라 "어느 대목을 보고
        #    있었나"일 뿐이라, 라벨로 분명히 갈라 둔다.
        lines += ["", "[학습자가 보고 있던 대목 — 위치 참고용, 사실 근거 아님]", context.strip()]

    lines += ["", f"[학습자가 모르겠다고 짚은 말] {selection.strip()}"]

    if sources:
        lines += ["", "[다른 자리에서 찾은 같은 개념 — 더 볼 곳]"]
        for i, s in enumerate(sources, 1):
            at = " · ".join(filter(None, [s.filename, s.topic_title, s.page]))
            lines.append(f"{i}. {s.concept} ({at})")
            if s.definition:
                lines.append(f"   {s.definition}")

    if not grounded and not sources:
        lines += [
            "",
            "[근거] 교재에서 관련 설명을 찾지 못했다.",
            "일반적인 지식으로 설명하되, **교재에 없는 내용이라고 먼저 밝혀라.**",
        ]

    for role, content in history[-_MAX_HISTORY:]:
        lines += ["", f"[{'학습자' if role == 'user' else '너의 답'}] {content}"]

    if question:
        lines += ["", f"[학습자의 이어지는 질문] {question.strip()}"]
        lines += ["", "이 질문에 학습자에게 직접 답하라."]
    else:
        lines += ["", "짚은 말이 무슨 뜻인지 학습자에게 직접 설명하라."]

    lines += ["", "규칙:"]
    if grounded:
        # 원문이 있으면 그게 **사실**의 출처라고 못 박는다. 안 그러면 모델이
        # 아는 것을 먼저 쓰고 원문은 장식으로 쓴다.
        #
        # ⚠️ "사실"이라고 쓰는 게 중요하다. 전에는 "원문에 없는 건 덧붙이지
        #    않는다"였는데, 그러면 **비유와 예시까지 금지된다.** 아래 이어묻기
        #    규칙과 정면으로 부딪힌다.
        lines.append("- **사실은 위 교재 원문에서 가져온다.** 원문에 없는 사실을 지어내지 않는다.")
        lines.append("- 원문으로 부족해 밖의 지식을 쓸 때는 그렇다고 밝힌다.")

    if question:
        # 실측: "좀 더 쉽게 설명해줘"에 **한 글자도 안 틀리고 같은 답**이 나왔다.
        #
        # 규칙이 서로 밀어낸 것이다. "원문에 없는 건 덧붙이지 마라"가 걸려
        # 있으면 쉬운 말·비유·예시는 전부 원문 밖이라 쓸 수 없고, 모델이 고를
        # 수 있는 가장 안전한 답은 **아까 한 말을 그대로 다시 하는 것**이 된다.
        #
        # `agents/explanation`이 같은 걸 겪었다 — "원문에 있는 사실만 써라"와
        # "비유를 먼저 놓아라"가 충돌해 모델이 원문 복창을 택했다. 그래서 거기도
        # 비유를 별도 필드로 떼고 "여기서는 원문 밖을 써도 된다"고 명시했다.
        #
        # **사실**과 **말하는 방식**을 갈라야 한다. 사실은 원문을 지키고,
        # 방식은 열어 준다.
        lines += [
            "- **앞에 한 말을 되풀이하지 않는다.** 다시 물었다는 건 그 설명이 안 통했다는 뜻이다.",
            "- 쉽게 풀어 달라거나 예를 들어 달라면 **원문 밖의 비유·예시를 써도 된다.**"
            " 사실은 원문을 지키되 말하는 방식은 바꿔라.",
        ]

    lines += [
        # 실측: 원문을 넣자마자 모델이 "학습자가 두 개념을 연결하려 한 것으로
        # 보입니다"라며 **행동을 분석하기 시작했다.** 원문이 그 화면 전체(여러
        # 쪽)라 짚은 말과 원문의 관계를 논하는 쪽으로 샌 것이다. 못 박는다.
        "- 학습자에게 바로 말한다. 학습자가 무엇을 하려 했는지 분석하지 않는다.",
        "- 짚은 말 하나만 설명한다. 원문의 다른 주제로 넓히지 않는다.",
        "- 모르면 모른다고 한다. 지어내지 않는다.",
        "- 3~5문장. 새 용어를 만들어 쓰지 않는다.",
        "- 마크다운 제목·목록을 쓰지 않는다. 말하듯 쓴다.",
    ]
    return "\n".join(lines)
