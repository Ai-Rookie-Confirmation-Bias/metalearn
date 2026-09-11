"""파싱 tree → 문제은행 입력. 경계에서 무엇이 지켜져야 하는가.

DB·LLM 없음. 여기서 잠그는 건 **이름이 다른 것들의 대응**과, 앵커가 없을 때
조용히 통과하지 않는다는 것이다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.quiz.adapters import parsed_from_tree  # noqa: E402
from app.features.quiz.intake import validate_document  # noqa: E402
from app.features.quiz.schemas import QuizGenConfig  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _tree(**over):
    """앵커·개념·그림이 다 있는 최소 트리 하나."""
    text = "감성은 느낌이다. 감성지수는 그것을 수치화한다."
    tree = {
        "document": {"filename": "probe.pdf", "parser_version": "v3.0"},
        "topics": [
            {
                "id": "t1",
                "seq": 0,
                "title": "감성의 원리",
                "page_from": 1,
                "page_to": 4,
                "segments": [
                    {
                        "seq": 0,
                        "content": text,
                        "page_from": 1,
                        "page_to": 2,
                        "sentences": [
                            {"seq": 1, "char_start": 10, "char_end": len(text)},
                            {"seq": 0, "char_start": 0, "char_end": 10},
                        ],
                        "figures": [
                            {
                                "page": 2,
                                "char_offset": 5,
                                "category": "chart",
                                "needs_vision": True,
                            }
                        ],
                    }
                ],
                "concepts": [
                    {
                        "id": "c1",
                        "name": "감성",
                        "definition": "느낌",
                        "segment_seqs": [0],
                        "prerequisite_ids": [],
                    },
                    {
                        "id": "c2",
                        "name": "감성지수",
                        "definition": "수치화한 지표",
                        "segment_seqs": [0],
                        "prerequisite_ids": ["c1"],
                    },
                ],
            }
        ],
        "orphan_segments": [],
    }
    tree.update(over)
    return tree


# ── 어댑터: 이름이 다른 것들의 대응 ────────────────────────────────


def test_트리를_계약_형태로_옮긴다():
    pd = parsed_from_tree(_tree())

    assert pd.parser_version == "v3.0"
    assert pd.source_name == "probe.pdf"
    assert [t.index for t in pd.tocs] == [0]
    assert pd.tocs[0].chunk_indexes == [0]

    chunk = pd.chunks[0]
    assert chunk.index == 0  # ← segments[].seq
    assert chunk.raw_text.startswith("감성은")  # ← segments[].content
    assert (chunk.page_from, chunk.page_to) == (1, 2)


def test_문장_앵커는_seq_순서로_온다():
    # 트리는 seq 역순으로 줬다. 계약은 "앵커끼리 겹치지 않게, 순서대로"다.
    pd = parsed_from_tree(_tree())
    starts = [s.start for s in pd.chunks[0].sentences]
    assert starts == sorted(starts), f"정렬이 안 됐다: {starts}"
    assert (pd.chunks[0].sentences[0].start, pd.chunks[0].sentences[0].end) == (0, 10)


def test_개념은_segment_seqs로_조각에_배분된다():
    pd = parsed_from_tree(_tree())
    names = {c.name for c in pd.chunks[0].concepts}
    assert names == {"감성", "감성지수"}


def test_선수개념은_UUID가_아니라_이름으로_바뀐다():
    # 파싱은 prerequisite_ids(식별자)를 주고, quiz 계약은 prereqs(이름)를 받는다.
    pd = parsed_from_tree(_tree())
    by_name = {c.name: c for c in pd.chunks[0].concepts}
    assert by_name["감성지수"].prereqs == ["감성"]
    assert by_name["감성"].prereqs == []


def test_그림은_char_offset을_offset으로_옮긴다():
    fig = parsed_from_tree(_tree()).chunks[0].figures[0]
    assert fig.offset == 5  # ← char_offset
    assert fig.kind == "chart"
    assert fig.needs_vision is True


def test_페이지가_없으면_목차에서_물려받는다():
    # 계약상 page_from/to는 필수 int인데 파싱은 None을 줄 수 있다.
    tree = _tree()
    tree["topics"][0]["segments"][0]["page_from"] = None
    tree["topics"][0]["segments"][0]["page_to"] = None
    chunk = parsed_from_tree(tree).chunks[0]
    assert (chunk.page_from, chunk.page_to) == (1, 4)  # 목차의 범위


def test_변환_결과가_무결성을_통과한다():
    rep = validate_document(parsed_from_tree(_tree()), QuizGenConfig())
    assert rep.errors == [], rep.errors


# ── 게이트: 앵커가 없으면 조용히 통과하면 안 된다 ────────────────────


def test_앵커가_없으면_무결성이_막는다():
    # ★ 예전엔 커버리지 검사가 `if chunk.sentences and …`라서 **빈 배열이면
    #   검사를 건너뛰고 오류 0·경고 0**이 나왔다. 하류가 전부 offset을 믿고
    #   도는데 미측정이 합격으로 보였다.
    tree = _tree()
    tree["topics"][0]["segments"][0]["sentences"] = []
    rep = validate_document(parsed_from_tree(tree), QuizGenConfig())
    assert rep.errors, "앵커가 하나도 없는데 통과했다"
    assert "앵커가 0개" in rep.errors[0]


def test_원문이_비면_앵커가_없어도_막지_않는다():
    # 빈 조각까지 실패로 만들면 파싱의 사소한 잔재가 문서 전체를 막는다.
    tree = _tree()
    tree["topics"][0]["segments"][0]["content"] = ""
    tree["topics"][0]["segments"][0]["sentences"] = []
    tree["topics"][0]["segments"][0]["figures"] = []
    rep = validate_document(parsed_from_tree(tree), QuizGenConfig())
    assert rep.errors == [], rep.errors


# ── 실제 파싱 산출물 ──────────────────────────────────────────────


def test_실제_트리_픽스처를_받는다():
    tree = json.loads((FIXTURES / "sample_sdlc.tree.json").read_text(encoding="utf-8"))
    pd = parsed_from_tree(tree)
    assert pd.chunks and pd.tocs
    # 목차가 가리키는 조각이 실제로 있어야 한다(계약 규칙).
    have = {c.index for c in pd.chunks}
    for toc in pd.tocs:
        assert set(toc.chunk_indexes) <= have


# ⚠️ 새 테스트는 **이 위에** 쓴다. 아래 `__main__` 블록보다 뒤에 정의하면
#    pytest로는 돌지만 스크립트로 직접 돌릴 때 조용히 빠진다.


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}  {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
