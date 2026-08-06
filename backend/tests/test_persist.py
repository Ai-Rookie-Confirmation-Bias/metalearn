"""진도 스냅샷 — 재시작해도 준비도가 0으로 안 돌아가게."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.mastery import FORMATIVE, RETRIEVAL, record  # noqa: E402
from app.features.curriculum.persist import (  # noqa: E402
    load_progress,
    progress_from_dict,
    progress_to_dict,
    save_progress,
)
from app.features.curriculum.store import Progress  # noqa: E402


def test_왕복해도_값이_같다(tmp_path: Path):
    p = Progress()
    p.sections["s1"] = record(p.of("s1"), True, "응집도", RETRIEVAL, at=1_700_000_000.0)
    p.sections["s1"] = record(p.sections["s1"], False, "결합도", FORMATIVE, at=1_700_000_100.0)
    p.recent_wrong = ["결합도"]

    path = tmp_path / "progress.json"
    save_progress(p, path)
    got = load_progress(path)

    assert set(got.sections) == {"s1"}
    s = got.sections["s1"]
    assert s.attempts == 2
    assert s.wrong_by_concept == {"결합도": 1}
    assert s.by_kind == {RETRIEVAL: 1, FORMATIVE: 1}
    assert s.last_success == 1_700_000_000.0
    assert s.streak == 0  # 마지막이 오답
    assert got.recent_wrong == ["결합도"]


def test_파일_없으면_빈_진도(tmp_path: Path):
    assert load_progress(tmp_path / "없음.json").sections == {}


def test_깨진_파일이면_빈_진도(tmp_path: Path):
    path = tmp_path / "broken.json"
    path.write_text("{아니}", encoding="utf-8")
    assert load_progress(path).sections == {}


def test_dict_왕복():
    p = Progress()
    p.sections["a"] = record(p.of("a"), True, None, RETRIEVAL, at=10.0)
    assert progress_to_dict(progress_from_dict(progress_to_dict(p)))["sections"]["a"][
        "attempts"
    ] == 1
