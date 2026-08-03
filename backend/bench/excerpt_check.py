"""원문 자르기가 실제 자료에서 얼마나 되는지 — 이게 낮으면 생성 단위가 무너진다.

절 하나에 800~1,200자를 주려면 개념별로 원문을 잘라야 한다. 항목 번호로 찾는
폴백이 실제 자료에서 몇 %나 맞는지 재고, 못 찾는 개념이 어떤 것들인지 본다.

사용: python3 bench/excerpt_check.py <파싱결과.md>
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from app.features.curriculum.excerpt import split_by_concepts  # noqa: E402
from app.features.curriculum.grouping import Concept, group_into_sections  # noqa: E402
from parsing_md import parse  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("사용: python3 bench/excerpt_check.py <파싱결과.md>")

doc = parse(sys.argv[1])
print(f"📄 {doc.title}  ·  조각 {len(doc.chunks)} · 개념 {len(doc.concepts)}\n")

total, matched = 0, 0
sizes: list[int] = []
misses: list[str] = []
section_sizes: list[int] = []

for chunk in doc.chunks:
    keys = [c.key for c in chunk.concepts]
    ex = split_by_concepts(chunk.text, keys)
    total += len(ex)
    matched += sum(1 for e in ex if e.matched)
    sizes.extend(e.chars for e in ex if e.matched)
    misses.extend(e.key for e in ex if not e.matched)

    # 절 단위 원문 크기 — 실제 생성에 던질 분량
    by_key = {e.key: e for e in ex}
    concepts = [
        Concept(c.key, c.definition, c.prerequisites, c.order, str(chunk.index))
        for c in chunk.concepts
    ]
    for s in group_into_sections(concepts):
        picked = [by_key[c.key] for c in s.concepts if c.key in by_key]
        if picked and all(p.matched for p in picked):
            section_sizes.append(sum(p.chars for p in picked))

print("── 개념별 원문 자르기 ─────────────────────────────")
print(f"  제목으로 찾음   {matched}/{total}  ({matched/total:.0%})")
if sizes:
    sizes.sort()
    print(f"  구간 크기       최소 {sizes[0]} · 중앙 {sizes[len(sizes)//2]} · 최대 {sizes[-1]}자")

if section_sizes:
    section_sizes.sort()
    print("\n── 절 단위 원문 (생성에 던질 분량) ────────────────")
    print(
        f"  절 {len(section_sizes)}개 · 최소 {section_sizes[0]} · "
        f"중앙 {section_sizes[len(section_sizes)//2]} · 최대 {section_sizes[-1]}자"
    )
    good = sum(1 for s in section_sizes if 300 <= s <= 1500)
    print(f"  300~1,500자 구간  {good}/{len(section_sizes)}  ({good/len(section_sizes):.0%})")
    print("  → 벗어나면 요약되거나(너무 큼) 설명이 빈약해진다(너무 작음)")

if misses:
    print(f"\n── 못 찾은 개념 {len(misses)}개 (조각 전체로 폴백) ──")
    for k in misses[:15]:
        print(f"    · {k}")
    if len(misses) > 15:
        print(f"    … 외 {len(misses) - 15}개")
