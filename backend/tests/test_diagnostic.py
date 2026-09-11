"""24 진단 — 순수 로직만. DB·LLM은 안 부른다.

여기서 지키는 것:
  ① 과목당 1~2문항. 틀리면 한 번으로 끝, 맞으면 두 번을 본다
  ② 자기신고는 판정이 아니라 **범위**다 — 탈락한 과목에서 뭘 뺄지만 정한다
  ③ 판정이 확정되기 전에는 `known`을 안 건드린다
  ④ LLM 응답의 흔들림(문자열 번호·범위 밖)을 견딘다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.course import search  # noqa: E402
from app.features.course.diagnostic import (  # noqa: E402
    Goal,
    Known,
    Style,
    _as_index,
    _cosine,
)
from app.features.course.prereq import _index_of, _squash  # noqa: E402
from app.features.course.search import HEARD, KNOWN, UNKNOWN, Item  # noqa: E402


def _items(n: int, known: str | None = None) -> list[Item]:
    return [Item(key=str(i), item=f"항목{i}", known=known) for i in range(n)]


def _run(items: list[Item], *, correct: bool) -> list[str]:
    """`correct`를 계속 답하며 끝까지 돌린다. 물어본 항목 key를 돌려준다."""
    asked = []
    while (target := search.next_item(items)) is not None:
        search.apply(items, target.key, correct)
        asked.append(target.key)
        if len(asked) > 10:
            raise AssertionError("안 끝난다")
    search.finalize(items)
    return asked


# ── ① 문항 수 ────────────────────────────────────────────────────


def test_틀리면_한_문항으로_끝난다():
    items = _items(13)
    assert len(_run(items, correct=False)) == 1
    assert all(r.known == UNKNOWN for r in items)


def test_맞히면_한_번_더_묻는다():
    """4지선다는 찍어서 맞는다. 하나로는 안 믿는다."""
    items = _items(13)
    asked = _run(items, correct=True)
    assert len(asked) == search.PROBES == 2
    assert len(set(asked)) == 2          # 같은 항목을 두 번 묻지 않는다
    assert all(r.known == KNOWN for r in items)


def test_맞히고_틀리면_모른다():
    items = _items(5)
    first = search.next_item(items)
    search.apply(items, first.key, True)
    assert search.state(items) is None   # 아직 판정 없음
    second = search.next_item(items)
    assert second is not None and second.key != first.key
    search.apply(items, second.key, False)
    search.finalize(items)
    assert search.state(items) == UNKNOWN
    # 직접 맞힌 항목만 남고 나머지는 과목 판정을 따른다.
    assert all(
        r.known == (KNOWN if r.key == first.key else UNKNOWN) for r in items
    )


def test_항목이_하나면_한_문항으로_끝난다():
    """더 물을 게 없다. 근거는 얇지만 없는 문항을 지어내지 않는다."""
    items = _items(1)
    assert _run(items, correct=True) == ["0"]
    assert items[0].known == KNOWN


def test_경계():
    assert search.max_probes(0) == 0
    assert search.max_probes(1) == 1
    assert search.max_probes(50) == 2
    assert search.next_item([]) is None
    assert search.state([]) is None
    search.finalize([])  # 안 터진다


# ── ② 자기신고 ───────────────────────────────────────────────────


def test_모른다고_해도_묻는다():
    """모른다고 한 사람도 맞힐 수 있다. 안 묻고 넘기면 진단이 아니다."""
    items = _items(6, known=UNKNOWN)
    assert search.next_item(items) is not None
    _run(items, correct=True)
    assert all(r.known == KNOWN for r in items)   # 뒤집힌다


def test_안다고_한_항목을_먼저_묻는다():
    """판정이 뒤집힐 여지가 거기 있다."""
    items = _items(4, known=UNKNOWN)
    items[2].known = KNOWN
    items[3].known = HEARD
    assert search.next_item(items).key == "2"      # known 먼저
    search.apply(items, "2", True)
    assert search.next_item(items).key == "3"      # 그다음 heard


def test_들어봤다도_두_번_맞혀야_안다():
    items = _items(5, known=HEARD)
    assert len(_run(items, correct=True)) == 2
    assert all(r.known == KNOWN for r in items)


# ── ③ 자기신고는 범위다 ─────────────────────────────────────────


def test_펼친_과목은_안다고_한_항목을_보강에서_뺀다():
    items = _items(5, known=UNKNOWN)
    items[1].known = KNOWN
    items[3].known = KNOWN
    search.apply(items, "0", False)               # 과목 탈락
    search.finalize(items)
    assert [r.known for r in items] == [
        UNKNOWN, KNOWN, UNKNOWN, KNOWN, UNKNOWN
    ]


def test_통과한_과목도_모른다고_한_항목은_남긴다():
    """실측: 「네트워크 기초」 두 문항 맞혔다고 "라우팅 모른다"까지 덮어썼다."""
    items = _items(5, known=KNOWN)
    items[2].known = UNKNOWN
    items[4].known = UNKNOWN
    search.apply(items, "0", True)
    search.apply(items, "1", True)
    search.finalize(items)
    assert search.state(items) == KNOWN
    assert [r.known for r in items] == [
        KNOWN, KNOWN, UNKNOWN, KNOWN, UNKNOWN
    ]


def test_직접_물어본_항목은_잰_값이_이긴다():
    """1라운드는 맞고 2라운드는 틀렸다 — 맞힌 항목까지 모른다로 만들지 않는다."""
    items = _items(5)
    search.apply(items, "0", True)
    search.apply(items, "1", False)
    search.finalize(items)
    assert search.state(items) == UNKNOWN
    assert items[0].known == KNOWN          # 직접 맞혔다
    assert [r.known for r in items[1:]] == [UNKNOWN] * 4


def test_안_펼친_과목은_통째로_간다():
    """항목 답이 전부 같으면 과목 답이 복사된 것이다 — 좁힐 근거가 없다."""
    items = _items(5, known=KNOWN)
    search.apply(items, "0", False)
    search.finalize(items)
    assert all(r.known == UNKNOWN for r in items)


def test_직접_틀린_항목은_예외가_없다():
    """스스로 안다고 했어도 그 문항을 틀렸으면 모른다."""
    items = _items(4, known=UNKNOWN)
    items[0].known = KNOWN
    items[2].known = KNOWN
    search.apply(items, "0", False)
    search.finalize(items)
    assert items[0].known == UNKNOWN   # 직접 틀렸다
    assert items[2].known == KNOWN     # 안 물어봤고 스스로 안다고 했다


def test_들어봤다가_안_남는다():
    for answer in (True, False):
        items = _items(4, known=HEARD)
        _run(items, correct=answer)
        assert all(r.known in (KNOWN, UNKNOWN) for r in items)


# ── ④ 진행 중에는 안 건드린다 ───────────────────────────────────


def test_판정_전에는_known을_그대로_둔다():
    """중간 결과를 known에 쓰면 다음 라운드가 자기신고 대신 그걸 읽는다."""
    items = _items(5, known=HEARD)
    items[0].known = KNOWN
    search.apply(items, "0", True)
    search.finalize(items)                         # 아직 1문항 — 확정 아님
    assert search.state(items) is None
    assert items[0].known == KNOWN and items[1].known == HEARD


def test_안_물어본_항목은_verified가_비어_있다():
    """`known`은 과목 판정을 내린 값이고, 그 항목을 잰 값이 아니다."""
    items = _items(9)
    _run(items, correct=True)
    assert sum(1 for r in items if r.verified is not None) == 2
    assert all(r.known == KNOWN for r in items)


# ── ⑤ LLM 응답 방어 ─────────────────────────────────────────────


def test_LLM이_준_번호를_방어적으로_읽는다():
    for fn in (_as_index, lambda v, n: _index_of(v, ["가"] * n)):
        assert fn(1, 3) == 1
        assert fn("2", 3) == 2
        assert fn(9, 3) is None
        assert fn(-1, 3) is None
        assert fn(None, 3) is None
        assert fn(True, 3) is None   # bool은 int의 하위형이다


def test_없는_항목에_답이_와도_안_터진다():
    items = _items(3)
    search.apply(items, "없는키", True)
    assert all(r.verified is None for r in items)


def test_과목이름은_공백만_달라도_같다():
    """실측: `컴퓨터구조`/`컴퓨터 구조`, `정보보안 기초`/`정보 보안 기초`."""
    assert _squash("컴퓨터구조") == _squash("컴퓨터 구조")
    assert _squash("정보보안 기초") == _squash("정보 보안 기초")
    assert _squash("네트워크 기초") != _squash("네트워크 보안 기초")


def test_상수값들():
    assert Known.ALL == {"known", "heard", "unknown"}
    assert Goal.ALL == {"exam", "work", "interest"}
    assert Style.ALL == {"metaphor", "definition", "table", "why"}


def test_코사인():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0  # 0벡터에 나눗셈이 없다
