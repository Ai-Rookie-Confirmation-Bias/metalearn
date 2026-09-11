"""파싱 직후 문제은행 자동 생성 (quiz/auto) — 분기 로직.

DB·LLM 없이 검증한다: 코스 확보와 실제 생성은 monkeypatch로 바꿔치기하고,
"언제 생성을 걸고 언제 건너뛰는가"만 본다.
"""
import uuid

from app.features.quiz import auto, jobs


async def test_auto_run_triggers_generation_when_no_bank(monkeypatch):
    cid, did = uuid.uuid4(), uuid.uuid4()
    called = []

    monkeypatch.setattr(auto, "_ensure_course", lambda _did: (cid, False))

    async def fake_generation(course_id, document_id, config):
        called.append((course_id, document_id))
        jobs.finish(course_id, document_id, saved=1, discarded=[],
                    report_errors=[], report_warnings=[])

    import app.features.quiz.router as router
    monkeypatch.setattr(router, "_run_generation", fake_generation)

    await auto._run(did)
    assert called == [(cid, did)]
    assert jobs.get(cid, did).status == "done"


async def test_auto_run_skips_when_bank_exists_or_running(monkeypatch):
    cid, did = uuid.uuid4(), uuid.uuid4()
    called = []

    import app.features.quiz.router as router

    async def fake_generation(*args):
        called.append(args)

    monkeypatch.setattr(router, "_run_generation", fake_generation)

    # 은행이 이미 있으면 건너뛴다 (재파싱 시 자동 재생성 금지 — 비용)
    monkeypatch.setattr(auto, "_ensure_course", lambda _did: (cid, True))
    await auto._run(did)
    assert called == []

    # 같은 (코스, 문서) 생성이 이미 돌고 있으면 중복 트리거 금지
    monkeypatch.setattr(auto, "_ensure_course", lambda _did: (cid, False))
    jobs.start(cid, did)  # 돌고 있는 상태를 만들어 둔다
    await auto._run(did)
    assert called == []


async def test_auto_run_swallows_failures(monkeypatch):
    """부가 트리거는 파싱을 깨면 안 된다 — 예외가 밖으로 안 샌다."""

    def boom(_did):
        raise RuntimeError("DB 죽음")

    monkeypatch.setattr(auto, "_ensure_course", boom)
    await auto._run(uuid.uuid4())  # 예외 없이 돌아오면 통과
