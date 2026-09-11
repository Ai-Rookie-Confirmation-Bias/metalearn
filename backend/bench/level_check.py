"""인출 문항 수준 분포 — 정의 되읽기가 얼마나 되나.

모델이 붙인 `kind`는 자기 신고라 못 믿는다. 여기서 기계로 판정해 견준다.
`COPY_RATIO` 문턱도 여기 분포를 보고 정한다.

사용: python3 bench/level_check.py [목차번호] [절_개수] [refresh]
"""
import json
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.features.curriculum.retrieval_level import (  # noqa: E402
    assess_cloze,
    assess_mcq,
    overlap,
)
from app.features.curriculum.store import build_document  # noqa: E402

BASE = "http://localhost:8000/api/curriculum"
DOC_ID = "파싱결과_실기요약노트"
DOC = urllib.parse.quote(DOC_ID)
CHAPTER = int(sys.argv[1]) if len(sys.argv) > 1 else 0
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
REFRESH = "?refresh=true" if len(sys.argv) > 3 else ""


def get(path, timeout=300):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


doc = build_document(_ROOT / "tests/fixtures" / f"{DOC_ID}.md")
defs = {c.key: c.definition for ch in doc.chapters for s in ch.sections for c in s.concepts}

ch = get(f"/documents/{DOC}/chapters/{CHAPTER}")
levels: Counter = Counter()
kind_vs_level: Counter = Counter()
ratios: list[float] = []
worst: list[tuple] = []

for sec in ch["sections"][:N]:
    L = get(f"/documents/{DOC}/sections/{sec['sectionId']}{REFRESH}")
    for b in L["blocks"]:
        c = b["content"]
        if b["type"] == "cloze":
            key = b["conceptKeys"][0] if b["conceptKeys"] else ""
            d = defs.get(key, "")
            lv = assess_cloze(c["sentence"], d, L["source"])
            stem = c["sentence"].replace("____", " ")
            r = overlap(d, stem) if d else 0.0
            ratios.append(r)
            if r >= 0.6 and len(worst) < 6:
                worst.append((r, key, c["sentence"]))
            levels[f"L{lv}"] += 1
            kind_vs_level[f"{c.get('kind', '?')}→L{lv}"] += 1
        elif b["type"] == "mcq":
            lv = assess_mcq(c["options"], L["concepts"])
            levels[f"L{lv}"] += 1
            kind_vs_level[f"mcq→L{lv}"] += 1

total = sum(levels.values())
print(f"목차 {CHAPTER} · 절 {N}개 · 문항 {total}개")
for k in ("L1", "L2", "L3"):
    v = levels[k]
    tag = {"L1": "재인(정의 되읽기)", "L2": "적용", "L3": "구별"}[k]
    print(f"   {k} {tag:<18} {v:>3}개  {v/max(total,1):.0%}")
print(f"\n   모델 라벨 vs 판정: {dict(kind_vs_level)}")
if ratios:
    ratios.sort()
    print(f"   정의문 겹침  중앙값 {ratios[len(ratios)//2]:.2f} · 최대 {ratios[-1]:.2f}")
if worst:
    print("\n[정의문을 그대로 옮긴 문항]")
    for r, key, s in worst:
        print(f"   {r:.2f} [{key}] {s[:64]}")
