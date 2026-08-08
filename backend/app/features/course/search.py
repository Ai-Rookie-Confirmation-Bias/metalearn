"""24 ⑤ 확인 문항 — **과목을 넣나 마나를 가른다.**

DB도 LLM도 안 부르는 순수 로직이다. 상태는 `known`·`verified` 두 칸에서 그대로
읽어내므로 세션 테이블이 없고, 중간에 창을 닫아도 이어진다.

## 왜 과목 단위인가

행동 단위가 과목이다. 27이 끼우는 건 보강 **단원**이고, 26이 만드는 건 항목마다
세 줄짜리 명세다. 그러면 진단이 답해야 할 건 하나뿐이다 — **이 과목을 넣나 마나.**

"13개 중 정확히 몇 번째까지 아는가"는 아무도 안 쓴다. 그걸 재려고 이분 탐색을
붙였다가 없는 순서를 지어냈다. 실측:

    데이터베이스 기초  항목 13개인데 서로 다른 seq는 4개
    네트워크 기초      항목 10개인데 서로 다른 seq는 5개

과목 병합이 이름만 합치고 seq를 안 고쳐서, 원본 4개 과목의 `seq 0`이 그대로
남았다. 그 상태로 이분 탐색이 리스트 인덱스를 타니 사실상 `id` 순이었다.
그래서 이런 게 나왔다:

    「피싱 개요」 맞힘   → TCP/IP · 라우팅 · IP 주소 = 안다
    「파티션 개념」맞힘  → 정규화 · SQL · 트랜잭션 = 안다

피싱을 안다고 라우팅을 아는 게 아니다. 54항목 중 24개가 이렇게 지어낸 "안다"였다.

## 규칙

    과목마다 문항을 낸다
      틀림    →  모른다. 끝                (1문항)
      맞음    →  한 번 더
         맞음 →  안다. 끝                  (2문항)
         틀림 →  모른다. 끝                (2문항)

**비대칭이고, 일부러 그렇다.** 틀림은 한 번으로 믿고 맞음은 두 번을 본다.
4지선다는 찍어서 맞지만 아는 사람이 틀릴 일은 드물고, 우리가 무서운 건
**모르는데 안다고 넘어가는 쪽**이라서다. 반대 방향은 보강을 한 번 더 보는 것뿐이다.

과목당 1~2문항. 자기신고가 맞으면 싸게 끝나고 어긋나는 과목에서만 늘어난다.

## 자기신고는 판정이 아니라 범위다

④에서 받은 항목별 답은 검증에 안 쓴다. 항목을 하나씩 검사하면 문항이 터진다.
대신 **그 과목이 탈락했을 때 뭘 넣을지**에 쓴다.

    탈락 + 펼친 과목    →  스스로 "안다"고 콕 집은 항목은 뺀다
    탈락 + 안 펼친 과목  →  그 과목 항목 전부

틀려도 보강이 좀 넓어지거나 좁아질 뿐이라, 자기신고가 사람을 오판하지 않는다.

## 안 쓰는 것

`ordered`와 항목 `seq` 순서는 12.5 LLM이 준 값이고 검증된 적이 없다.
여기서는 **둘 다 안 본다.** 어느 항목을 먼저 물을지 고를 때만 seq를 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass

KNOWN = "known"
HEARD = "heard"
UNKNOWN = "unknown"

# 한 과목에 낼 문항 수 상한. 맞았을 때만 여기까지 간다.
#   1개  찍어서 맞을 수 있다(4지선다 25%)
#   2개  둘 다 찍을 확률 6%. 이 판정으로 보강을 빼도 될 만하다
#   3개  같은 과목을 세 번 묻는 값이 판정이 나아지는 값보다 크다
PROBES = 2


@dataclass
class Item:
    """탐색이 보는 항목 하나. DB 행에서 필요한 것만 뽑았다."""

    key: str                      # course_prereqs.id (문자열)
    item: str
    known: str | None = None      # 자기신고. 판정이 끝나면 결과로 덮인다
    verified: bool | None = None  # 이 항목이 문항으로 나갔을 때의 결과


def _asked(items: list[Item]) -> list[bool]:
    return [row.verified for row in items if row.verified is not None]


def state(items: list[Item]) -> str | None:
    """확정된 과목 판정. `None`이면 아직 물을 게 남았다.

    항목이 하나뿐인 과목은 한 번 맞히면 거기서 끝난다 — 더 물을 게 없다.
    근거가 얇지만 없는 문항을 지어내는 것보다 낫다.
    """
    asked = _asked(items)
    if any(x is False for x in asked):
        return UNKNOWN
    if items and len(asked) >= min(PROBES, len(items)):
        return KNOWN
    return None


def next_item(items: list[Item]) -> Item | None:
    """다음에 물을 항목. `None`이면 이 과목은 끝났다.

    **스스로 "안다"고 한 항목을 먼저 묻는다.** 판정이 뒤집힐 여지가 거기 있고,
    모른다고 한 걸 물어 맞혀도 어차피 한 번 더 물어야 한다.
    """
    if not items or state(items) is not None:
        return None
    pool = [row for row in items if row.verified is None]
    if not pool:
        return None
    rank = {KNOWN: 0, HEARD: 1}
    return min(pool, key=lambda row: (rank.get(row.known or "", 2), items.index(row)))


def apply(items: list[Item], key: str, correct: bool) -> None:
    """답 하나를 반영한다. **제자리에서 고친다.**"""
    for row in items:
        if row.key == key:
            row.verified = correct
            return


def _expanded(items: list[Item]) -> bool:
    """펼친 과목인가 — 항목마다 답이 다르면 펼쳐서 받은 것이다.

    안 펼친 과목은 과목 답 하나가 항목 전부에 복사돼 있어 값이 같다.
    펼쳤는데 전부 같은 답을 골랐다면 안 펼친 것과 결과가 같으니 상관없다.
    """
    return len({row.known for row in items}) > 1


def finalize(items: list[Item]) -> None:
    """확정된 판정을 항목에 내린다. 진행 중이면 아무것도 안 한다.

    진행 중에 `known`을 건드리지 않는 게 중요하다 — 그러면 다음 라운드가
    자기신고 대신 중간 결과를 읽게 되고, 범위 좁히기 근거가 사라진다.

    **판정은 과목 것이고 항목을 덮어쓰지 않는다.** 펼쳐서 항목마다 답을 받은
    과목이라면, 그 사람이 콕 집어 반대로 말한 항목은 그대로 둔다. 우리가 잰 건
    과목이지 그 항목이 아니다. 실측에서 「네트워크 기초」를 두 문항 맞혔다고
    스스로 "라우팅 모른다"고 한 것까지 안다로 덮어썼다 — 지어낸 값이다.

        판정 안다  + 스스로 "모른다"고 한 항목  →  모른다로 둔다
        판정 모른다 + 스스로 "안다"고 한 항목    →  안다로 둔다
        직접 물어본 항목                        →  잰 값이 이긴다
    """
    verdict = state(items)
    if verdict is None:
        return

    narrow = _expanded(items)
    opposite = UNKNOWN if verdict == KNOWN else KNOWN
    for row in items:
        if row.verified is not None:
            row.known = KNOWN if row.verified else UNKNOWN   # 직접 쟀다
        elif narrow and row.known == opposite:
            continue                                          # 콕 집어 말했다
        else:
            row.known = verdict


def done(items: list[Item]) -> bool:
    return next_item(items) is None


def max_probes(n: int) -> int:
    """이 과목에 나갈 수 있는 문항 수 상한. 화면 진행률이 쓴다."""
    return min(PROBES, n) if n > 0 else 0
