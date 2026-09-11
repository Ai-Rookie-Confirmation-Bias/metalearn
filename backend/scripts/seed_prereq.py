"""시연용 — 12.5 분야 판정을 손으로 심는다.

12.5는 LLM 2회 호출의 합집합이라 **실행마다 다르게 나온다.** 실측:

    같은 라이언 PDF 두 벌   '정보 기술 및 컴퓨터 과학 교육' / '정보처리기사 실기'
    필기                   한 번은 영어 한 번은 한글로 와서 10과목
                           (`Database Fundamentals` + `데이터베이스 기초`)

촬영 중에 화면 ②에 `Programming Foundations`가 뜨면 다시 못 찍는다. 그래서
시연 자료만 판정을 고정한다. **문서 소유라 한 번 심으면 그 파일에 붙는다.**

    docker compose exec backend uv run python -m scripts.seed_prereq --list
    docker compose exec backend uv run python -m scripts.seed_prereq --doc 딥러닝 --dry-run
    docker compose exec backend uv run python -m scripts.seed_prereq --doc 딥러닝

⚠️ **파싱이 끝난 뒤에 돌려라.** 먼저 심으면 12.5가 덮어쓴다.
⚠️ 재사용(REUSE_PARSED_DOCUMENTS)이 꺼져 있으면 다시 올릴 때마다 새 문서가
   생겨 심은 값이 안 쓰인다. 시연 전에 docker-compose.yml에서 그 줄을 지운다.

읽는 쪽이 쓰는 건 네 칸뿐이다 (course/prereq.py:91) —
`prereq_subjects[].{name, why, ordered, subtopics}`. `runs`는 원본 기록용이라
안 넣는다.
"""
from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.core.database import SessionLocal
from app.features.course.models import Course, CourseDocument
from app.features.parsing.models import DocStatus, Document

# ── 시연 자료의 선수 판정 ────────────────────────────────────────
#
# 딥러닝을 고른 이유: **딥러닝 자료는 절대 선형대수를 안 가르친다.**
# 기각 검사(0.75/0.50)는 "이 자료가 이미 가르치나"를 보고 지우는데, 여기는
# 지울 근거가 자료 안에 없다. 반대로 "○○ 입문/기초"류는 밑바닥부터 가르쳐서
# 선수가 전부 기각되고 진단이 "먼저 필요한 게 없습니다"로 뜬다.
#
# 과목이 넷인 이유: 진단 ④가 스크롤 없이 한 화면에 들어간다. 실측 7과목
# 54항목이 11문항·2라운드·13~17초였으니 여기는 그 절반이다.
#
# ★ 넷을 다 심되 **보강이 몇 개 생길지는 화면에서 정한다.** "모른다"고 한
#   과목만 목차 앞에 들어간다. 시연 대본은 README가 아니라 docs/DEMO.md에.
DEEP_LEARNING = {
    "field": "딥러닝 입문",
    "level": "입문",
    "prereq_subjects": [
        {
            "name": "선형대수 기초",
            "ordered": True,
            "why": "신경망의 층 하나가 행렬 곱이다. 벡터·행렬을 못 읽으면 수식이 전부 막힌다",
            "subtopics": [
                "벡터와 내적",
                "행렬 곱셈",
                "전치와 차원 맞추기",
                "선형변환",
            ],
        },
        {
            "name": "미분과 연쇄법칙",
            "ordered": True,
            "why": "역전파가 연쇄법칙 그 자체다. 편미분을 모르면 학습이 왜 되는지 못 본다",
            "subtopics": [
                "도함수의 의미",
                "편미분",
                "연쇄법칙",
                "그래디언트",
                "극값과 최적화",
            ],
        },
        {
            "name": "확률과 통계 기초",
            "ordered": False,
            "why": "손실 함수와 소프트맥스가 확률분포 위에서 정의된다",
            "subtopics": [
                "확률분포",
                "기댓값과 분산",
                "조건부확률",
                "정규분포",
                "최대우도추정",
            ],
        },
        # ⚠️ 하위 항목을 **책장에 있는 자료에 맞춰 골랐다.** 대체 자료 조회는
        #    항목 이름과 개념 이름을 임베딩으로 재는데, 아무리 옳은 항목이라도
        #    책에 그 말이 없으면 안 걸린다. 실측(`Do it! 점프 투 파이썬` 발췌):
        #
        #        부동소수점 오차   → 부동 소수점 한계  0.728  ✓
        #        난수 생성과 시드  → 난수 생성        0.682  ✓
        #        평균과 중앙값     → 중앙값           0.657  ✓
        #        배열 인덱싱·슬라이싱 → (없음)         0.435  ✗
        #
        #    `브로드캐스팅`은 일부러 뺐다 — 정처기 교재의 네트워크
        #    `브로드캐스트`에 0.686으로 **잘못 걸린다.** 과목 대표 근거는
        #    항목 중 최고점이 가져가므로, 두면 엉뚱한 책이 대표로 뜬다.
        {
            "name": "파이썬 수치 계산 기초",
            "ordered": False,
            "why": "학습이 되는지 안 되는지는 숫자로만 보인다. 재현·수치 안정성이 여기서 갈린다",
            "subtopics": [
                "난수 생성과 시드",
                "부동소수점 오차",
                "평균과 중앙값",
                "반복자와 누적 계산",
            ],
        },
    ],
}

SEEDS = {"deeplearning": DEEP_LEARNING}


def _pick(db, needle: str) -> Document | None:
    """id 앞자리든 파일명 일부든 받는다. 촬영 중에 UUID를 다 칠 수는 없다."""
    rows = list(
        db.scalars(
            select(Document).where(Document.source_format != "generated")
        )
    )
    hits = [d for d in rows if needle in str(d.id) or needle in d.filename]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        print(f"✗ '{needle}'에 맞는 문서가 없습니다. --list로 확인하세요.")
        return None
    print(f"✗ '{needle}'에 {len(hits)}개가 걸립니다. 더 좁혀 주세요:")
    for d in hits:
        print(f"    {d.id}  {d.filename}")
    return None


def _show(db) -> None:
    rows = db.scalars(
        select(Document)
        .where(Document.source_format != "generated")
        .order_by(Document.created_at)
    )
    for d in rows:
        subs = (d.prereq_probe or {}).get("prereq_subjects") or []
        print(f"{d.id}  {d.status:6}  {d.filename[:44]:46}  과목 {len(subs):2}  {d.field or '-'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="문서 목록만 본다")
    parser.add_argument("--doc", help="문서 id 앞자리 또는 파일명 일부")
    parser.add_argument("--seed", default="deeplearning", choices=sorted(SEEDS))
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않는다")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.list or not args.doc:
            _show(db)
            if not args.doc:
                print("\n--doc <id 앞자리 | 파일명 일부> 로 대상을 고르세요.")
            return

        document = _pick(db, args.doc)
        if document is None:
            return
        if document.status != DocStatus.READY.value:
            # 파싱 중에 심으면 12.5가 뒤늦게 덮어쓴다. 그게 촬영 직전에 터진다.
            print(f"✗ 아직 파싱 중입니다 (status={document.status}). 끝나고 다시 돌리세요.")
            return

        seed = SEEDS[args.seed]
        print(f"대상   {document.filename}  ({document.id})")
        print(f"이전   {document.field or '-'} · 과목 "
              f"{len((document.prereq_probe or {}).get('prereq_subjects') or [])}")
        print(f"이후   {seed['field']} · 과목 {len(seed['prereq_subjects'])}")
        for s in seed["prereq_subjects"]:
            print(f"         · {s['name']} ({len(s['subtopics'])}항목)")

        if args.dry_run:
            print("\n(--dry-run — 저장하지 않았습니다)")
            print(json.dumps(seed, ensure_ascii=False, indent=2))
            return

        document.field = seed["field"]
        document.prereq_probe = seed
        db.commit()
        print("\n✓ 심었습니다.")

        # 이미 코스가 있으면 course_prereqs는 **그 코스가 만들어질 때 계산된
        # 값**이라 낡았다. 기각 검사를 다시 돌려야 심은 게 화면에 나온다.
        courses = list(
            db.scalars(
                select(Course)
                .join(CourseDocument, CourseDocument.course_id == Course.id)
                .where(CourseDocument.document_id == document.id)
            )
        )
        if courses:
            print("\n⚠️ 이 자료를 쓰는 수업이 이미 있습니다. 선수 판정을 다시 돌리세요:")
            for c in courses:
                print(f"    curl -s 'localhost:8000/api/courses/{c.id}/prereqs?refresh=true' >/dev/null")
            print("  또는 그 수업을 지우고 새로 만드는 쪽이 깨끗합니다.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
