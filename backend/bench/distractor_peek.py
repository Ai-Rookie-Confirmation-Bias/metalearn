"""오답 보기가 원문에서 왔는지 본다 — 소민섭 지적("오답을 막 만들면 답이 보인다") 검증.

현재 게이트는 **정답과 근거**가 원문에 있는지만 본다. 오답 보기는 order/multi에서만
`items_not_in_source`로 검사하고, **mcq 오답은 아무도 안 본다.** 그래서 모델이 오답을
원문 밖에서 지어내면, 학습자는 "원문에서 본 적 있는 보기"만 고르면 정답을 맞힌다.

사용: python3 bench/distractor_peek.py [per_level]   (backend/ 에서, 서버 필요)
"""
import ast
import json
import sys
import time
import urllib.request
from pathlib import Path

_BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(_BENCH.parent))

from app.features.problems.grounding import normalize  # noqa: E402

_tree = ast.parse((_BENCH / "volume_test.py").read_text(encoding="utf-8"))
SOURCE = next(
    n.value.value
    for n in _tree.body
    if isinstance(n, ast.Assign) and n.targets[0].id == "SOURCE"  # type: ignore[attr-defined]
)
_NORM_SOURCE = normalize(SOURCE)


def in_source(text: str) -> bool:
    return bool(text.strip()) and normalize(text) in _NORM_SOURCE


payload = {
    "subject": "정보처리기사",
    "per_level": int(sys.argv[1]) if len(sys.argv) > 1 else 3,
    "concepts": [
        {
            "concept_id": "s_os_mem",
            "chapter_id": "ch_3",
            "chapter_title": "운영체제",
            "title": "기억장치 관리",
            "order": 1,
            "keywords": ["반입 전략", "배치 전략", "교체 전략"],
            "source_page": 9,
            "source_text": SOURCE,
        }
    ],
}
req = urllib.request.Request(
    "http://localhost:48011/api/agents/problems/generate",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=1800) as r:
    resp = json.loads(r.read().decode("utf-8"))

problems = resp["results"][0]["problems"]
giveaway = 0
total_mcq = 0
with_notes = 0
note_slots = 0  # 오답 보기 총 개수(= distractor가 있어야 할 자리)
notes_given = 0
confused_ok = 0
for i, p in enumerate(problems):
    if p["type"] != "mcq":
        continue
    total_mcq += 1
    answer = p["answer"]
    wrong = [o for o in p["options"] if o != answer]
    notes = {d["text"]: d for d in p.get("distractors", [])}
    note_slots += len(wrong)
    notes_given += len(notes)
    with_notes += bool(notes)

    fake_wrong = sum(1 for o in wrong if not in_source(o))
    leaks = in_source(answer) and fake_wrong == len(wrong)
    giveaway += leaks

    print(f"\n[{i}] L{p['level']} {'🚨 정답이 보임' if leaks else ''}")
    print(f"    Q. {p['question']}")
    for o in p["options"]:
        mark = "O" if in_source(o) else "X"
        tag = "  ←정답" if o == answer else ""
        print(f"       {mark} {o}{tag}")
        if (d := notes.get(o)) is not None:
            hit = in_source(d["confused_with"])
            confused_ok += hit
            print(f"          ↳ {'O' if hit else 'X'} '{d['confused_with']}'와 혼동")
            print(f"            {d['note']}")

print(f"\n{'=' * 60}")
print(f"mcq {total_mcq}문항 · 오답 보기 {note_slots}개")
print(f"  정답만 원문에 있는 문항   {giveaway}/{total_mcq}   ← 낮을수록 좋다")
print(f"  오답 해설이 붙은 보기      {notes_given}/{note_slots}")
print(f"  혼동 대상이 원문에 실재    {confused_ok}/{notes_given or 1}")
print(f"소요 {time.time() - t0:.1f}초   (O=원문에 있음 / X=원문에 없음=창작)")
