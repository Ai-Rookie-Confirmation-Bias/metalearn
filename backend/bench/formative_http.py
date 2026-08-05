"""형성평가 HTTP 한 바퀴 — 잠금 → 학습 → 열림 → 가로지름 확인."""
import json
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/curriculum"


def url(p):
    return BASE + urllib.parse.quote(p)


def get(p):
    with urllib.request.urlopen(url(p), timeout=300) as r:
        return json.load(r)


def post(p, body):
    req = urllib.request.Request(
        url(p), data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


doc_id = next(d for d in get("/documents") if "필기" in d)
ch = get(f"/documents/{doc_id}/chapters/0")
secs = ch["sections"]
print(f"목차 '{ch['title']}' · 화면 {len(secs)}개\n")

f = get(f"/documents/{doc_id}/chapters/0/formative")
print(f"[잠금 상태] locked={f['locked']} progress={f['progress']}")
print(f"           {f['reason']}\n")

# 60% 넘게 학습한 것으로 만든다. 일부는 틀려서 약점을 만든다
need = int(len(secs) * 0.6) + 1
for i, s in enumerate(secs[:need]):
    correct = i % 3 != 0  # 3개 중 1개는 틀린다
    post(
        f"/documents/{doc_id}/sections/{s['sectionId']}/answer",
        {"correct": correct, "conceptKey": s["concepts"][0], "kind": "retrieval"},
    )
    if not correct:  # 두 번 틀려야 약점으로 잡힌다
        post(
            f"/documents/{doc_id}/sections/{s['sectionId']}/answer",
            {"correct": False, "conceptKey": s["concepts"][0], "kind": "retrieval"},
        )
print(f"화면 {need}개 학습 기록 (일부 오답)\n")

ch = get(f"/documents/{doc_id}/chapters/0")
print(f"약점 개념: {ch['weakConcepts'][:5]}")

f = get(f"/documents/{doc_id}/chapters/0/formative")
print(f"\n[열림 상태] locked={f['locked']} progress={f['progress']} 생성={f['generated']}")
n = len(f["blocks"])
print(f"문항 {n}개 · 가로지름 {f['crossing']}/{n} · 확인하는 약점 {f['coveredWeak']}")

screen_of = {c: i for i, s in enumerate(secs) for c in s["concepts"]}
for b in f["blocks"]:
    opts = b["content"]["options"]
    sc = sorted({screen_of[o] for o in opts if o in screen_of})
    mark = "가로지름" if len(sc) >= 2 else "한 화면 "
    print(f"\n  [{mark}] 화면{sc}")
    print(f"   Q. {b['content']['question'][:70]}")
    print(f"   보기: {opts}")
    print(f"   답: {b['content']['answer']}")
