"""HTTP로 네 출처를 섞어 넣고 하나의 누적값이 나오는지 본다."""
import json
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/curriculum"


def get(p):
    with urllib.request.urlopen(BASE + urllib.parse.quote(p), timeout=60) as r:
        return json.load(r)


def post(p, body):
    req = urllib.request.Request(
        BASE + urllib.parse.quote(p),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


doc_id = next(d for d in get("/documents") if "필기" in d)
ch = get(f"/documents/{doc_id}/chapters/0")
secs = ch["sections"][:3]
print(f"목차 '{ch['title']}' · 절 {len(ch['sections'])}개, 앞 3개로 시험\n")

plan = [
    (secs[0], "diagnostic", False),  # 배우기 전 — 틀려도 당연
    (secs[0], "retrieval", True),
    (secs[0], "retrieval", True),
    (secs[1], "retrieval", True),
    (secs[1], "review", True),  # 시간 지나 다시 꺼냄
    (secs[2], "formative", False),  # 종합 평가에서 틀림
]
for s, kind, correct in plan:
    r = post(
        f"/documents/{doc_id}/sections/{s['sectionId']}/answer",
        {"correct": correct, "conceptKey": s["concepts"][0], "kind": kind},
    )
    mark = "○" if correct else "✗"
    print(
        f"  {kind:<11}{mark}  {s['title'][:14]:<16}"
        f"→ 절 {r['statusLabel']} · 회상 {r['recall']} · "
        f"준비도 {r['readiness']} / 이해도 {r['understanding']}"
    )

doc = get(f"/documents/{doc_id}")
print(f"\n누적 결과")
print(f"  준비도 {doc['readiness']}  (= 이해도 × 진도 × 회상)")
print(f"  이해도 {doc['understanding']}  (망각 뺀 값)")
print(f"  복습 대기 {doc['sectionsDue']}개")
print(f"  출처별 {doc['byKind']}")

ch = get(f"/documents/{doc_id}/chapters/0")
print(f"\n목차 회상 {ch['recall']} · 복습 대기 {ch['sectionsDue']}")
for s in ch["sections"][:3]:
    print(
        f"  {s['title'][:16]:<18} {s['statusLabel']:<6} "
        f"회상 {s['recall']} · 복습 {s['needsReview']} · {s['byKind']}"
    )

try:
    post(
        f"/documents/{doc_id}/sections/{secs[0]['sectionId']}/answer",
        {"correct": True, "kind": "made_up"},
    )
    print("\n알 수 없는 출처를 통과시킴 — 문제")
except urllib.error.HTTPError as e:
    print(f"\n알 수 없는 출처 거부: {e.code}")
