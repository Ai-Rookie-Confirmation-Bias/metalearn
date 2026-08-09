"""코스 라우터.

  POST   /courses                        자료 묶어 수업 만들기 (역할 제안 + 목차 복사)
  GET    /courses                        내가 만든 수업 목록
  GET    /courses/{id}                   자료·역할·목차
  GET    /courses/{id}/tree              뼈대 목차 + 본문 자료 설명
  GET    /courses/{id}/prereqs           선수 판정
  GET    /courses/{id}/gaps              끊긴 고리 (외부 조달 후보)

  GET    /courses/{id}/diagnostic         진단 화면 ①~④ (LLM 없음)
  GET    /courses/{id}/diagnostic/cards   ③ 카드 4장 (LLM 1콜)
  PATCH  /courses/{id}/diagnostic         ①③ 목표·기간·형식 저장
  POST   /courses/{id}/diagnostic/subjects ④-1 과목 단위 답 → 펼칠 과목
  POST   /courses/{id}/diagnostic/prereqs  ④-2 펼친 과목의 항목별 답
  GET    /courses/{id}/diagnostic/probes  ⑤ 확인 문항
  POST   /courses/{id}/diagnostic/probes  ⑤ 채점

  POST   /courses/{id}/supply             26·27 보강 자료 마련 + 목차에 끼우기
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_id
from app.features.course.diagnostic import DiagnosticService
from app.features.course.models import Course
from app.features.course.schemas import (
    CourseCreate,
    CourseOut,
    CourseTree,
    DiagnosticCardsOut,
    DiagnosticConfigIn,
    DiagnosticSetupOut,
    GapOut,
    PrereqAnswersIn,
    PrereqOut,
    ProbeGradeOut,
    ProbeOut,
    ProbeResultsIn,
    SubjectAnswersIn,
    SubjectAnswersOut,
    SupplyOut,
)
from app.features.course.service import CourseService
from app.features.course.supply import SupplyService

_log = logging.getLogger("uvicorn.error")
router = APIRouter()


@router.post("", response_model=CourseOut, status_code=201)
def create_course(
    body: CourseCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> CourseOut:
    service = CourseService(db)
    try:
        course = service.create(
            user_id=user_id,
            document_ids=body.document_ids,
            title=body.title,
            roles=body.roles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return CourseOut.model_validate(course)


@router.get("", response_model=list[CourseOut])
def list_courses(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[CourseOut]:
    """내가 만든 수업. 책장은 curriculum 목록을 쓰지만 문제집·관리는 여기다."""
    return [
        CourseOut.model_validate(c) for c in CourseService(db).list_for(user_id)
    ]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: uuid.UUID, db: Session = Depends(get_db)) -> CourseOut:
    try:
        return CourseOut.model_validate(CourseService(db).get(course_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/tree", response_model=CourseTree)
async def get_course_tree(
    course_id: uuid.UUID,
    force_link: bool = False,
    db: Session = Depends(get_db),
) -> CourseTree:
    """**뼈대 목차 순서 + 본문 자료의 설명.**

    PPT에는 표제어만 있고 교재에 설명이 세 쪽 있을 때, 각 개념에 그 설명이
    `body`로 붙어 나온다. 개념 연결은 첫 호출에서 계산해 문서쌍 단위로 저장
    하므로 같은 두 책을 쓰는 다음 코스는 계산이 없다.

    문서 트리(GET /parsing/documents/{id}/tree)는 책 한 권 안만 본다.
    """
    try:
        return await CourseService(db).tree(course_id, force_link=force_link)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/prereqs", response_model=list[PrereqOut])
async def get_prereqs(
    course_id: uuid.UUID,
    refresh: bool = False,
    status: str | None = Query(None, description="pass|gray|rejected 로 거르기"),
    db: Session = Depends(get_db),
) -> list[PrereqOut]:
    """이 코스를 시작하기 전에 알아야 하는 것.

    첫 호출에서 계산하고 저장한다(임베딩 1회). 이후는 조회뿐이다.
    자료 구성을 바꿨으면 refresh=true.

    기각된 항목도 돌려주는 게 기본이다 — 왜 빠졌는지 되짚을 수 있어야 문턱을
    옮길 근거가 생긴다. 화면에는 status=pass,gray만 쓴다.
    """
    try:
        rows = await CourseService(db).prereqs(course_id, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if status:
        wanted = {s.strip() for s in status.split(",") if s.strip()}
        rows = [r for r in rows if r.status in wanted]
    return [PrereqOut.model_validate(r) for r in rows]


@router.get("/{course_id}/gaps", response_model=list[GapOut])
def get_gaps(course_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GapOut]:
    try:
        return [GapOut(**g) for g in CourseService(db).gaps(course_id)]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ── 24 진단 ──────────────────────────────────────────────────────
#
# 시험이 아니라 설정이다. 화면 다섯.
#   ① 왜 배우나 ② 분야 맞나 ③ 카드 4장 ④ 선수 체크 ⑤ 확인 문항
#
# ④가 두 단계인 이유: 항목을 전부 물으면 실측 54개다. 과목으로 먼저 묻고
# ("들어봤다"인 것만 펼친다) 실측 7 + 23 = 30번으로 줄었다.
#
# setup/cards가 갈린 이유: setup은 LLM을 안 불러 즉시 뜨고, cards만 한 콜이
# 든다. 한 엔드포인트로 묶으면 첫 화면이 카드 생성을 기다린다.


def _course(course_id: uuid.UUID, db: Session) -> Course:
    try:
        return CourseService(db).get(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{course_id}/diagnostic", response_model=DiagnosticSetupOut)
async def diagnostic_setup(
    course_id: uuid.UUID, db: Session = Depends(get_db)
) -> DiagnosticSetupOut:
    """화면 ①~④가 필요한 것 전부.

    선수 목록이 아직 없으면 여기서 계산한다(16'). 그 다음부터는 조회뿐이다.
    """
    course = _course(course_id, db)
    service = DiagnosticService(db)
    if not service.setup(course)["subjects"]:
        await CourseService(db).prereqs(course_id)
        db.commit()
    return DiagnosticSetupOut(**service.setup(course))


@router.get("/{course_id}/diagnostic/cards", response_model=DiagnosticCardsOut)
async def diagnostic_cards(
    course_id: uuid.UUID, db: Session = Depends(get_db)
) -> DiagnosticCardsOut:
    """③ 같은 개념을 네 형식으로. LLM 1콜."""
    course = _course(course_id, db)
    return DiagnosticCardsOut(**await DiagnosticService(db).cards(course))


@router.patch("/{course_id}/diagnostic", response_model=DiagnosticSetupOut)
def diagnostic_configure(
    course_id: uuid.UUID,
    body: DiagnosticConfigIn,
    db: Session = Depends(get_db),
) -> DiagnosticSetupOut:
    """①③ 저장 — 목표·기간·설명 형식. 모르는 값은 조용히 무시한다."""
    course = _course(course_id, db)
    service = DiagnosticService(db)
    service.configure(
        course,
        goal=body.goal,
        deadline_weeks=body.deadline_weeks,
        style=body.style,
    )
    db.commit()
    return DiagnosticSetupOut(**service.setup(course))


@router.post("/{course_id}/diagnostic/subjects", response_model=SubjectAnswersOut)
def diagnostic_subjects(
    course_id: uuid.UUID,
    body: SubjectAnswersIn,
    db: Session = Depends(get_db),
) -> SubjectAnswersOut:
    """④-1 과목 단위로 먼저 묻는다. `{과목명: known|heard|unknown}`.

    "들어봤다"인 과목만 `expand`로 돌려준다 — 그것만 항목을 펼쳐 다시 묻는다.
    아는 것과 모르는 것은 더 물어도 얻을 게 없다.
    """
    course = _course(course_id, db)
    service = DiagnosticService(db)
    expand = service.record_subjects(course, answers=body.answers)
    db.commit()
    return SubjectAnswersOut(
        expand=expand, setup=DiagnosticSetupOut(**service.setup(course))
    )


@router.post("/{course_id}/diagnostic/prereqs", response_model=DiagnosticSetupOut)
def diagnostic_answers(
    course_id: uuid.UUID,
    body: PrereqAnswersIn,
    db: Session = Depends(get_db),
) -> DiagnosticSetupOut:
    """④-2 펼친 과목의 항목별 답. `{prereq_id: known|heard|unknown}`."""
    course = _course(course_id, db)
    service = DiagnosticService(db)
    service.record(course, answers=body.answers)
    db.commit()
    return DiagnosticSetupOut(**service.setup(course))


@router.get("/{course_id}/diagnostic/probes", response_model=list[ProbeOut])
async def diagnostic_probes(
    course_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ProbeOut]:
    """⑤ "안다"고 한 것 중 몇 개만 실제로 물어본다.

    개수는 고정이 아니다 — "안다"가 많을수록 몇 개 더 본다(상한 4).
    정답을 못 세운 항목은 문항을 안 낸다. 빈 목록이면 이 화면을 건너뛴다.
    """
    course = _course(course_id, db)
    return [
        ProbeOut(**q.__dict__) for q in await DiagnosticService(db).probes(course)
    ]


@router.post("/{course_id}/diagnostic/probes", response_model=ProbeGradeOut)
def diagnostic_grade(
    course_id: uuid.UUID,
    body: ProbeResultsIn,
    db: Session = Depends(get_db),
) -> ProbeGradeOut:
    """⑤ 채점. 한 답이 과목 하나를 정한다."""
    course = _course(course_id, db)
    result = DiagnosticService(db).grade(course, results=body.results)
    db.commit()
    return ProbeGradeOut(**result)


@router.post("/{course_id}/supply", response_model=SupplyOut)
async def supply(
    course_id: uuid.UUID,
    refresh: bool = Query(False, description="이미 끼운 단원의 plan을 다시 맞춘다"),
    db: Session = Depends(get_db),
) -> SupplyOut:
    """26·27 — 진단이 "모른다"고 한 과목의 자료를 마련하고 목차 앞에 끼운다.

    **여러 번 불러도 안전하다.** 자료는 (분야, 과목) 지문으로 한 번만 만들고,
    이미 끼운 단원은 `plan`만 다시 맞춘다 — 진단을 다시 해도 사용자가 고친
    목차 순서가 안 날아간다.
    """
    course = _course(course_id, db)
    result = await SupplyService(db).run(course, refresh=refresh)
    db.commit()

    # **목차가 바뀌었으면 학습 store도 다시 조립한다.**
    # 안 하면 보강 단원을 끼워 놓고도 학습 화면엔 안 나온다 — 실측에서 4단원을
    # 넣었는데 화면은 3단원 그대로였다. 클라이언트가 잊을 수 있는 자리라
    # 서버가 책임진다. (지연 import — bridge가 이 패키지를 쓴다)
    if result["inserted"] or result["updated"]:
        from app.features.curriculum.bridge import ingest_course

        try:
            await ingest_course(db, course_id, refresh=True)
        except Exception as exc:  # noqa: BLE001 — 조달 자체는 성공했다
            _log.warning("보강 뒤 학습 store 갱신 실패 %s: %s", course_id, exc)
    return SupplyOut(**result)
