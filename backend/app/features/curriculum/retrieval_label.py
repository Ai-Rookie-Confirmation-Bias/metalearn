"""[순수로직] 인출 라벨 검증 — 오측정이 미측정보다 나쁘다.

게이트가 `concept` **라벨**로만 세면 "라벨 ≠ 실제 묻는 것"이 통과한다.
실측(`0-8cdd5ac9` 중):

    concept='애자일 모형'     answer='XP(eXtreme Programming)'  ← 다른 개념이 정답
    concept='프로토타입 모형'  answer='견본·시제품'              ← 성질 유형(의도)

성질은 프롬프트가 허용한 설계다. 문제는 숙련도가 그걸 구분 없이 라벨 개념에
기록한다는 것 — 성질을 맞혀도 "그 개념을 꺼낼 수 있다"의 증거는 약하다.
정답이 **이 화면(절) 밖·다른 개념**인 것은 유형과 무관하게 사고다.

규칙
  · 정답이 이 화면의 **다른** 개념이면 폐기 (포함 매칭 — 상대가 두셋이라 표기 흔들림을 흡수)
  · 정답이 문서의 **다른 화면** 개념이면 폐기 (`foreign_keys`, **정확 일치만** — `_foreign_hit`)
  · 정답이 라벨 개념이면 이름 인출(정의·상황) — 누락 게이트·숙련도에 쓴다
  · 정답이 개념명이 아니면 성질 — `concept_keys`는 비우고 라벨은 `content.concept`에 남긴다
  · 모델이 "정의/상황"이라 신고했는데 답이 개념명이 아니면 폐기
  · 누락 = 이름 인출이 한 번도 없는 개념 (성질만 있으면 미측정)
"""
from __future__ import annotations

from dataclasses import replace

from .blocks import Block, ConceptBrief, _answer_concept, _sq
from .excerpt import aliases


def _foreign_hit(answer: str, foreign_keys: tuple[str, ...]) -> str | None:
    """정답이 **다른 화면 개념 그 자체**인가. 아니면 None.

    ⚠️ 여기에 `_answer_concept`를 쓰면 안 된다. 거기엔 표기가 조금 달라도 서로
    **포함**이면 같게 보는 완화가 있는데, 그건 상대가 이 화면 개념 두셋일 때 맞다.
    `foreign_keys`는 **문서 전체**가 상대다(실측 371개, 3자 이하가 59개).

    실측 사고: 성질 정답 `'이미 오름차순으로 정렬된 상태를 유지하는 배열의 일부'`가
    문서 어딘가의 개념 `'상태'`를 품었다는 이유로 폐기됐다. 멀쩡한 문항이 조용히
    사라진다. ⇒ **같은 함수를 상대 크기가 다른 자리에 쓴 것**이 원인이다.
    여기서는 정확히 같은 표기일 때만 본다 — 실제로 잡아야 하는 사고
    (`concept='애자일 모형'` / `answer='XP(eXtreme Programming)'`)가 그 모양이다.
    """
    ans = _sq(answer)
    if not ans:
        return None
    for k in foreign_keys:
        if any(_sq(a) == ans for a in aliases(k)):
            return k
    return None


def scrub_cloze(
    block: Block,
    concepts: list[ConceptBrief],
    *,
    foreign_keys: tuple[str, ...] = (),
) -> Block | None:
    """빈칸 하나를 검증한다. 폐기면 None.

    살아남은 이름 인출은 `concept_keys`가 정확히 하나다.
    성질은 `concept_keys=()` — 화면이 숙련도에 안 붙인다.
    """
    if block.type != "cloze":
        return block

    answer = str(block.content.get("answer") or "")
    kind = str(block.content.get("kind") or "")
    labeled = block.concept_keys[0] if len(block.concept_keys) == 1 else None
    pointed = _answer_concept(answer, concepts)

    # 정답이 이 화면의 다른 개념 → 라벨 사고. 유형과 무관하게 버린다.
    if pointed is not None and labeled is not None and pointed != labeled:
        return None

    # 정답이 문서의 다른 화면 개념(이 화면에 없음) → 버린다.
    if pointed is None and foreign_keys and _foreign_hit(answer, foreign_keys):
        return None

    if pointed is not None:
        # 이름 인출. 라벨이 없거나 흐리면 정답이 가리키는 개념으로 고정한다.
        return replace(block, concept_keys=(pointed,))

    # 성질 — 답이 개념명이 아님.
    # "정의/상황"이라고 신고했으면 모델이 이름 인출을 만든 척한 것이라 버린다.
    if kind in ("정의", "상황"):
        return None
    # 숙련도에는 안 붙이되 **어느 개념을 다룬 문장인지는 남긴다**(`content.concept`).
    # `_levels_of`가 그 개념의 정의문과 대조해 L1(정의문 베끼기)을 잰다 —
    # 채점 귀속용 키와 측정용 라벨을 같은 칸에 두면 하나를 끌 때 다른 하나도 꺼진다.
    # 객관식이 이미 쓰는 방식이다(`concept_keys`는 절 전체, 귀속은 `content.concept`).
    content = block.content if labeled is None else {**block.content, "concept": labeled}
    return replace(block, content=content, concept_keys=())


def scrub_blocks(
    blocks: list[Block] | tuple[Block, ...],
    concepts: list[ConceptBrief],
    *,
    foreign_keys: tuple[str, ...] = (),
) -> list[Block]:
    """인출 블록 묶음을 검증한다. 객관식은 그대로 통과."""
    out: list[Block] = []
    for b in blocks:
        if b.type == "cloze":
            kept = scrub_cloze(b, concepts, foreign_keys=foreign_keys)
            if kept is not None:
                out.append(kept)
        else:
            out.append(b)
    return out


def is_name_recall(block: Block, concepts: list[ConceptBrief]) -> bool:
    """이 빈칸이 라벨 개념의 **이름 인출**인가.

    숙련도·누락 게이트에 넣는 조건이다. 성질은 False.
    """
    if block.type != "cloze" or len(block.concept_keys) != 1:
        return False
    key = block.concept_keys[0]
    answer = str(block.content.get("answer") or "")
    return _answer_concept(answer, concepts) == key


def recall_asked(blocks: list[Block] | tuple[Block, ...], concepts: list[ConceptBrief]) -> set[str]:
    """이름 인출로 한 번이라도 물어본 개념."""
    return {
        b.concept_keys[0]
        for b in blocks
        if is_name_recall(b, concepts)
    }
