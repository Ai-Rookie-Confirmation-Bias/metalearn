"""설명이 **원문 내용**을 얼마나 담았는지 잰다.

`coverage()`는 개념 **이름**이 설명에 나오는지만 본다. 이름만 나오고 내용이
빠지면 그건 목록이지 설명이 아니다. "교재와 비교해 생략되는 부분이 많지 않게"가
서비스 원칙인데 그걸 재는 자가 없었다.

원문을 항목 단위(표 행 · 불릿 · 문장)로 쪼개고, 각 항목의 내용이 설명에
반영됐는지 본다. 항목이 통째로 빠졌으면 그 대목을 못 배운 것이다.

사용: python3 bench/explain_coverage.py [목차번호] [절_개수] [refresh]
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path("/app") if Path("/app/app").exists() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.features.curriculum.retrieval_level import overlap  # noqa: E402

BASE = "http://localhost:8000/api/curriculum"
DOC = urllib.parse.quote("파싱결과_실기요약노트")
CHAPTER = int(sys.argv[1]) if len(sys.argv) > 1 else 0
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
REFRESH = "?refresh=true" if len(sys.argv) > 3 else ""

# 이 비율 이상 겹치면 그 항목이 설명에 반영된 것으로 본다.
HIT = 0.35
# 너무 짧은 줄은 제목·잡음이라 내용으로 안 센다.
MIN_LEN = 14


def get(path, timeout=400):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read())


def items(source: str) -> list[str]:
    """원문을 내용 항목으로 쪼갠다. 표 행은 셀을 합쳐 한 항목으로 본다."""
    out: list[str] = []
    for line in source.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "![")):
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|") if c.strip()]
            if len(cells) >= 2 and not all(set(c) <= set("-: ") for c in cells):
                out.append(" ".join(cells))
            continue
        s = re.sub(r"^[\s\-•*·>]+", "", s)
        if len(s) >= MIN_LEN:
            out.append(s)
    return out


total = hit = 0
worst: list[tuple] = []
per_section: list[tuple] = []

ch = get(f"/documents/{DOC}/chapters/{CHAPTER}")
for sec in ch["sections"][:N]:
    L = get(f"/documents/{DOC}/sections/{sec['sectionId']}{REFRESH}")
    explanation = next(
        (b["content"]["text"] for b in L["blocks"] if b["type"] == "concept"), ""
    )
    src_items = items(L["source"])
    if not src_items or not explanation:
        per_section.append((sec["title"], 0, 0, len(L["source"])))
        continue
    got = [it for it in src_items if overlap(it, explanation) >= HIT]
    total += len(src_items)
    hit += len(got)
    per_section.append((sec["title"], len(got), len(src_items), len(L["source"])))
    for it in src_items:
        if overlap(it, explanation) < HIT and len(worst) < 8:
            worst.append((sec["title"], it))

print(f"목차 {CHAPTER} · 절 {N}개")
print(f"{'절':<24}{'담긴 항목':>10}{'설명 길이 대비':>16}")
for title, g, t, srclen in per_section:
    ratio = f"{g}/{t}" if t else "원문/설명 없음"
    print(f"   {title[:22]:<24}{ratio:>10}   원문 {srclen}자")
print(f"\n   원문 항목 {total}개 중 설명에 담긴 것 {hit}개 = {hit/max(total,1):.0%}")
if worst:
    print("\n[설명에 안 들어간 원문 항목]")
    for t, it in worst:
        print(f"   [{t[:14]}] {it[:66]}")
