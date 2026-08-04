"""[순수로직] 조각 원문에서 개념별 구간을 잘라낸다.

DB·LLM 비의존.

왜 필요한가:
    파싱은 `조각 → 개념 N개`로 준다. 그런데 **개념이 조각의 어느 부분인지는
    안 준다.** 조각 하나가 평균 3,438자(최대 3,982자)이므로, 이대로 두면
      · 절 하나를 설명하려고 조각 전체를 던지게 되고 → 요약된다(실측 39%)
      · 근거를 보여줄 때 3,982자를 통째로 펼치게 된다

    파싱에 "개념의 문장 범위를 달라"고 요청했지만, 받기 전까지는 우리가
    직접 찾아야 한다. 다행히 이 자료는 원문 자체가 항목으로 구조화되어 있다:

        001
        소프트웨어 공학의 기본 원칙
        - •현대적인프로그래밍기술을...

        002
        폭포수 모형
        ...

    개념명이 항목 제목과 일치하므로, **제목 위치로 구간을 자를 수 있다.**

⚠️ 이건 폴백이다. 항목 번호가 없는 일반 교재에는 안 통한다. 그때는
   `matched_ratio()`가 낮게 나오므로 조각 전체로 되돌아간다(fallback_whole).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 항목 번호 줄: "001", "002" — 단독 라인. 제목 후보에서 제외하는 데만 쓴다.
_ITEM_NO = re.compile(r"^\s*#?\s*(\d{2,3})\s*(초|치기)?\s*$")
# 요약집 조판 잡음. 세로로 흩어진 브랜드 표기가 원문 곳곳에 섞여 있다.
_NOISE = {"초", "치기", "핵심 요약", "정보처리기사 핵심 요약", ""}
# 줄머리 장식·이미지 플레이스홀더.
_DECOR = re.compile(r"^[\s\-•*#]+|!\[image\]\([^)]*\)")

# ⚠️ PDF 추출본은 **공백이 BEL(\x07)로 치환되어** 있다.
# 실측: '•\x07현대적인\x07프로그래밍\x07기술을' — 띄어쓰기가 없는 게 아니라 다른 문자다.
# 검색·표시 양쪽에서 이걸 먼저 되돌려야 한다.
_WEIRD_SPACE = re.compile(r"[\x07\x0b\x0c\xa0​]+")


def normalize_spaces(text: str) -> str:
    """PDF 추출 과정에서 뒤틀린 공백을 되돌린다.

    저장은 원문 그대로 두되, **검색과 화면 표시에는 이 함수를 통과시킨다.**
    원문을 고치는 게 아니라 읽을 수 있게 만드는 것이다.
    """
    return _WEIRD_SPACE.sub(" ", text)


# 개념명의 괄호 병기. `목 오브젝트 (Mock Object)` / `DRM(디지털 저작권 관리)`
_PAREN = re.compile(r"\s*[(（]([^)）]*)[)）]\s*")


def aliases(key: str) -> list[str]:
    """개념명의 표기 후보. 괄호 병기를 **따로 떼어** 둘 다 후보로 삼는다.

    실측 사고: 개념명이 `목 오브젝트 (Mock Object)`인데 본문은 `목 오브젝트`라고만
    써서 **넷 다 나와 있는 설명이 `언급 0/4`로 찍혔다.** 토큰으로 쪼개면
    `(Mock` `Object)`가 본문에 없어 70% 문턱을 못 넘기 때문이다.

    교재도 설명도 한쪽 표기만 쓴다. 둘 다 요구하면 정상 문장이 누락이 된다.
    괄호 병기 개념은 실측에서 필기 16%·실기 15%로 적지 않다.

        "목 오브젝트 (Mock Object)"  →  [원형, "목 오브젝트", "Mock Object"]
        "Python input() 함수"       →  [원형]          괄호가 이름의 일부다
        "키(Key)"                   →  [원형, "Key"]   한 글자 주표기는 버린다

    ※ 여기 있는 이유: 개념명을 원문에 맞춰보는 일은 절 묶기(grouping)와 학습 블록
      (blocks) 양쪽이 쓴다. 낮은 층인 이 모듈에 둬야 `grouping → blocks` 방향이
      뒤집히지 않는다.
    """
    # 원형을 먼저 둔다 — `Python input() 함수`처럼 괄호가 병기가 아니라
    # 이름의 일부인 경우가 있다. 떼어내면 원문과 안 맞는다.
    out = [key.strip()]
    outer = _PAREN.sub(" ", key).strip()
    if len(outer) >= 2:
        out.append(outer)
    # 병기 자체(`Mock Object`). 한 글자짜리는 노이즈라 버린다.
    out += [a.strip() for a in _PAREN.findall(key) if len(a.strip()) >= 2]
    return [a for a in dict.fromkeys(out) if a]


# 괄호 안이 이름이 아니라 설명일 때 섞이는 조사·어미. 있으면 별칭이 아니다.
_PROSE = re.compile(r"[은는이가을를의에서하며되고]")


def source_aliases(key: str, text: str) -> list[str]:
    """원문·정의문에서 **개념명 바로 뒤 괄호**를 별칭으로 뽑는다.

    교재는 약어를 괄호로 단다:
        ※ 익스트림 프로그래밍 (eXtreme Programming, XP)
    그런데 파싱이 주는 개념명은 `익스트림 프로그래밍`뿐이라 **`XP`라고 답하면
    오답**이 됐다(yoonhs 지적). 개념명에 없는 이름이 원문에는 있는 것이다.

    실측: 개념의 21~26%가 이렇게 별칭을 얻는다.
        소프트웨어 생명 주기 → SDLC · 하향식 설계 → Top-down · 캡슐화 → Encapsulation

    괄호 안이 이름이 아니라 설명인 경우가 있어(`프로토타입 (고객 needs 파악…)`)
    조사·어미가 섞였거나 너무 길면 버린다.
    """
    core = key.replace(" ", "")
    if len(core) < 2:
        return []
    # 원문은 띄어쓰기가 들쭉날쭉해 글자 사이 어디에나 공백이 올 수 있다.
    pat = re.compile(r"\s*".join(map(re.escape, core)) + r"\s*[(（]([^)）]{1,60})[)）]")
    m = pat.search(normalize_spaces(text))
    if not m:
        return []
    out: list[str] = []
    for piece in re.split(r"[,/·]", m.group(1)):
        p = piece.strip()
        if 2 <= len(p) <= 25 and not _PROSE.search(p):
            out.append(p)
    return out


# 분류어로 인정할 최소 공유 수. 이보다 적으면 그냥 우연히 끝이 같은 말이다.
MIN_CATEGORY_SHARE = 3


def category_words(keys: list[str], min_share: int = MIN_CATEGORY_SHARE) -> frozenset[str]:
    """개념명 끝 어절 중 여러 개념이 공유하는 것 = 교재의 **분류어**.

    교재는 표 안에서 분류어를 생략한다:
        # ■ 응집도 (Cohesion)
        | 기능적 (Function) | … |      ← 원문은 `기능적`
    파싱은 표 제목을 읽고 `기능적 응집도`로 이름을 완성한다. 잘한 일이지만 그 바람에
    **우리가 원문에서 그 이름을 못 찾아** 표를 통째로 놓쳤다(응집/결합 15개 중 13개).
    그러면 ③이 원문 순서로 4개씩 잘라 `시간적 응집도·싱글톤 패턴·외부 결합도`처럼
    섞인다.

    분류어를 **목록으로 박지 않고 데이터에서 뽑는다** — 박으면 정보처리기사에만
    맞는 물건이 된다. 교재가 바뀌면 그 교재의 분류어가 자동으로 잡힌다.

    ※ 여기 있는 이유: 절 묶기(원문에서 개념 찾기)와 채점(정답 표기 인정) 양쪽이
      쓴다. 낮은 층인 이 모듈에 둬야 `grouping → blocks` 방향이 뒤집히지 않는다.

    ⚠️ `min_share`를 쓰는 쪽마다 다르게 준다. **오탐 비용이 다르기 때문이다.**
      묶기(3) — 잘못 떼면 엉뚱한 덩어리에 배치돼 **절이 통째로 잘못 만들어진다**
      채점(2) — 잘못 떼면 관대하게 채점될 뿐이다. 반대로 엄격하면 개념을 정확히
                꺼낸 학습자가 틀렸다는 말을 듣는다(`폭포수` vs `폭포수 모형`)
    """
    tail: dict[str, int] = {}
    for k in keys:
        parts = k.split()
        if len(parts) >= 2 and len(parts[-1]) >= 2:
            tail[parts[-1]] = tail.get(parts[-1], 0) + 1
    return frozenset(w for w, n in tail.items() if n >= min_share)


@dataclass(frozen=True)
class Excerpt:
    """개념 하나에 대응하는 원문 구간."""

    key: str
    text: str
    start: int  # 조각 원문에서의 문자 오프셋 — 근거 표시·좌표 보존용
    end: int
    matched: bool  # 제목으로 실제 찾았는가 (False면 폴백)

    @property
    def chars(self) -> int:
        return len(self.text)


def _clean_line(line: str) -> str:
    return _DECOR.sub("", normalize_spaces(line)).strip()


def _heading_positions(text: str) -> list[tuple[int, str]]:
    """(오프셋, 제목 후보) 목록.

    항목 번호에 의존하지 않는다. 실측에서 조판이 뒤엉켜 있었다 —
    번호 두 개가 연달아 나오거나(`003` `007`), 번호가 헤딩에 붙거나
    (`# 010 치기`), 번호와 제목 사이에 이미지·잡음이 4줄 넘게 끼었다.
    번호를 기준으로 삼으니 30%밖에 못 찾았다.

    대신 **짧은 단독 줄**을 제목 후보로 본다. 요약집은 제목이 한 줄로
    떨어져 있고 본문은 불릿(`- •`)으로 시작하므로 구분된다.
    """
    out: list[tuple[int, str]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\n")
        cand = _clean_line(line)
        # 본문 불릿·표·긴 문장은 제목이 아니다.
        is_body = line.lstrip().startswith(("- ", "•", "|")) or len(cand) > 40
        if cand and not is_body and cand not in _NOISE and not _ITEM_NO.match(line):
            out.append((offset, cand))
        offset += len(raw)
    return out


def split_by_concepts(chunk_text: str, concept_keys: list[str]) -> list[Excerpt]:
    """조각 원문을 개념별 구간으로 자른다.

    제목으로 찾은 개념은 그 위치부터 다음 제목 직전까지를 구간으로 갖는다.
    못 찾은 개념은 조각 전체를 구간으로 갖는다(폴백) — 근거가 넓어질 뿐,
    틀린 내용을 주지는 않는다.
    """
    if not chunk_text or not concept_keys:
        return []

    headings = _heading_positions(chunk_text)
    # 제목 → 오프셋. 같은 제목이 여러 번이면 처음 것.
    at: dict[str, int] = {}
    for pos, title in headings:
        at.setdefault(title, pos)

    # 개념명 ↔ 원문 제목 매칭. 셋을 순서대로 시도한다.
    #   ① 정확히 같다                    "HIPO" = "HIPO"
    #   ② 제목이 개념명을 포함한다        "자료 흐름도" ⊂ "자료 흐름도의 구성 요소"
    #   ③ 개념명이 제목을 포함한다        "XP의 핵심 가치" ⊃ "XP"
    # 짧은 개념명(2자 이하)은 우연히 겹치기 쉬우므로 ①만 인정한다.
    starts: dict[str, int] = {}
    for key in concept_keys:
        if key in at:
            starts[key] = at[key]
            continue
        if len(key) <= 2:
            continue
        best: tuple[int, int] | None = None  # (제목 길이, 위치) — 가장 짧은 제목 우선
        for title, pos in at.items():
            if key in title or (len(title) >= 3 and title in key):
                if best is None or len(title) < best[0]:
                    best = (len(title), pos)
        if best is not None:
            starts[key] = best[1]

    bounds = sorted(pos for pos, _ in headings)

    out: list[Excerpt] = []
    for key in concept_keys:
        if key not in starts:
            out.append(
                Excerpt(key=key, text=chunk_text, start=0, end=len(chunk_text), matched=False)
            )
            continue
        s = starts[key]
        nxt = [b for b in bounds if b > s]
        e = nxt[0] if nxt else len(chunk_text)
        out.append(
            Excerpt(key=key, text=chunk_text[s:e].strip(), start=s, end=e, matched=True)
        )
    return out


def matched_ratio(excerpts: list[Excerpt]) -> float:
    """제목으로 실제 잘라낸 비율. 낮으면 이 자료엔 항목 구조가 없는 것이다."""
    if not excerpts:
        return 0.0
    return sum(1 for e in excerpts if e.matched) / len(excerpts)


def section_source(
    chunk_text: str, section_keys: list[str], all_keys: list[str]
) -> str:
    """절 하나에 줄 원문. 절에 속한 개념들의 구간만 이어 붙인다.

    하나라도 못 찾으면 조각 전체를 준다 — 절의 일부만 주면 설명이 반쪽이 되고,
    그게 요약보다 나쁘다(사실이 빠진 채로 완결된 것처럼 보인다).
    """
    excerpts = {e.key: e for e in split_by_concepts(chunk_text, all_keys)}
    picked = [excerpts[k] for k in section_keys if k in excerpts]
    if not picked or any(not e.matched for e in picked):
        return chunk_text
    # 원문 순서를 지켜 이어 붙인다.
    picked.sort(key=lambda e: e.start)
    return "\n\n".join(e.text for e in picked)
