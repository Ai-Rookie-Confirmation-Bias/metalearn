"""코스 트리 어댑터 — 수업 하나(자료 여러 개)를 학습 화면으로.

여기서 지키는 것:
  ① 코스 id가 곧 doc_id — 책장 링크가 그 값으로 열린다
  ② 목차는 `course_topics`다 (교재 목차가 아니라 그 사람의 목차)
  ③ 자료 하나 경로는 동작이 하나도 안 바뀐다

**자르기는 여기서 안 한다.** 코스 트리는 조각을 통째로 실어 오고, 화면으로
자르는 건 `group_into_sections`/`split_by_concepts`가 원래 하던 일이다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.adapters.course_tree import (  # noqa: E402
    document_from_course_tree,
)
from app.features.curriculum.store import FIXTURE_DIR, Store  # noqa: E402

FIXTURE = FIXTURE_DIR / "sample_sdlc.tree.json"

# 본문 자료(교재)의 조각. 개념 링크가 없어도 단원에 통째로 실린다.
BODY_SEGMENT = {
    "id": "22222222-2222-2222-2222-222222222222",
    "seq": 1000,  # 뼈대(0~n) 뒤에 오도록 민 값
    "heading": None,
    "content": "폭포수 모형은 각 단계를 확실히 끝내고 다음으로 넘어간다.",
    "page_from": 51,
    "page_to": 53,
    "document_id": "33333333-3333-3333-3333-333333333333",
    "filename": "요약노트.pdf",
    "role": "body",
}


def _course_tree(*, with_body: bool = True) -> dict:
    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    topics = tree["topics"]
    if with_body:
        topics[0]["segments"] = list(topics[0]["segments"]) + [BODY_SEGMENT]
    return {
        "course_id": "11111111-1111-1111-1111-111111111111",
        "title": "정보처리기사",
        "skeleton_document_id": "d1",
        "body_document_ids": ["33333333-3333-3333-3333-333333333333"],
        "topics": topics,
    }


def test_코스가_자료와_같은_자리에서_돈다():
    """코스 id가 곧 doc_id. 책장→`/curriculum/{id}`가 그 값으로 열린다."""
    doc = document_from_course_tree(_course_tree())
    assert doc.doc_id == "11111111-1111-1111-1111-111111111111"
    assert doc.title == "정보처리기사"
    assert doc.chapters and doc.chapters[0].sections


def test_목차는_코스_것을_쓴다():
    tree = _course_tree()
    tree["topics"][0]["title"] = "내가 바꾼 제목"
    doc = document_from_course_tree(tree)
    assert doc.chapters[0].title == "내가 바꾼 제목"


def test_본문_조각이_뼈대_뒤에_온다():
    """받는 쪽이 seq로 정렬한다. 섞이면 뼈대가 정한 학습 순서가 흐트러진다."""
    from app.features.curriculum.adapters.parsing_tree import _joined_source

    joined = _joined_source(_course_tree()["topics"][0])
    assert "폭포수" in joined
    assert joined.index("폭포수") < joined.index(BODY_SEGMENT["content"])


def test_본문이_없어도_열린다():
    """자료 하나짜리 코스 — `segments`에 뼈대만 있다."""
    doc = document_from_course_tree(_course_tree(with_body=False))
    assert sum(len(ch.sections) for ch in doc.chapters) > 0


def test_자료_트리는_그대로다():
    """파싱 문서 경로는 코스 작업의 영향을 받지 않는다."""
    from app.features.curriculum.adapters.parsing_tree import document_from_tree
    from app.features.curriculum.store import build_document_from_tree

    tree = json.loads(FIXTURE.read_text(encoding="utf-8"))
    a = document_from_tree(tree, doc_id="sample_sdlc")
    b = build_document_from_tree(FIXTURE)
    assert [ch.title for ch in a.chapters] == [ch.title for ch in b.chapters]
    assert [s.source for ch in a.chapters for s in ch.sections] == [
        s.source for ch in b.chapters for s in ch.sections
    ]


def test_store에_올라간다():
    store = Store()
    doc = store.ingest_course_tree(_course_tree())
    assert store.documents[doc.doc_id] is doc
