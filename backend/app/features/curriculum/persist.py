"""진도 스냅샷 — DB 전에 파일로 살린다.

인메모리만 두면 백엔드 재시작마다 준비도가 0이 된다. 데모 리허설·코드
고치는 도중에 실제로 겪었다. 테이블을 만들기 전에 **같은 모양을 JSON으로
읽고 쓴다.** DB가 붙으면 여기 입출력만 바꾸면 된다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .mastery import SectionMastery

if TYPE_CHECKING:
    from .store import Progress

# 사용자별 스냅샷 자리. 진도는 사람마다 다르므로 파일도 사람마다다.
PROGRESS_DIR = Path(
    os.getenv(
        "CURRICULUM_PROGRESS_DIR",
        Path(__file__).resolve().parents[3] / "data" / "progress",
    )
)

# 사용자 구분이 없던 시절의 단일 파일. 지금은 **읽기만** 한다 —
# 서버가 처음 뜰 때 dev 유저 몫으로 한 번 옮기고 끝이다.
LEGACY_PATH = Path(
    os.getenv(
        "CURRICULUM_PROGRESS",
        Path(__file__).resolve().parents[3] / "data" / "curriculum_progress.json",
    )
)


def user_path(user_id: str) -> Path:
    return PROGRESS_DIR / f"{user_id}.json"


def progress_to_dict(progress: Progress) -> dict:
    return {
        "recent_wrong": list(progress.recent_wrong),
        "sections": {
            sid: {
                "section_id": s.section_id,
                "attempts": s.attempts,
                "weight": s.weight,
                "score": s.score,
                "by_kind": dict(s.by_kind),
                "recent": list(s.recent),
                "wrong_by_concept": dict(s.wrong_by_concept),
                "last_success": s.last_success,
                "streak": s.streak,
            }
            for sid, s in progress.sections.items()
        },
    }


def progress_from_dict(data: dict) -> Progress:
    from .store import Progress

    sections: dict[str, SectionMastery] = {}
    for sid, raw in (data.get("sections") or {}).items():
        sections[sid] = SectionMastery(
            section_id=str(raw.get("section_id") or sid),
            attempts=int(raw.get("attempts") or 0),
            weight=float(raw.get("weight") or 0.0),
            score=float(raw.get("score") or 0.0),
            by_kind={str(k): int(v) for k, v in (raw.get("by_kind") or {}).items()},
            recent=[bool(x) for x in (raw.get("recent") or [])],
            wrong_by_concept={
                str(k): int(v) for k, v in (raw.get("wrong_by_concept") or {}).items()
            },
            last_success=(
                float(raw["last_success"])
                if raw.get("last_success") is not None
                else None
            ),
            streak=int(raw.get("streak") or 0),
        )
    return Progress(
        sections=sections,
        recent_wrong=[str(x) for x in (data.get("recent_wrong") or [])],
    )


def load_progress(path: Path) -> Progress:
    """파일이 없거나 깨져 있으면 빈 진도 — 서버는 계속 떠야 한다."""
    from .store import Progress

    if not path.is_file():
        return Progress()
    try:
        return progress_from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"[curriculum] 진도 로드 실패(빈 진도로 시작): {type(e).__name__}: {e}")
        return Progress()


def save_progress(progress: Progress, path: Path) -> None:
    """원자적으로 쓴다 — 중간에 죽어도 반쪽 파일이 안 남게."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(progress_to_dict(progress), ensure_ascii=False, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def migrate_legacy(user_id: str) -> int:
    """예전 단일 스냅샷을 그 사용자 몫으로 한 번 옮긴다. 옮긴 화면 수를 돌려준다.

    안 옮기면 로그인을 붙이는 순간 지금까지 쌓인 진도가 통째로 사라져 보인다.
    이미 그 사용자 파일이 있으면 손대지 않는다 — 두 번 돌아도 안전해야 한다.
    """
    target = user_path(user_id)
    if target.is_file() or not LEGACY_PATH.is_file():
        return 0
    progress = load_progress(LEGACY_PATH)
    save_progress(progress, target)
    # 원본은 남긴다. 되돌릴 일이 생기면 이 파일이 유일한 근거다.
    LEGACY_PATH.replace(LEGACY_PATH.with_suffix(".json.migrated"))
    return len(progress.sections)
