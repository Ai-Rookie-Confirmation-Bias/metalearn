"""실제 파싱 결과 전체로 절 묶기를 돌려본다.

손으로 옮긴 샘플 18개로는 규모에서 뭐가 깨지는지 알 수 없다. 개념 533·634개를
넣었을 때 절이 몇 개 나오는지, 이상하게 큰/작은 절이 있는지, 고아가 생기는지를
숫자로 본다.

사용: python3 bench/real_grouping.py <파싱결과.md> [--detail 조각번호]
"""
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from app.features.curriculum.grouping import (  # noqa: E402
    Concept,
    group_into_sections,
)
from app.features.curriculum.parsing_md import parse  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("사용: python3 bench/real_grouping.py <파싱결과.md> [--detail 조각번호]")

path = sys.argv[1]
detail = None
if "--detail" in sys.argv:
    detail = int(sys.argv[sys.argv.index("--detail") + 1])

doc = parse(path)
print(f"📄 {doc.title}")
print(f"   조각 {len(doc.chunks)}개 · 개념 {len(doc.concepts)}개 · "
      f"목차 {len(doc.by_chapter())}개\n")

total_sections = 0
sizes: list[int] = []
reasons: Counter[str] = Counter()
per_chapter: dict[str, tuple[int, int]] = {}

for chapter, chunks in doc.by_chapter().items():
    ch_concepts = 0
    ch_sections = 0
    for chunk in chunks:
        concepts = [
            Concept(
                key=c.key,
                definition=c.definition,
                prerequisites=c.prerequisites,
                order=c.order,
                chunk_id=str(chunk.index),
            )
            for c in chunk.concepts
        ]
        sections = group_into_sections(concepts)
        ch_concepts += len(concepts)
        ch_sections += len(sections)
        total_sections += len(sections)
        sizes.extend(s.size for s in sections)
        for s in sections:
            key = (
                "같은 부모" if "함께 알아야" in s.reason
                else "순환" if "서로가 서로" in s.reason
                else "원문 순서"
            )
            reasons[key] += 1

        # 누락·중복 검사 — 여기가 깨지면 개념을 영영 안 배우거나 두 번 배운다.
        got = [c.key for s in sections for c in s.concepts]
        assert len(got) == len(concepts), f"조각 #{chunk.index} 개념 수 불일치"
        assert len(set(got)) == len(got), f"조각 #{chunk.index} 중복"

        if detail is not None and chunk.index == detail:
            print(f"── 조각 #{chunk.index} 상세 ({len(concepts)}개 → {len(sections)}절)")
            for s in sections:
                print(f"  [{s.order}] {s.title}  ({s.size}개)")
                print(f"       ⚡ {s.reason}")
                for c in s.concepts:
                    pre = f"  ← {', '.join(c.prerequisites)}" if c.prerequisites else ""
                    print(f"       · {c.key}{pre}")
            print()

    per_chapter[chapter] = (ch_concepts, ch_sections)

print("── 목차별 ─────────────────────────────────────────────")
for chapter, (n_c, n_s) in per_chapter.items():
    avg = n_c / n_s if n_s else 0
    print(f"  {chapter[:34]:<36} 개념 {n_c:>4}  →  절 {n_s:>3}  (평균 {avg:.1f})")

print("\n── 전체 ───────────────────────────────────────────────")
print(f"  개념 {len(doc.concepts)} → 절 {total_sections}  (평균 {len(doc.concepts)/total_sections:.1f})")
print(f"  절 크기: 최소 {min(sizes)} · 최대 {max(sizes)} · 중앙 {sorted(sizes)[len(sizes)//2]}")

dist = Counter(sizes)
print("\n  크기 분포")
for size in sorted(dist):
    bar = "▇" * min(dist[size], 50)
    print(f"    {size:>2}개 짜리 절  {dist[size]:>3}  {bar}")

print("\n  묶인 이유")
for reason, n in reasons.most_common():
    print(f"    {reason:<12} {n:>3}절  ({n/total_sections:.0%})")

lonely = dist.get(1, 0)
print(f"\n  ⚠️ 혼자인 절 {lonely}개 ({lonely/total_sections:.0%}) — 많으면 진도가 잘게 끊긴다")
big = sum(n for s, n in dist.items() if s >= 8)
print(f"  ⚠️ 8개 이상인 절 {big}개 — 많으면 한 화면에 안 담긴다")
