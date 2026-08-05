"""7단계 목차 분류 프롬프트.

LLM에게 **분류만** 시킨다. 원문 생성도, 요약도, 재작성도 시키지 않는다.
그래서 이 단계에서 원문이 손상될 여지가 구조적으로 없다.

조각을 보여줄 때는 제목 + 앞부분만 준다. 전문을 넣으면 토큰이 폭발하고,
분류에는 앞부분이면 충분하다.
"""
from __future__ import annotations

from app.features.parsing.schemas import Segment

SYSTEM = (
    "너는 학습 자료의 목차를 정하는 분류기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다. "
    "본문을 생성하거나 고쳐 쓰지 말고, 조각 번호와 목차 제목으로만 답한다."
)

# 조각당 프롬프트에 넣을 원문 길이. 분류에는 앞부분이면 충분하다.
PREVIEW_CHARS = 300


def build_outline_prompt(
    segments: list[Segment], max_topics: int, preview_chars: int = 120
) -> str:
    """1패스 — **단원 이름만** 짓는다. 배정은 안 시킨다.

    짓기와 배정을 한 번에 시키면 앞 조각부터 이름을 붙이다가 상한이 차고,
    남은 조각이 인접 목차로 쓸려 들어간다. 실측: 정처기 필기 자료에서
    "선택 정렬 알고리즘"이라는 소제목이 조각 6개를 먹었다.

    먼저 전체를 조망하게 하면 "단원"이라는 층위가 생긴다.
    """
    # 단원 하나가 조각 3~4개를 담는 크기를 목표로 역산한다.
    target = 3
    low = max(3, min(max_topics, round(len(segments) / 4)))
    high = max(low + 1, min(max_topics, round(len(segments) / 2.5)))

    lines = [
        f"학습 자료가 조각 {len(segments)}개로 나뉘어 있다. "
        "아래는 각 조각의 제목과 앞부분이다.\n\n",
        "이 자료 전체를 아우르는 **단원 목록**을 만들어라.\n\n",
        "먼저 판단하라:\n",
        "  · 이 자료가 특정 시험·과목의 것이고 그 과목에 **공인된 표준 목차**가 "
        "있다면, 그 표준 목차를 그대로 쓴다 (source=\"standard\").\n",
        "  · 아니면 자료의 흐름을 보고 직접 짓는다 (source=\"derived\").\n\n",
        "규칙:\n",
        # 상한만 알려주면 LLM이 그 수를 채우려 든다. 실측 3회에서 10개를
        # 만든 두 번은 1개짜리 단원이 7/10, 4/10이었고, 6개를 만든 한 번은
        # 0/6으로 완벽했다. 조각 수에서 역산한 목표를 직접 준다.
        f"1. 단원은 **{low}~{high}개**. 이 범위를 지켜라.\n",
        "2. **소제목이 아니라 단원 수준**이어야 한다.\n",
        "   ✗ 나쁜 예: \"선택 정렬 알고리즘\", \"트리 순회 방법(전위/중위)\", "
        "\"파티션 유형\"  ← 한 페이지짜리 소제목\n",
        "   ✓ 좋은 예: \"소프트웨어 개발\", \"데이터베이스 구축\", "
        "\"프로그래밍 언어 활용\"\n",
        f"3. 단원 하나가 조각 {target}개 안팎을 담을 크기여야 한다. "
        "**조각 하나만 들어갈 단원은 만들지 마라.** 그건 소제목이다.\n",
        "4. 한 단원에 이름을 두 개 붙이지 마라 "
        "(✗ \"자료구조 및 접근제어\" — 서로 다른 주제다).\n",
        "5. 자료에 실제로 없는 내용의 단원은 만들지 마라.\n",
        "6. **여기서는 배정하지 마라.** 단원 이름만 낸다.\n\n",
        'JSON: {"source":"standard|derived","subject":str,"topics":[str]}\n\n',
        "=== 조각 목록 ===\n",
    ]
    lines.extend(_render(s, preview_chars) for s in segments)
    return "".join(lines)


def build_prompt(
    segments: list[Segment], max_topics: int, preview_chars: int = PREVIEW_CHARS
) -> str:
    """조각 목록 → 분류 요청 프롬프트 (1패스가 실패했을 때의 단일 호출 경로)."""
    seqs = [s.seq for s in segments]
    lines = [
        f"학습 자료가 조각 {len(segments)}개로 나뉘어 있다. "
        f"이 조각들을 {max_topics}개 이내의 목차로 분류하라.\n\n",
        "규칙:\n",
        f"1. 목차는 최대 {max_topics}개다. 자료에 이미 목차/장 구조가 보이면 "
        "그 항목을 그대로 목차 제목으로 쓰고, 없으면 내용 흐름을 보고 새로 지어라.\n",
        # 실측: 조각 21개 중 0~9만 배정하고 10~20을 통째로 빠뜨렸다.
        # 배정해야 할 번호를 눈앞에 나열해 주면 누락이 크게 준다.
        f"2. **{seqs[0]}번부터 {seqs[-1]}번까지 {len(seqs)}개 번호가 "
        "정확히 한 번씩 전부 나와야 한다.** 빠뜨리면 안 되고, 한 조각을 "
        "두 목차에 넣어도 안 된다. 답을 쓰기 전에 번호를 세어 확인하라.\n",
        "3. 조각 번호 순서는 자료의 원래 순서다. 목차는 그 흐름을 따라 "
        "연속된 조각들을 묶는 것이 자연스럽다. 특정 목차 하나에 대부분을 "
        "몰아넣지 말고, 분량이 고르게 나뉘도록 하라.\n",
        "4. 목차 제목은 학습 주제로 읽히게 짓는다. "
        '헤딩 원문을 그대로 베끼지 말 것(예: "■ 트리 순회 방법 - 3가지" → "트리 순회").\n',
        "5. 본문을 요약하거나 고쳐 쓰지 말 것. 조각 번호만 배정하라.\n\n",
        'JSON 형식: {"topics": [{"title": str, "segments": [조각 번호, ...]}, ...]}\n\n',
        "=== 조각 목록 ===\n",
    ]

    lines.extend(_render(s, preview_chars) for s in segments)
    return "".join(lines)


def build_assign_prompt(
    orphans: list[Segment],
    topic_titles: list[str],
    preview_chars: int = PREVIEW_CHARS,
    *,
    full: bool = False,
) -> str:
    """정해진 목차에 조각을 배정한다.

    두 군데서 쓴다.
      full=True   2패스 — 1패스가 지은 단원에 **전체 조각**을 배정
      full=False  보정 — 1차에서 빠진 조각만 다시 배정

    짓기와 배정을 분리하는 게 핵심이다. 목차가 이미 있으면 LLM이 하는 일은
    분류뿐이고, 분류는 짓기보다 훨씬 잘한다. 러닝 헤더로 배정할 때 정확했던
    것과 같은 이유다 — 답을 주고 매칭만 시키는 것.
    """
    listed = "\n".join(f"  {i}: {title}" for i, title in enumerate(topic_titles))
    head = (
        f"아래 단원 {len(topic_titles)}개에 조각 {len(orphans)}개를 전부 배정하라.\n\n"
        if full
        else f"아래 목차 {len(topic_titles)}개가 이미 정해져 있다.\n\n"
    )
    lines = [
        head,
        f"{listed}\n\n",
    ]
    if not full:
        lines.append(
            f"다음 조각 {len(orphans)}개가 아직 어느 목차에도 배정되지 않았다. "
            "각 조각을 위 목차 중 하나에 배정하라.\n\n"
        )
    lines += [
        "규칙:\n",
        "1. **새 목차를 만들지 말 것.** 위 번호 중에서만 고른다.\n",
        "2. 모든 조각이 정확히 하나의 목차에 들어가야 한다.\n",
        "3. 조각 번호 순서는 자료의 원래 순서다. 대체로 연속된 조각이 "
        "같은 단원에 들어간다.\n",
        "4. 특정 단원에 몰아넣지 말 것. 내용이 애매하면 번호가 가까운 조각과 "
        "같은 단원으로 보낸다.\n\n",
        'JSON 형식: {"assignments": [{"segment": 조각번호, "topic": 단원번호}, ...]}\n\n',
        "=== 배정할 조각 ===\n",
    ]
    lines.extend(_render(s, preview_chars) for s in orphans)
    return "".join(lines)


def _render(segment: Segment, preview_chars: int) -> str:
    preview = " ".join(segment.content[:preview_chars].split())
    heading = segment.heading or "(제목 없음)"
    if segment.page_from is None:
        pages = ""
    elif segment.page_from == segment.page_to:
        pages = f" p.{segment.page_from}"
    else:
        pages = f" p.{segment.page_from}-{segment.page_to}"
    return f"[{segment.seq}]{pages} {heading}\n    {preview}\n"
