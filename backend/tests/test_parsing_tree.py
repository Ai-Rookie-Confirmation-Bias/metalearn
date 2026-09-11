"""DocumentTree 어댑터 테스트."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.adapters.parsing_tree import document_from_tree  # noqa: E402
from app.features.curriculum.store import (  # noqa: E402
    FIXTURE_DIR,
    Store,
    build_document_from_tree,
)

FIXTURE = FIXTURE_DIR / "sample_sdlc.tree.json"


def test_fixture_로드():
    doc = build_document_from_tree(FIXTURE)
    assert doc.doc_id == "sample_sdlc"
    assert len(doc.chapters) == 2
    assert doc.chapters[0].title.startswith("1.")


def test_선수관계가_이름으로_연결된다():
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc = document_from_tree(tree, doc_id="t")
    cocomo = next(
        c
        for ch in doc.chapters
        for s in ch.sections
        for c in s.concepts
        if c.key == "COCOMO 모형"
    )
    assert "LOC 기법" in cocomo.prerequisites


def test_화면이_원문을_들고_있다():
    doc = build_document_from_tree(FIXTURE)
    # 첫 목차 개념 5개 → 화면 2개 (3+2)
    ch0 = doc.chapters[0]
    assert len(ch0.sections) == 2
    first = ch0.sections[0]
    assert first.size == 3
    assert "폭포수" in first.source
    assert first.page.startswith("p.")


def test_원문은_조각_본문이_1차_evidence는_폴백():
    """파싱 STATUS 경고: evidence는 3개 중 1~2개만 개념을 정확히 짚는다.

    📎 원문은 "교재의 그 문장"이라는 근거라 틀린 문장을 보이면 안 되고,
    evidence 몇 줄만 주면 설명 재료도 얇아진다. 조각 본문이 1차여야 한다.
    """
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    seg = tree["topics"][0]["segments"][0]["content"]

    doc = document_from_tree(tree, doc_id="t")
    first = doc.chapters[0].sections[0]
    # 발췌를 이어 붙인 것이라 통짜로는 안 들어맞는다. 조각마다 확인한다.
    assert first.source
    for piece in (p.strip() for p in first.source.split("\n\n")):
        if piece and piece != "…":
            assert piece in seg, piece

    # 조각 본문을 지우면 그때 evidence가 메운다
    stripped = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for s in stripped["topics"][0]["segments"]:
        s["content"] = ""
    fallback = document_from_tree(stripped, doc_id="t").chapters[0].sections[0]
    assert fallback.source  # 비지 않는다
    ev = stripped["topics"][0]["concepts"][0].get("evidence") or []
    assert not ev or any(e["text"] in fallback.source for e in ev)


def test_global_key를_들고_다닌다():
    """코스(다자료)가 붙으면 같은 개념을 합치는 근거가 된다. 지금은 보존만."""
    doc = build_document_from_tree(FIXTURE)
    keys = {
        c.key: c.global_key for ch in doc.chapters for s in ch.sections for c in s.concepts
    }
    assert any(keys.values()), "파싱이 준 global_key가 하나도 안 넘어왔다"
    # 표기는 그대로 이름이어야 한다 — 화면·채점이 이름을 쓴다
    assert "COCOMO 모형" in keys


def test_evidence_순으로_정렬():
    doc = build_document_from_tree(FIXTURE)
    keys = [c.key for s in doc.chapters[0].sections for c in s.concepts]
    # evidence 없는 생명주기는 뒤로, 나머지는 char_start 순
    assert keys.index("폭포수 모형") < keys.index("애자일 모형")
    assert keys[-1] == "소프트웨어 생명 주기"


def test_모든_개념이_화면에():
    doc = build_document_from_tree(FIXTURE)
    n = sum(len(s.concepts) for ch in doc.chapters for s in ch.sections)
    assert n == 8  # 5 + 3


def test_ingest_tree는_파싱_id로_올린다():
    """책장→`/curriculum/{uuid}`가 그 id로 열려야 한다. 파일명 stem이면 404다."""
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    tree["document"] = {
        **(tree.get("document") or {}),
        "id": "5528a1e3-b255-45df-9fb9-fcd089d80ee0",
        "filename": "probe.pdf",
        "status": "ready",
    }
    s = Store()
    doc = s.ingest_tree(tree)
    assert doc.doc_id == "5528a1e3-b255-45df-9fb9-fcd089d80ee0"
    assert doc.doc_id in s.documents
    assert len(doc.chapters) == 2


def test_ingest_tree_명시_id가_우선이다():
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    s = Store()
    doc = s.ingest_tree(tree, doc_id="custom-key")
    assert doc.doc_id == "custom-key"
    assert "custom-key" in s.documents


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
