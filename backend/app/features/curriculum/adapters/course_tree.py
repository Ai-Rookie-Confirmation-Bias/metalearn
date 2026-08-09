"""코스 트리(`GET /api/courses/{id}/tree`) → 우리 Document.

`parsing_tree`와 나란한 어댑터다. 다른 점은 **자료 하나가 아니라 수업 하나**를
받는다는 것 하나뿐이다:

    parsing_tree   책 한 권. 목차는 `doc_topics`(교재 목차 그대로)
    course_tree    수업 하나. 목차는 `course_topics`(그 사람의 목차 복사본)

`course_topics`를 쓰기 때문에 학습 화면이 처음으로 이것들을 볼 수 있게 된다:

  · 자료 여러 개가 한 권으로 — 뼈대(PPT) 목차 순서에 본문(교재) 설명이 붙는다
  · 사용자가 고친 목차 — 제목 변경·순서 이동·합치기·쪼개기
  · 보강 단원(`origin=inserted`) — 진단이 끼운 책 밖 선수 단원

⚠️ **목차는 여기 도착하기 전에 이미 확정돼 있다.** 보강 단원 삽입은 코스 층
(진단 시점)에서 끝나고, 학습 중에 목차가 늘어나는 일은 없다. `grouping`의
"목차는 고정" 원칙과 부딪히지 않는 이유가 이것이다.

두 트리의 모양이 같아서(`topics[].concepts[].evidence[]`) 변환은 겉껍데기를
맞춰 주는 게 전부이고, 자르기·화면 만들기는 `document_from_tree`를 그대로 쓴다.
"""
from __future__ import annotations

from typing import Any

from ..models import Document
from .parsing_tree import document_from_tree


def document_from_course_tree(
    tree: dict[str, Any], *, doc_id: str | None = None
) -> Document:
    """CourseTree dict → 커리큘럼 Document.

    `doc_id`를 안 주면 코스 id를 쓴다. 책장 링크 `/curriculum/{id}`가 그 값으로
    열리고, 파싱 문서 id와 같은 자리에서 돈다(둘 다 UUID 문자열).
    """
    course_id = str(tree.get("course_id") or "course")
    return document_from_tree(
        {
            # 문서 트리의 `document` 자리. 어댑터는 여기서 제목과 id만 읽는다.
            # 확장자가 없으므로 `document_from_tree`의 스템 자르기가 그냥 통과한다.
            "document": {"id": course_id, "filename": tree.get("title") or course_id},
            "topics": tree.get("topics") or [],
            # 24 진단이 정한 것 — 설명 형식과 분량이 여기서 갈린다.
            "style": tree.get("style"),
            "goal": tree.get("goal"),
            "deadline_weeks": tree.get("deadline_weeks"),
        },
        doc_id=doc_id or course_id,
    )
