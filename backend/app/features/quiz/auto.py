"""파싱 완료 → 코스 자동 생성 → 문제은행 자동 생성 (확정안 §3).

확정안에서 문제 페이지의 생성 시점은 **"PDF 파싱 직후"**다 — 학습 전에도
언제든 풀 수 있어야 하므로 사용자가 방아쇠를 당기게 하지 않는다.

업로드 흐름은 아직 코스를 만들지 않으므로(위저드의 역할 확인 화면 미구현),
여기서 "자료 1개짜리 코스"를 자동으로 만들어 은행을 건다. 위저드가 코스
확정(자료 역할 화면)을 갖추면 이 자동 생성은 그 호출로 대체하면 된다.

호출 지점은 파싱 파이프라인의 READY 직후 한 곳. **실패해도 파싱은 성공이다**
— 부가 트리거라 예외를 전부 삼키고 로그만 남긴다 (파싱 12.5단계와 같은 원칙).
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.core.database import SessionLocal
from app.features.quiz import jobs

logger = logging.getLogger("uvicorn.error")

# 업로드 흐름에 사용자 개념이 아직 없다(users 테이블 없음 — course.user_id와
# 같은 사정). 자동 생성 코스의 소유자 자리표시자. auth가 생기면 실제 사용자로.
AUTO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

# asyncio는 참조가 없는 태스크를 회수할 수 있다 — 완료까지 붙잡아 둔다.
_tasks: set[asyncio.Task] = set()


def schedule_bank_generation(document_id: uuid.UUID) -> None:
    """파싱 READY 직후 호출. 즉시 반환 — 코스 생성·문항 생성은 백그라운드."""
    task = asyncio.create_task(_run(document_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def _run(document_id: uuid.UUID) -> None:
    try:
        course_id, has_bank = _ensure_course(document_id)
        if course_id is None:
            return
        if has_bank:
            # 재파싱(내용 변경) 경로. 기존 은행을 자동으로 갈아엎지 않는다 —
            # 문항 재생성은 비용이 커서 명시 호출(from-parsing API)로만.
            logger.info("문제은행 이미 존재 — 자동 생성 건너뜀: doc=%s", document_id)
            return
        if jobs.start(course_id, document_id) is None:
            return  # 이미 생성 중 (중복 트리거 방지)

        logger.info(
            "문제은행 자동 생성 시작: doc=%s course=%s", document_id, course_id
        )
        # 지연 import — 파싱 서비스와의 순환 참조 방지
        # (auto ← parsing.service / router → bridge → parsing.service)
        from app.features.quiz.router import _run_generation

        await _run_generation(course_id, document_id, None)
    except Exception:  # noqa: BLE001 — 부가 트리거는 파싱을 깨면 안 된다
        logger.exception("문제은행 자동 생성 실패: doc=%s", document_id)


def _ensure_course(document_id: uuid.UUID) -> tuple[uuid.UUID | None, bool]:
    """이 문서가 담긴 코스를 찾고, 없으면 자료 1개짜리 코스를 만든다.

    반환: (course_id, 그 코스에 이 문서의 문제은행이 이미 있는가)
    """
    from app.features.course.models import CourseDocument
    from app.features.course.service import CourseService
    from app.features.quiz.models import QuizItem

    db = SessionLocal()
    try:
        link = (
            db.query(CourseDocument)
            .filter(CourseDocument.document_id == document_id)
            .first()
        )
        if link is not None:
            course_id = link.course_id
        else:
            course = CourseService(db).create(
                user_id=AUTO_USER_ID, document_ids=[document_id]
            )
            db.commit()
            course_id = course.id
            logger.info(
                "자동 코스 생성: doc=%s → course=%s (%r)",
                document_id, course_id, course.title,
            )

        has_bank = (
            db.query(QuizItem.id)
            .filter(
                QuizItem.course_id == course_id,
                QuizItem.document_id == document_id,
            )
            .first()
            is not None
        )
        return course_id, has_bank
    finally:
        db.close()
