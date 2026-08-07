"""24 진단 — 순수 로직만. DB·LLM은 안 부른다.

여기서 지키는 것:
  ① 확인 문항 수는 **고정이 아니다** — "안다"가 많을수록 몇 개 더 본다
  ② 과목 이름 정규화·번호 파싱이 LLM 응답의 흔들림을 견딘다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.course.diagnostic import (  # noqa: E402
    PROBE_MAX,
    Goal,
    Known,
    Style,
    _cosine,
    probe_count,
)
from app.features.course.prereq import _index_of, _squash  # noqa: E402


def test_확인문항은_고정_개수가_아니다():
    """점수를 내는 시험이 아니라 자기평가가 후한지 보는 표본이다."""
    assert probe_count(0) == 0      # 물을 게 없다
    assert probe_count(1) == 1
    assert probe_count(3) == 1
    assert probe_count(4) == 1
    assert probe_count(5) == 2
    assert probe_count(12) == 3


def test_확인문항에_상한이_있다():
    """진단이 길어지면 시험처럼 느껴지고, 그 순간 이 화면의 목적이 깨진다."""
    assert probe_count(100) == PROBE_MAX
    assert probe_count(10_000) == PROBE_MAX


def test_과목이름은_공백만_달라도_같다():
    """실측: `컴퓨터구조`/`컴퓨터 구조`, `정보보안 기초`/`정보 보안 기초`."""
    assert _squash("컴퓨터구조") == _squash("컴퓨터 구조")
    assert _squash("정보보안 기초") == _squash("정보 보안 기초")
    assert _squash("네트워크 기초") != _squash("네트워크 보안 기초")


def test_LLM이_준_번호를_방어적으로_읽는다():
    items = ["가", "나", "다"]
    assert _index_of(1, items) == 1
    assert _index_of("2", items) == 2       # 문자열로 올 수 있다
    assert _index_of(9, items) is None      # 범위 밖
    assert _index_of(-1, items) is None
    assert _index_of("나", items) is None   # 이름으로 오면 못 쓴다
    assert _index_of(None, items) is None
    assert _index_of(True, items) is None   # bool은 int의 하위형이다


def test_상수값들():
    assert Known.ALL == {"known", "heard", "unknown"}
    assert Goal.ALL == {"exam", "work", "interest"}
    assert Style.ALL == {"metaphor", "definition", "table", "why"}


def test_코사인():
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0  # 0벡터에 나눗셈이 없다
