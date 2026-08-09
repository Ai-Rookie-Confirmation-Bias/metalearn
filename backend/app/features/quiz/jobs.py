"""문제은행 생성 작업 상태 — 비동기 전환(202 접수 + 폴링)의 인메모리 저장소.

생성은 조각마다 LLM을 여러 번 부르는 분 단위 작업이라(실측 888초) HTTP 요청이
끝날 때까지 붙잡으면 타임아웃이 난다. 접수 즉시 202를 돌려주고 여기 상태를
폴링하게 한다 (파싱의 DocStatus 폴링과 같은 사용법).

인메모리인 이유: 상태의 수명이 프로세스와 같다 — 서버가 재시작되면 돌던 생성
자체가 죽으므로, DB에 상태를 남겨도 "running" 좀비 행만 남는다. 단일 프로세스
(compose uvicorn) 전제. 워커를 늘리면 DB 테이블로 옮겨야 한다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class GenJob:
    status: str = "running"  # running | done | failed
    saved: int = 0
    discarded: list[str] = field(default_factory=list)
    report_errors: list[str] = field(default_factory=list)
    report_warnings: list[str] = field(default_factory=list)
    error: str | None = None


_jobs: dict[tuple[str, str], GenJob] = {}


def _key(course_id: uuid.UUID, document_id: uuid.UUID) -> tuple[str, str]:
    return (str(course_id), str(document_id))


def get(course_id: uuid.UUID, document_id: uuid.UUID) -> GenJob | None:
    return _jobs.get(_key(course_id, document_id))


def start(course_id: uuid.UUID, document_id: uuid.UUID) -> GenJob | None:
    """새 작업 등록. 같은 (코스, 문서)가 이미 돌고 있으면 None (중복 실행 차단)."""
    key = _key(course_id, document_id)
    existing = _jobs.get(key)
    if existing is not None and existing.status == "running":
        return None
    job = GenJob()
    _jobs[key] = job
    return job


def finish(
    course_id: uuid.UUID,
    document_id: uuid.UUID,
    *,
    saved: int,
    discarded: list[str],
    report_errors: list[str],
    report_warnings: list[str],
) -> None:
    _jobs[_key(course_id, document_id)] = GenJob(
        status="done",
        saved=saved,
        discarded=discarded,
        report_errors=report_errors,
        report_warnings=report_warnings,
    )


def fail(course_id: uuid.UUID, document_id: uuid.UUID, error: str) -> None:
    _jobs[_key(course_id, document_id)] = GenJob(status="failed", error=error)
