"""데모용 상태 만들기 — **네 출처를 실제 API로 채운다.**

분석 화면이 "진단·인출·복습·형성이 하나로 모인다"를 보여주는데, 갓 띄운 서버는
인출 몇 건뿐이라 막대 하나만 선다. 그러면 심사에서 *못 만든 기능*으로 읽힌다.

## 왜 HTTP로 하나

`store`가 인메모리라 **별도 프로세스에서 만지면 서버가 그걸 못 본다.** DB를 직접
쓰는 방법도 있지만, 그러면 "그렇게 쌓인다"가 아니라 "그렇게 넣었다"가 된다.
실제 엔드포인트를 그대로 지나므로 여기서 만든 상태는 사용자가 손으로 만든
것과 구별되지 않는다.

## 쓰는 법

    docker compose exec backend uv run python scripts/demo_seed.py --list
    docker compose exec backend uv run python scripts/demo_seed.py --doc <id>
    docker compose exec backend uv run python scripts/demo_seed.py --doc <id> --sections 24 --wrong 0.3

앞 화면부터 순서대로 학습하고, 일부를 틀리고, 그중 일부를 복습으로 다시 맞히고,
잠금이 열리면 단원 평가까지 푼다. 화면 생성이 5~7초라 `--sections 20`이면
2분쯤 걸린다(prewarm이 병렬로 미리 만들어 두면 훨씬 짧다).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/curriculum"
# 로그인 없이 도는 dev 유저. core/deps.py의 DEV_USER_ID와 같아야 한다.
DEV_USER = "00000000-0000-0000-0000-000000000001"

# ⚠️ **누구로 기록하느냐가 결과를 가른다.** 진도는 사람별이고, 분석은 그
#    사람이 소유한 자료만 센다. 구글로 로그인해 만든 수업에 dev 유저로
#    시드하면 답은 들어가는데 **분석에는 하나도 안 잡힌다**(실측: 형성평가
#    4개까지 풀었는데 시도 0건). `--user`로 그 수업의 주인을 넘겨라.
_user = DEV_USER


def call(method: str, path: str, body: dict | None = None, timeout: int = 600):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("X-User-Id", _user)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read())


def q(doc_id: str) -> str:
    return urllib.parse.quote(doc_id, safe="")


def seed(
    doc_id: str,
    n_sections: int,
    wrong_rate: float,
    seed_n: int,
    from_chapter: int = 0,
) -> None:
    rng = random.Random(seed_n)
    t0 = time.time()

    doc = call("GET", f"/documents/{q(doc_id)}")
    print(f"자료  {doc['title']} · 목차 {len(doc['chapters'])} · 화면 {doc['sectionsTotal']}")

    # ── 미리 만들어 둔다. 없으면 화면마다 5~7초를 그대로 기다린다 ──────
    print(f"\n[0] prewarm {n_sections}개 …", flush=True)
    if from_chapter:
        # prewarm은 **앞 화면부터** 데운다. 뒤 목차를 시드할 때는 데울 자리가
        # 어긋나서 시간만 쓴다 — 그냥 화면마다 5~7초를 기다린다.
        print(f"    건너뜀 (목차 {from_chapter}부터라 데울 자리가 다르다)")
    else:
        try:
            w = call("POST", f"/documents/{q(doc_id)}/prewarm?limit={n_sections}", {})
            print(f"    {w}")
        except urllib.error.HTTPError as e:
            print(f"    건너뜀 ({e.code})")

    # ── 인출 — 앞 화면부터 순서대로 ─────────────────────────────────
    print(f"\n[1] 학습(인출) — 앞 {n_sections}개 화면", flush=True)
    learned: list[tuple[str, str, list[str]]] = []  # (chapter_idx, section_id, 틀린 개념)
    done = 0
    for ch in doc["chapters"]:
        if done >= n_sections:
            break
        if ch["index"] < from_chapter:
            continue
        chapter = call("GET", f"/documents/{q(doc_id)}/chapters/{ch['index']}")
        for sec in chapter["sections"]:
            if done >= n_sections:
                break
            lesson = call("GET", f"/documents/{q(doc_id)}/sections/{sec['sectionId']}")
            asked = [b for b in lesson["blocks"] if b["type"] in ("cloze", "mcq")]
            missed: list[str] = []
            for b in asked:
                keys = b.get("conceptKeys") or []
                key = keys[0] if len(keys) == 1 else None
                ok = rng.random() >= wrong_rate
                call(
                    "POST",
                    f"/documents/{q(doc_id)}/sections/{sec['sectionId']}/answer",
                    {"correct": ok, "conceptKey": key, "kind": "retrieval"},
                )
                if not ok and key:
                    missed.append(key)
            # 틀린 개념은 **그 자리에서 한 번 더** 틀린 것으로 남긴다.
            #
            # 약점(`weak_concepts`)은 같은 개념 2회 이상 오답이라야 잡힌다
            # (`WEAK_THRESHOLD`). 그런데 화면마다 개념이 다르니 한 바퀴 돌면
            # 개념당 1회뿐이라, 오답률을 아무리 올려도 **약점이 0개로 남는다**
            # (실측: wrong 0.45로 68건을 풀었는데 약점 0). 그러면 분석 화면의
            # "자주 걸리는 개념"이 통째로 빈다.
            #
            # 실제 학습자도 틀린 문항을 다시 풀다 또 틀린다 — 지어낸 상태가
            # 아니라 흔한 상태다.
            for key in missed:
                call(
                    "POST",
                    f"/documents/{q(doc_id)}/sections/{sec['sectionId']}/answer",
                    {"correct": False, "conceptKey": key, "kind": "retrieval"},
                )
            learned.append((ch["index"], sec["sectionId"], missed))
            done += 1
            print(f"    {done:2}/{n_sections}  {sec['title'][:26]:28} 문항 {len(asked)} · 틀림 {len(missed)}", flush=True)

    # ── 복습 — 틀린 화면 몇 개를 시간이 지난 뒤 다시 맞힌 것으로 ──────
    wrong_secs = [x for x in learned if x[2]]
    picks = wrong_secs[: max(1, len(wrong_secs) // 2)]
    print(f"\n[2] 복습 — 틀렸던 화면 {len(picks)}개를 다시 맞힘", flush=True)
    for _ch, sid, missed in picks:
        for key in missed[:2]:
            call(
                "POST",
                f"/documents/{q(doc_id)}/sections/{sid}/answer",
                {"correct": True, "conceptKey": key, "kind": "review"},
            )
    print(f"    복습 시도 {sum(len(m[:2]) for _c, _s, m in picks)}건")

    # ── 형성평가 — 진도 60%를 넘긴 목차만 열린다 ────────────────────
    print("\n[3] 단원 평가", flush=True)
    opened = 0
    for ch in doc["chapters"]:
        try:
            f = call("GET", f"/documents/{q(doc_id)}/chapters/{ch['index']}/formative")
        except urllib.error.HTTPError as e:
            print(f"    [{ch['index']}] 실패 {e.code}")
            continue
        if f.get("locked"):
            print(f"    [{ch['index']}] 잠김 — {f.get('reason', '')[:52]}")
            continue
        opened += 1
        for b in f.get("blocks", []):
            if b["type"] not in ("cloze", "mcq"):
                continue
            keys = b.get("conceptKeys") or []
            sid = (b.get("content") or {}).get("sectionId")
            if not sid:
                continue
            call(
                "POST",
                f"/documents/{q(doc_id)}/sections/{sid}/answer",
                {
                    "correct": rng.random() >= wrong_rate,
                    "conceptKey": keys[0] if len(keys) == 1 else None,
                    "kind": "formative",
                },
            )
        print(f"    [{ch['index']}] 열림 — 문항 {len(f.get('blocks', []))}개 풀이")
    if opened == 0:
        print("    ⚠️ 열린 목차가 없다. --sections 를 늘려라 (진도 60%가 잠금 기준).")

    # ── 결과 ────────────────────────────────────────────────────────
    a = call("GET", "/analysis")
    print(f"\n{'=' * 62}")
    print(f"준비도 {a['readiness']:.1%} · 이해도 {a['understanding']:.1%}")
    print(f"진도 {a['sectionsDone']}/{a['sectionsTotal']} · 복습 대상 {a['sectionsDue']}")
    print(f"시도 {a['attemptsTotal']}건 · 출처 {a['byKind']}")
    if a["weakConcepts"]:
        print(f"약점 {', '.join(n for n, _ in a['weakConcepts'][:6])}")
    # 진단은 빼고 센다. `by_kind["diagnostic"]`은 **구조적으로 늘 0이다** —
    # 진단(24)은 문항을 풀려 점수를 쌓는 게 아니라 "안다/모른다"를 남기고 그
    # 결과로 목차를 바꾼다. 여기서 빈 구멍으로 세면 시드가 실패한 것처럼 읽힌다.
    missing = [k for k in ("retrieval", "review", "formative") if not a["byKind"].get(k)]
    if missing:
        print(f"⚠️ 아직 빈 출처: {', '.join(missing)}")
    print(f"진단이 끼운 보강 단원 {a.get('insertedChapters', 0)}개 (진단은 점수가 아니라 목차로 남는다)")
    print(f"{time.time() - t0:.0f}초")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", help="자료 또는 코스 id")
    ap.add_argument("--list", action="store_true", help="책장 목록만 보고 끝낸다")
    ap.add_argument("--sections", type=int, default=20, help="학습할 화면 수 (기본 20)")
    ap.add_argument("--wrong", type=float, default=0.25, help="오답 비율 (기본 0.25)")
    ap.add_argument("--seed", type=int, default=7, help="난수 시드 — 같은 값이면 같은 결과")
    # 앞 목차를 **일부러 안 건드리기 위한** 것이다. 진단이 정한 분량(compressed·
    # deep)은 아직 안 배운 목차에만 걸리는데, 시드가 앞부터 채우면 첫 목차가
    # 측정 기반으로 넘어가 A/B 차이가 첫 화면에서 안 보인다(실측: 목차 0만 normal).
    ap.add_argument("--from-chapter", type=int, default=0, help="이 목차부터 학습 (기본 0)")
    ap.add_argument(
        "--user",
        default=DEV_USER,
        help="누구로 기록할지. **그 수업의 주인이어야 한다** — 아니면 분석에 안 잡힌다",
    )
    args = ap.parse_args()

    global _user
    _user = args.user

    if args.list or not args.doc:
        for d in call("GET", "/documents"):
            print(" ", d)
        if not args.doc:
            print("\n--doc <id> 로 지정해라.")
        return 0

    seed(args.doc, args.sections, args.wrong, args.seed, args.from_chapter)
    return 0


if __name__ == "__main__":
    sys.exit(main())
