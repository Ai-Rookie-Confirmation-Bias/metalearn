"""보충 화면이 실제로 끼워지는가 — API로 확인.

순수 로직 테스트는 규칙이 도는지만 잠근다. 진짜 문서의 선수 관계로도
걸리는지, 진도가 뒤로 안 가는지는 여기서만 나온다.
"""
import sys

sys.path.insert(0, "/app")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

# ⚠️ 픽스처는 startup 이벤트에서 읽는다. 컨텍스트로 열지 않으면 문서가 0개다.
_ctx = TestClient(app)
c = _ctx.__enter__()
DOC = "파싱결과_필기핵심요약"


def chapter(i: int) -> dict:
    return c.get(f"/api/curriculum/documents/{DOC}/chapters/{i}").json()


def show(tag: str, ch: dict) -> None:
    ins = [s for s in ch["sections"] if s.get("inserted")]
    print(
        f"{tag:<12} 화면 {len(ch['sections']):>3}개 (보충 {len(ins)}) · "
        f"진도 {ch['progress']:.0%} · 평가 {'열림' if ch['formativeReady'] else '잠김'}"
    )
    for s in ins:
        print(f"               ↻ {s['title']}  —  {s['reason']}")


ch0 = chapter(0)
show("처음", ch0)

# 이 목차 화면들의 선수 개념을 찾아, 그 선수를 담은 화면에서 반복해서 틀린다.
doc_sections = {s["sectionId"]: s for s in ch0["sections"]}
target = None
for s in ch0["sections"]:
    lesson = c.get(f"/api/curriculum/documents/{DOC}/sections/{s['sectionId']}")
    break

# 선수 관계는 도메인 객체에만 있으므로 직접 본다.
from app.features.curriculum.store import store  # noqa: E402

doc = store.documents[DOC]
pool = {c.key for ch in doc.chapters for s in ch.sections for c in s.concepts}
# ⚠️ 선수 이름이 **개념 목록에 없는** 경우가 많다(실측: 필기 339개 중 122개만
#    찾아진다). 못 찾는 선수는 보충 화면을 만들 재료가 없으니 걸러야 한다.
prereqs = [
    (sec, key)
    for ch in doc.chapters
    for sec in ch.sections
    for con in sec.concepts
    for key in con.prerequisites
    if key not in sec.concept_keys and key in pool
]
print(f"\n보충 재료가 있는 선수 관계 {len(prereqs)}개")
if not prereqs:
    print("이 문서에는 쓸 수 있는 선수 관계가 없다 — 보충이 안 생기는 게 맞다")
    raise SystemExit

sec, weak_key = prereqs[0]
owner = next(
    s.section_id for ch in doc.chapters for s in ch.sections if weak_key in s.concept_keys
)
print(f"'{weak_key}' 를 3번 틀린다 (담긴 화면 {owner}) → '{sec.title}' 앞에 보충이 떠야 한다")

for _ in range(3):
    c.post(
        f"/api/curriculum/documents/{DOC}/sections/{owner}/answer",
        json={"correct": False, "conceptKey": weak_key, "kind": "retrieval"},
    )

for i in range(len(doc.chapters)):
    after = chapter(i)
    if any(s.get("inserted") for s in after["sections"]) or i == 0:
        show(f"틀린 뒤 {i}단원", after)
