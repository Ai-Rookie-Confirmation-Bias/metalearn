"""커리큘럼 API.

화면 셋 = 엔드포인트 셋 + 기록 하나. integration의 경로는 안 따른다 —
그쪽은 그쪽 파싱에 맞춘 모양이고 지금 파싱과 다르다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .mastery import label
from .planner import weak_for_section
from .schemas import (
    AnswerIn,
    AnswerOut,
    BlockOut,
    ChapterBrief,
    ChapterOut,
    DocumentOut,
    LessonOut,
    SectionOut,
)
from .service import build_lesson
from .store import Chapter, Document, store, summarize

router = APIRouter()


def _doc(doc_id: str) -> Document:
    doc = store.documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, f"자료를 찾을 수 없습니다: {doc_id}")
    return doc


def _sections_out(chapter: Chapter) -> list[SectionOut]:
    out = []
    for s in chapter.sections:
        m = store.progress.of(s.section_id)
        out.append(
            SectionOut(
                section_id=s.section_id,
                order=s.order,
                title=s.title,
                concepts=list(s.concept_keys),
                reason=s.reason,
                page=s.page,
                status=m.status,
                status_label=label(m.status),
                attempts=m.attempts,
                improving=m.improving,
                weak_concepts=list(m.weak_concepts),
            )
        )
    return out


@router.get("/documents", response_model=list[str])
def list_documents() -> list[str]:
    return list(store.documents)


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str) -> DocumentOut:
    """[화면 1] 내 자료 — 준비도와 목차 목록."""
    doc = _doc(doc_id)
    course, plans = summarize(doc, store.progress)
    weakest = course.weakest
    weakest_index = next(
        (c.index for c in doc.chapters if weakest and c.title == weakest.chapter), None
    )
    return DocumentOut(
        doc_id=doc.doc_id,
        title=doc.title,
        readiness=course.readiness,
        complete=course.complete,
        sections_total=sum(len(c.sections) for c in doc.chapters),
        remaining_sections=course.remaining_sections,
        estimated_minutes=course.estimated_minutes(),
        weakest_chapter=weakest_index,
        chapters=[
            ChapterBrief(
                index=ch.index,
                title=ch.title,
                pages=ch.pages,
                sections_total=summary.sections_total,
                sections_done=summary.sections_touched,
                status=summary.status,
                status_label=label(summary.status),
                ratio=summary.ratio,
                progress=round(summary.progress, 3),
                mode=plan.mode,
                reason=plan.reason,
            )
            for ch, summary, plan in zip(doc.chapters, course.chapters, plans)
        ],
    )


@router.get("/documents/{doc_id}/chapters/{index}", response_model=ChapterOut)
def get_chapter(doc_id: str, index: int) -> ChapterOut:
    """[화면 2] 목차 하나 — 절 목록과 왜 이렇게 나왔는지."""
    doc = _doc(doc_id)
    chapter = doc.chapter(index)
    if chapter is None:
        raise HTTPException(404, f"목차를 찾을 수 없습니다: {index}")
    course, plans = summarize(doc, store.progress)
    summary, plan = course.chapters[index], plans[index]
    return ChapterOut(
        doc_id=doc.doc_id,
        doc_title=doc.title,
        index=chapter.index,
        title=chapter.title,
        pages=chapter.pages,
        readiness=course.readiness,
        ratio=summary.ratio,
        progress=round(summary.progress, 3),
        mode=plan.mode,
        reason=plan.reason,
        weak_concepts=list(plan.weak_concepts),
        sections=_sections_out(chapter),
    )


@router.get(
    "/documents/{doc_id}/sections/{section_id}", response_model=LessonOut
)
async def get_lesson(doc_id: str, section_id: str, refresh: bool = False) -> LessonOut:
    """[화면 3] 절 하나 — 설명·비유·빈칸·객관식 + 원문.

    생성이 5~7초라 캐시한다. `?refresh=true`로 다시 만들 수 있다(개발용).
    성향은 아직 안 붙인다 — 온보딩이 없으므로 중립으로 생성한다.

    **최근 틀린 개념은 여기서 붙는다.** 이 절과 이어지는 것만 골라 설명
    에이전트에 넘긴다. 캐시 키에도 들어가므로, 틀린 뒤 다시 열면 다시 생성된다.
    """
    doc = _doc(doc_id)
    found = doc.section(section_id)
    if found is None:
        raise HTTPException(404, f"절을 찾을 수 없습니다: {section_id}")
    chapter, section = found

    all_keys = [k for ch in doc.chapters for s in ch.sections for k in s.concept_keys]
    weak = weak_for_section(section, store.progress.recent_wrong, all_keys)

    lesson = await build_lesson(section, "", weak, refresh=refresh)
    m = store.progress.of(section_id)
    return LessonOut(
        section_id=section.section_id,
        doc_id=doc.doc_id,
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        title=section.title,
        concepts=list(section.concept_keys),
        reason=section.reason,
        page=section.page,
        status=m.status,
        status_label=label(m.status),
        blocks=[
            BlockOut(type=b.type, content=b.content, concept_keys=list(b.concept_keys))
            for b in lesson.blocks
        ],
        source=section.source,
        covered=lesson.covered,
        missing=list(lesson.missing),
        retrieval_gap=list(lesson.retrieval_gap),
        generated=lesson.ok,
        # 요청한 약점(weak)이 아니라 **본문에 실제로 들어간 것**을 보낸다.
        # 화면의 ⚡는 이 값이 있을 때만 뜬다.
        tied_in=list(lesson.tied_in),
    )


@router.post("/documents/{doc_id}/sections/{section_id}/answer", response_model=AnswerOut)
def answer(doc_id: str, section_id: str, body: AnswerIn) -> AnswerOut:
    """인출 결과 한 건을 기록하고 **바뀐 값을 그 자리에서** 돌려준다.

    이게 있어야 "학습 → 분석 → 커리큘럼 변경"이 화면에서 눈에 보인다.
    """
    doc = _doc(doc_id)
    found = doc.section(section_id)
    if found is None:
        raise HTTPException(404, f"절을 찾을 수 없습니다: {section_id}")
    chapter, _ = found

    state = store.record(section_id, body.correct, body.concept_key)
    course, plans = summarize(doc, store.progress)
    summary, plan = course.chapters[chapter.index], plans[chapter.index]
    return AnswerOut(
        section_id=section_id,
        status=state.status,
        status_label=label(state.status),
        attempts=state.attempts,
        improving=state.improving,
        chapter_ratio=summary.ratio,
        chapter_mode=plan.mode,
        chapter_reason=plan.reason,
        readiness=course.readiness,
    )
