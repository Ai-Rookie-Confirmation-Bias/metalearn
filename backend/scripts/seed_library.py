"""폴더 하나 → **기본 제공 자료**. 촬영하는 사람이 자기 강의자료로 실행한다.

책장이 비어 있으면 서비스가 서비스로 안 보인다. CS 기초 자료를 미리 깔아
두면 두 가지가 생긴다:

    책장   "기본 제공 자료" 칸이 찬다(내가 올린 것과 갈라 보인다)
    보강   진단이 "이 선수 개념은 이미 있는 자료에 있다"를 찾을 수 있다
           (`supply._existing_hits` — 그 조회는 **내 코스 밖 · 실제 교재 ·
           원문 조각 있음**만 보는데, DB에 남의 교재가 없으면 찾을 게 없다.
           주석에 적힌 "실측 히트율 28개 중 2개"가 그 상태에서 나온 값이다.)

## 왜 스크립트인가 — DB는 안 따라간다

코드와 문서는 git으로 가지만 **적재된 DB는 각자 로컬에 남는다.** 촬영하는
사람이 자기 자료로 직접 돌려야 같은 화면이 나온다. 그래서 파일이 아니라
절차를 넘긴다.

## 쓰는 법

    # 컨테이너 안에서 볼 수 있는 경로에 PDF를 모아 둔다
    docker compose cp ./내자료 backend:/app/seed_materials

    docker compose exec backend uv run python scripts/seed_library.py \\
        --dir /app/seed_materials

    # 이미 올라간 자료를 기본 제공으로 — **id를 직접 적는다**
    docker compose exec backend uv run python scripts/seed_library.py \\
        --mark 7151777a-fc0a-4e9b-a919-613808a634a4

    # 지금 뭐가 기본 제공인지만 보기
    docker compose exec backend uv run python scripts/seed_library.py --list

⚠️ 파싱은 자료당 수 분이다. 촬영 전날 걸어 둬라.

⚠️ `--mark`는 **소유 기록을 지운다.** 남이 올린 자료 id를 넣으면 그 사람
   책장에서 사라진다(되돌리려면 user_documents를 직접 복구해야 한다).
   `--list`로 먼저 확인해라.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

# ⚠️ **전 모델을 먼저 로드한다.** parsing 모델만 import하면
# `user_documents.user_id` → `users` FK를 풀 수 없어 첫 쿼리에서 죽는다
# (NoReferencedTableError). 앱은 main.py가 같은 줄로 해결하고 있다.
import app.models_registry  # noqa: F401,E402
from app.core.database import SessionLocal  # noqa: E402
from app.features.parsing.models import Document, UserDocument  # noqa: E402

# 파싱은 업로드 라우터가 백그라운드로 돌리는 것과 **같은 함수**를 쓴다
# (`ParsingService.run`). 여기서 따로 구현하면 화면으로 올린 자료와 이
# 스크립트로 올린 자료가 다른 결과를 갖게 된다.
from app.features.parsing.service import ParsingService  # noqa: E402

READY = "ready"
FAILED = "failed"
GENERATED = "generated"
SUFFIXES = {".pdf", ".pptx", ".docx"}


def _files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise SystemExit(f"폴더가 아니다: {root}")
    found = sorted(p for p in root.iterdir() if p.suffix.lower() in SUFFIXES)
    if not found:
        raise SystemExit(f"{root} 에 자료가 없다 (지원: {', '.join(sorted(SUFFIXES))})")
    return found


def mark_public(db, document_ids: list[uuid.UUID]) -> int:
    """`visibility='public'` 로 바꾸고 **소유 기록을 지운다.**

    소유가 남아 있으면 올린 사람 책장에서는 "내가 올린 자료" 칸에, 다른
    사람에게는 "기본 제공" 칸에 뜬다. 같은 책이 사람마다 다른 칸에 있으면
    촬영할 때 설명할 수 없다.

    26이 만든 보강 자료(`source_format='generated'`)는 건드리지 않는다 —
    그건 원문 없는 명세라 책장에서 골라 읽는 책이 아니다.

    ⚠️ **대상은 반드시 명시해야 한다.** 처음엔 인자가 없으면 전체를 바꾸게
       했는데, 그걸로 남이 방금 올려 진단까지 끝낸 자료를 공개로 돌리고
       소유 기록을 지웠다(복구는 됐지만 되돌릴 수 없는 삭제였다).
       "대상을 안 주면 전부"는 이런 함수에서 쓰면 안 되는 기본값이다.
    """
    if not document_ids:
        return 0
    rows = db.scalars(
        select(Document).where(
            Document.source_format != GENERATED,
            Document.id.in_(document_ids),
        )
    ).all()

    changed = 0
    for row in rows:
        if row.visibility == "public":
            continue
        row.visibility = "public"
        db.execute(
            UserDocument.__table__.delete().where(
                UserDocument.document_id == row.id
            )
        )
        changed += 1
    db.commit()
    return changed


async def ingest(db, paths: list[Path], owner: uuid.UUID) -> list[uuid.UUID]:
    """업로드 + 파싱. 이미 같은 지문이 있으면 파싱을 건너뛴다.

    ⚠️ **자료마다 `asyncio.run`을 부르면 안 된다.** `solar_client`는 모듈
       싱글턴이라 첫 루프에서 만든 연결을 들고 있는데, 그 루프가 닫히면
       두 번째 자료부터 `RuntimeError: Event loop is closed`로 죽는다
       (실측: 4개 중 2개만 들어갔다). 루프는 바깥에서 한 번만 연다.
    """
    service = ParsingService(db)
    done: list[uuid.UUID] = []

    for i, path in enumerate(paths, 1):
        data = path.read_bytes()
        document_id, needs_parse = service.register(
            file_bytes=data, filename=path.name, user_id=owner, role="skeleton"
        )
        db.commit()

        if not needs_parse:
            print(f"  [{i}/{len(paths)}] {path.name} — 이미 파싱됨, 건너뜀")
            done.append(document_id)
            continue

        t0 = time.time()
        print(f"  [{i}/{len(paths)}] {path.name} — 파싱 중…", flush=True)
        try:
            await ParsingService(db).run(document_id, data)
        except Exception as e:  # noqa: BLE001 — 한 자료가 죽어도 나머지는 간다
            print(f"      실패: {type(e).__name__}: {e}")
            continue

        row = db.get(Document, document_id)
        status = row.status if row else "?"
        print(f"      {status} · {time.time() - t0:.0f}초")
        if status == READY:
            done.append(document_id)

    return done


def report(db) -> None:
    rows = db.scalars(
        select(Document).where(
            Document.visibility == "public",
            Document.source_format != GENERATED,
        )
    ).all()
    print(f"\n{'=' * 58}\n기본 제공 자료 {len(rows)}권")
    for row in rows:
        mark = "" if row.status == READY else f"  ⚠️ {row.status}"
        print(f"  {row.filename[:44]:46}{mark}")
    if not rows:
        print("  (없다. --dir 로 자료를 넣어라)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="자료가 든 폴더 (컨테이너 안 경로)")
    ap.add_argument(
        "--mark",
        nargs="+",
        metavar="DOC_ID",
        help="이미 올라간 자료를 기본 제공으로 바꾼다. **id를 직접 적는다** — "
        "'전부'는 안 된다(남의 자료까지 공개로 돌린 사고가 있었다)",
    )
    ap.add_argument("--list", action="store_true", help="현재 기본 제공 목록만 본다")
    ap.add_argument(
        "--owner",
        default="00000000-0000-0000-0000-000000000001",
        help="업로드 주체(dev 유저). 적재 후 소유 기록은 지워진다",
    )
    args = ap.parse_args()

    if not (args.dir or args.mark or args.list):
        ap.error("--dir · --mark · --list 중 하나는 있어야 한다")

    db = SessionLocal()
    try:
        if args.list:
            report(db)
            return 0

        ids: list[uuid.UUID] = []
        if args.dir:
            import asyncio

            paths = _files(Path(args.dir))
            print(f"자료 {len(paths)}개 적재\n")
            # 루프는 여기서 한 번만 연다(`ingest` 주석 참고).
            ids = asyncio.run(ingest(db, paths, uuid.UUID(args.owner)))
        if args.mark:
            ids += [uuid.UUID(x) for x in args.mark]

        changed = mark_public(db, ids)
        print(f"\n기본 제공으로 표시: {changed}권")
        report(db)
        print("\n책장을 새로고침하면 '기본 제공 자료' 칸에 뜬다.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
