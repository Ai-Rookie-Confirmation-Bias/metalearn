"""절 묶기 결과를 눈으로 확인 — 숫자만 봐서는 이상한 묶음이 안 드러난다.

`grouping.py`를 고칠 때마다 여기부터 돌린다. LLM 호출 없이 즉시 실행된다.

사용: python3 bench/section_peek.py     (backend/ 에서)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.grouping import group_into_sections  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_grouping import SAMPLE  # noqa: E402

sections = group_into_sections(SAMPLE)

print(f"개념 {len(SAMPLE)}개 → 절 {len(sections)}개\n")
for s in sections:
    print(f"[{s.order}] {s.title}  ({s.size}개)")
    print(f"     ⚡ {s.reason}")
    for c in s.concepts:
        prereq = f"  ← {', '.join(c.prerequisites)}" if c.prerequisites else ""
        print(f"     · {c.key}{prereq}")
    print()

sizes = [s.size for s in sections]
print(f"절 크기: 최소 {min(sizes)} · 최대 {max(sizes)} · 평균 {sum(sizes)/len(sizes):.1f}")
