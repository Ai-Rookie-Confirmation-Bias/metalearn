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


def call(method: str, path: str, body: dict | None = None, timeout: int = 600):
    req = urllib.request.Request(f"{BASE}{path}", method=method)
    req.add_header("X-User-Id", DEV_USER)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data, timeout=timeout) as r:
        return json.loads(r.read())


def q(doc_id: str) -> str:
    return urllib.parse.quote(doc_id, safe="")


def seed(doc_id: str, n_sections: int, wrong_rate: float, seed_n: int) -> None:
    rng = random.Random(seed_n)
    t0 = time.time()

    doc = call("GET", f"/documents/{q(doc_id)}")
    print(f"자료  {doc['title']} · 목차 {len(doc['chapters'])} · 화면 {doc['sectionsTotal']}")

    # ── 미리 만들어 둔다. 없으면 화면마다 5~7초를 그대로 기다린다 ──────
    print(f"\n[0] prewarm {n_sections}개 …", flush=True)
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
    missing = [k for k in ("diagnostic", "retrieval", "review", "formative") if not a["byKind"].get(k)]
    if missing:
        print(f"⚠️ 아직 빈 출처: {', '.join(missing)}")
        if "diagnostic" in missing:
            print("   진단은 코스에서 /diagnostic/{courseId} 를 거쳐야 쌓인다.")
    print(f"{time.time() - t0:.0f}초")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", help="자료 또는 코스 id")
    ap.add_argument("--list", action="store_true", help="책장 목록만 보고 끝낸다")
    ap.add_argument("--sections", type=int, default=20, help="학습할 화면 수 (기본 20)")
    ap.add_argument("--wrong", type=float, default=0.25, help="오답 비율 (기본 0.25)")
    ap.add_argument("--seed", type=int, default=7, help="난수 시드 — 같은 값이면 같은 결과")
    args = ap.parse_args()

    if args.list or not args.doc:
        for d in call("GET", "/documents"):
            print(" ", d)
        if not args.doc:
            print("\n--doc <id> 로 지정해라.")
        return 0

    seed(args.doc, args.sections, args.wrong, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
