"""문제은행 생성 잡 저장소 — 202 접수 + 폴링의 상태 전이."""
import uuid

from app.features.quiz import jobs


def test_job_lifecycle_and_duplicate_guard():
    cid, did = uuid.uuid4(), uuid.uuid4()

    assert jobs.get(cid, did) is None  # 접수 이력 없음 = idle

    job = jobs.start(cid, did)
    assert job is not None and job.status == "running"
    assert jobs.start(cid, did) is None  # 돌고 있는데 또 접수 → 차단 (409 재료)

    jobs.finish(cid, did, saved=5, discarded=["x: 사유"], report_errors=[], report_warnings=["w"])
    done = jobs.get(cid, did)
    assert done.status == "done" and done.saved == 5 and done.report_warnings == ["w"]

    assert jobs.start(cid, did) is not None  # 끝난 뒤엔 재실행(교체) 허용


def test_job_failure_records_error():
    cid, did = uuid.uuid4(), uuid.uuid4()
    jobs.start(cid, did)
    jobs.fail(cid, did, "LLM 타임아웃")
    failed = jobs.get(cid, did)
    assert failed.status == "failed" and "타임아웃" in failed.error
    assert jobs.start(cid, did) is not None  # 실패 후 재시도 허용
