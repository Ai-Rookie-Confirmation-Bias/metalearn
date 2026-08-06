"""HTTP로 루프 한 바퀴 — 틀린다 → 다음 절을 연다 → 설명이 달라졌는가.

화면이 실제로 하는 것과 같은 순서로 부른다. 코드 단위로만 확인하면
라우터에서 안 넘기는 실수(방금 겪은 그것)를 못 잡는다.
"""
import json
import urllib.parse
import urllib.request

BASE = "http://localhost:8000/api/curriculum"


def url(path: str) -> str:
    return BASE + urllib.parse.quote(path)


def get(path):
    with urllib.request.urlopen(url(path), timeout=180) as r:
        return json.load(r)


def post(path, body):
    req = urllib.request.Request(
        url(path),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


docs = get("/documents")
doc_id = next(d for d in docs if "필기" in d)
doc = get(f"/documents/{doc_id}")
print(f"자료 '{doc['title']}' · 목차 {len(doc['chapters'])}")

# '디자인 패턴'이 있는 절과 '생성 패턴' 절을 찾는다
src_sec = dst_sec = None
for ch in doc["chapters"]:
    detail = get(f"/documents/{doc_id}/chapters/{ch['index']}")
    for s in detail["sections"]:
        if "디자인 패턴" in s["concepts"] and src_sec is None:
            src_sec = s
        if s["title"] == "생성 패턴" and dst_sec is None:
            dst_sec = s
    if src_sec and dst_sec:
        break
print(f"틀릴 절   {src_sec['title']}  ({src_sec['sectionId']})")
print(f"열어볼 절 {dst_sec['title']}  ({dst_sec['sectionId']})")

before = get(f"/documents/{doc_id}/sections/{dst_sec['sectionId']}")
print(f"\n[전] tiedIn={before['tiedIn']} · tie_in 블록="
      f"{any(b['type'] == 'tie_in' for b in before['blocks'])}")

r = post(f"/documents/{doc_id}/sections/{src_sec['sectionId']}/answer",
         {"correct": False, "conceptKey": "디자인 패턴"})
print(f"\n'디자인 패턴' 오답 기록 → 절 상태 {r['statusLabel']} · 준비도 {r['readiness']}")

after = get(f"/documents/{doc_id}/sections/{dst_sec['sectionId']}")
tie = next((b for b in after["blocks"] if b["type"] == "tie_in"), None)
print(f"\n[후] tiedIn={after['tiedIn']} · tie_in 블록={bool(tie)}")
if tie:
    print(f"     >>> {tie['content']['text'][:280]}")

b1 = next(b["content"]["text"] for b in before["blocks"] if b["type"] == "concept")
b2 = next(b["content"]["text"] for b in after["blocks"] if b["type"] == "concept")
print(f"\n본문도 다시 생성됐는가: {b1 != b2}")
