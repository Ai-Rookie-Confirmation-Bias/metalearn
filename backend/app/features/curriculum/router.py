"""커리큘럼 API.

화면 셋 = 엔드포인트 셋 + 기록 하나. integration의 경로는 안 따른다 —
그쪽은 그쪽 파싱에 맞춘 모양이고 지금 파싱과 다르다.
"""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id

from .blocks import ConceptBrief
from .bridge import ingest_parsing_document, sync_ready_documents
from .mastery import DAY, WEIGHT, label
from .planner import formative_ready, weak_for_section
from .schemas import (
    AnswerIn,
    AnswerOut,
    BlockOut,
    ChapterBrief,
    ChapterOut,
    DocumentOut,
    FormativeOut,
    IngestOut,
    LessonOut,
    ReviewItem,
    ReviewOut,
    SectionOut,
)
from .service import build_formative, build_lesson, build_review, prewarm_document
from .store import Chapter, Document, Progress, store, summarize, with_supplements

# 한 번에 보여줄 복습 화면 수. 다 보여주면 어디부터 할지 학습자가 정해야 하고,
# 화면마다 LLM 콜이 하나씩 붙는다.
REVIEW_BATCH = 5

router = APIRouter()


def _me(user_id: uuid.UUID) -> Progress:
    """이 요청을 낸 사람의 진도. 자료는 공용이고 진도만 사람별이다."""
    return store.progress_of(str(user_id))


def _doc(doc_id: str, db: Session | None, progress: Progress) -> Document:
    """이 자료 — **보충 화면이 끼워진 상태로.**

    파싱이 준 문서(`store.documents`)는 그대로 두고 읽을 때 계산한다. 순수
    함수라 같은 상태면 같은 결과가 나오고, 어느 엔드포인트로 들어와도 같은
    화면 목록을 본다. 여기 한 곳만 지나면 목차·학습·평가·채점이 다 따라온다.

    보충이 **진도의 함수**라서 사람마다 다른 문서가 나온다 — 같은 책이라도
    많이 틀린 사람에게만 보충 화면이 끼워진다.

    store에 없고 id가 UUID면 파싱 DB에서 한 번 당겨 본다 — 책장 sync 전에
    딥링크로 들어오거나 서버가 재시작된 자리.
    """
    if doc_id not in store.documents and db is not None:
        try:
            uid = uuid.UUID(doc_id)
        except ValueError:
            uid = None
        if uid is not None:
            try:
                ingest_parsing_document(db, uid)
            except LookupError:
                pass
    doc = store.documents.get(doc_id)
    if doc is None:
        raise HTTPException(404, f"자료를 찾을 수 없습니다: {doc_id}")
    return with_supplements(doc, progress)


def _sections_out(chapter: Chapter, progress: Progress) -> list[SectionOut]:
    out = []
    for s in chapter.sections:
        m = progress.of(s.section_id)
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
                recall=round(m.recall(), 3),
                needs_review=m.needs_review(),
                by_kind=dict(m.by_kind),
                # 우리가 끼운 보충 화면인가. 화면이 구분해 보여줘야 학습자가
                # 교재에 원래 있던 내용이라고 오해하지 않는다.
                inserted=s.inserted,
            )
        )
    return out


@router.get("/documents", response_model=list[str])
def list_documents(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[str]:
    """**내** 책장 — 학습 가능한 자료 id 목록.

    파일 픽스처 + 내가 올린 ready 문서(아직 store에 없으면 여기서 주입).
    책장이 이 목록만 보므로, 이 한 줄이 파싱→학습 이음매다.

    픽스처는 누구에게나 보인다. DB 행이 없는 데모 자료라 소유를 붙일 자리가
    없고, 붙였다면 새 계정으로 처음 들어온 사람이 빈 화면만 본다.

    store를 그대로 늘어놓지 않는 이유: store는 서버가 지금까지 읽은 자료
    **전부**라 남이 올린 것도 들어 있다. 소유는 매번 DB에서 다시 센다.
    """
    mine = sync_ready_documents(db, user_id=user_id)
    owned = set(mine)
    return [k for k in store.documents if k in store.fixture_ids or k in owned]


@router.post(
    "/documents/from-parsing/{document_id}",
    response_model=IngestOut,
)
def ingest_from_parsing(
    document_id: uuid.UUID,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> IngestOut:
    """파싱 문서 하나를 학습 store에 올린다(또는 갱신).

    책장 목록이 자동 sync를 하지만, 업로드 직후·재파싱 뒤에는 이걸로 명시한다.
    """
    try:
        doc = ingest_parsing_document(db, document_id, refresh=refresh)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return IngestOut(
        doc_id=doc.doc_id,
        title=doc.title,
        chapters=len(doc.chapters),
        sections=sum(len(ch.sections) for ch in doc.chapters),
        source="parsing",
    )


@router.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(
    doc_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """[화면 1] 내 자료 — 준비도와 목차 목록."""
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    course, plans = summarize(doc, progress)
    weakest = course.weakest
    weakest_index = next(
        (c.index for c in doc.chapters if weakest and c.title == weakest.chapter), None
    )
    return DocumentOut(
        doc_id=doc.doc_id,
        title=doc.title,
        readiness=course.readiness,
        understanding=course.understanding,
        complete=course.complete,
        # 보충 화면은 빼고 센다 — 진도 분모와 같은 기준이어야 한다.
        sections_total=sum(c.sections_total for c in course.chapters),
        remaining_sections=course.remaining_sections,
        sections_due=course.sections_due,
        estimated_minutes=course.estimated_minutes(),
        weakest_chapter=weakest_index,
        by_kind=course.by_kind,
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
                recall=summary.recall,
                sections_due=summary.sections_due,
                mode=plan.mode,
                reason=plan.reason,
            )
            for ch, summary, plan in zip(doc.chapters, course.chapters, plans)
        ],
    )


@router.get("/documents/{doc_id}/chapters/{index}", response_model=ChapterOut)
def get_chapter(
    doc_id: str,
    index: int,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ChapterOut:
    """[화면 2] 목차 하나 — 절 목록과 왜 이렇게 나왔는지."""
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    chapter = doc.chapter(index)
    if chapter is None:
        raise HTTPException(404, f"목차를 찾을 수 없습니다: {index}")
    course, plans = summarize(doc, progress)
    summary, plan = course.chapters[index], plans[index]
    ready, why = formative_ready(summary)
    return ChapterOut(
        doc_id=doc.doc_id,
        doc_title=doc.title,
        index=chapter.index,
        title=chapter.title,
        pages=chapter.pages,
        readiness=course.readiness,
        ratio=summary.ratio,
        progress=round(summary.progress, 3),
        recall=summary.recall,
        sections_due=summary.sections_due,
        mode=plan.mode,
        reason=plan.reason,
        weak_concepts=list(plan.weak_concepts),
        sections=_sections_out(chapter, progress),
        # 목차 마지막 항목(단원 평가)의 잠금 여부. 여기서 판정해 보내야
        # 화면이 문턱을 알 필요가 없다. 평가 자체를 부르면 생성이 돌아 비싸다.
        formative_ready=ready,
        formative_reason=why,
    )


@router.get(
    "/documents/{doc_id}/chapters/{index}/formative", response_model=FormativeOut
)
async def get_formative(
    doc_id: str,
    index: int,
    refresh: bool = False,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FormativeOut:
    """[화면 4] 단원 평가 — 화면을 가로질러 구별할 수 있는가.

    **여기만 잠근다.** 학습은 절대 안 잠근다(integration이 학습을 잠갔다가
    이탈을 겪었다). 잠금 판정은 `planner.formative_ready` — 진도로만 본다.
    """
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    chapter = doc.chapter(index)
    if chapter is None:
        raise HTTPException(404, f"목차를 찾을 수 없습니다: {index}")

    course, _plans = summarize(doc, progress)
    summary = course.chapters[index]
    ready, reason = formative_ready(summary)

    base = dict(
        doc_id=doc.doc_id,
        chapter_index=index,
        chapter_title=chapter.title,
        progress=round(summary.progress, 3),
    )
    if not ready:
        # 잠긴 상태로 문항을 만들면 돈만 쓰고 안 보여준다.
        return FormativeOut(**base, locked=True, reason=reason)

    screens = [
        (
            s.title,
            tuple(ConceptBrief(c.key, c.definition) for c in s.concepts),
            progress.of(s.section_id).attempts,
        )
        for s in chapter.sections
    ]
    ev = await build_formative(
        chapter.title, screens, summary.weak_concepts, refresh=refresh
    )

    # 문항은 화면을 가로지르는데 숙련도는 화면 단위다. **정답 개념을 가진 화면**에
    # 기록한다 — "단원 평가에서 이 화면 개념을 틀렸다"가 정확한 뜻이다.
    # 프론트가 고르게 두면 화면이 판단을 하게 되고, 그건 이 설계가 피하는 것이다.
    owner = {c.key: s.section_id for s in chapter.sections for c in s.concepts}
    fallback = chapter.sections[0].section_id if chapter.sections else ""

    return FormativeOut(
        **base,
        blocks=[
            BlockOut(
                type=b.type,
                content={
                    **b.content,
                    "sectionId": owner.get(str(b.content.get("concept") or ""), fallback),
                },
                concept_keys=list(b.concept_keys),
            )
            for b in ev.blocks
        ],
        crossing=ev.crossing,
        covered_weak=list(ev.covered_weak),
        generated=ev.ok,
    )


@router.get(
    "/documents/{doc_id}/sections/{section_id}", response_model=LessonOut
)
async def get_lesson(
    doc_id: str,
    section_id: str,
    refresh: bool = False,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> LessonOut:
    """[화면 3] 절 하나 — 설명·비유·빈칸·객관식 + 원문.

    생성이 5~7초라 캐시한다. `?refresh=true`로 다시 만들 수 있다(개발용).

    **성향**은 `CURRICULUM_PROFILE` fixture(기본 metaphor)로 붙인다 — 온보딩 UI 전.
    **분량**은 이 목차의 `plan.mode`를 설명 지시에 넣는다.
    **최근 틀린 개념**도 이어지는 것만 골라 넘긴다.
    """
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    found = doc.section(section_id)
    if found is None:
        raise HTTPException(404, f"절을 찾을 수 없습니다: {section_id}")
    chapter, section = found

    _, plans = summarize(doc, progress)
    plan = plans[chapter.index]

    all_keys = [k for ch in doc.chapters for s in ch.sections for k in s.concept_keys]
    weak = weak_for_section(section, progress.recent_wrong, all_keys)
    # 이 화면에 없는 문서 개념 — 인출 정답이 여기 걸리면 라벨 사고로 폐기
    foreign = tuple(k for k in all_keys if k not in section.concept_keys)

    lesson = await build_lesson(
        section,
        store.profile_block(),
        weak,
        foreign_keys=foreign,
        mode=plan.mode,
        refresh=refresh,
    )
    m = progress.of(section_id)
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



@router.post("/documents/{doc_id}/prewarm")
async def prewarm(
    doc_id: str,
    limit: int = 6,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """데모용 — 앞 N개 화면을 미리 만들어 캐시에 올린다.

    화면당 5~7초라 영상에서 기다리면 안 된다. 찍기 전에 한 번 호출한다.
    """
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    return await prewarm_document(
        doc, progress, limit=limit, profile_block=store.profile_block()
    )


@router.get("/documents/{doc_id}/review", response_model=ReviewOut)
async def get_review(
    doc_id: str,
    days: int = 0,
    limit: int = REVIEW_BATCH,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> ReviewOut:
    """[화면 5] 복습 큐 — 망각곡선이 불러온 화면들.

    `days`는 **시연용 시계 이동**이다. 첫 복습은 맞힌 뒤 2.2일에 오는데
    발표에서 그걸 기다릴 수 없다. `recall(now)`가 원래 시각을 받게 되어 있어
    **진짜 곡선을 시간만 옮겨** 보여준다 — 가짜 데이터가 아니라서 심사에서
    그대로 설명할 수 있다.

    문항은 **새로 만든다.** 그때 그 빈칸을 다시 내면 개념이 아니라 그 문장을
    외웠는지를 재게 된다. 설명은 안 준다(복습이지 재학습이 아니다).
    """
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    now = time.time() + days * DAY

    due = [
        (ch, s, progress.of(s.section_id))
        for ch in doc.chapters
        for s in ch.sections
        if progress.of(s.section_id).needs_review(now)
    ]
    # 많이 잊은 것부터. 다 보여주면 어디부터 할지 학습자가 정해야 한다.
    due.sort(key=lambda t: t[2].recall(now))

    items = []
    for ch, section, m in due[:limit]:
        blocks = await build_review(section, m.attempts)
        items.append(
            ReviewItem(
                section_id=section.section_id,
                title=section.title,
                chapter_index=ch.index,
                chapter_title=ch.title,
                recall=round(m.recall(now), 3),
                days_since=round((now - (m.last_success or now)) / DAY, 1),
                blocks=[
                    BlockOut(type=b.type, content=b.content, concept_keys=list(b.concept_keys))
                    for b in blocks
                ],
            )
        )

    return ReviewOut(
        doc_id=doc.doc_id, shifted_days=days, total_due=len(due), items=items
    )


@router.post("/documents/{doc_id}/sections/{section_id}/answer", response_model=AnswerOut)
def answer(
    doc_id: str,
    section_id: str,
    body: AnswerIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> AnswerOut:
    """시도 한 건을 기록하고 **바뀐 값을 그 자리에서** 돌려준다.

    이게 있어야 "학습 → 분석 → 커리큘럼 변경"이 화면에서 눈에 보인다.
    진단·인출·복습·형성이 전부 여기로 들어와 하나의 누적으로 쌓인다(`body.kind`).
    """
    progress = _me(user_id)
    doc = _doc(doc_id, db, progress)
    found = doc.section(section_id)
    if found is None:
        raise HTTPException(404, f"절을 찾을 수 없습니다: {section_id}")
    if body.kind not in WEIGHT:
        raise HTTPException(422, f"알 수 없는 출처입니다: {body.kind}")
    chapter, _ = found

    state = store.record(
        str(user_id), section_id, body.correct, body.concept_key, body.kind
    )
    course, plans = summarize(doc, progress)
    summary, plan = course.chapters[chapter.index], plans[chapter.index]
    return AnswerOut(
        section_id=section_id,
        status=state.status,
        status_label=label(state.status),
        attempts=state.attempts,
        improving=state.improving,
        recall=round(state.recall(), 3),
        chapter_ratio=summary.ratio,
        chapter_mode=plan.mode,
        chapter_reason=plan.reason,
        readiness=course.readiness,
        understanding=course.understanding,
    )
