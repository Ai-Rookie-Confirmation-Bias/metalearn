"""커리큘럼이 학습 결과에 따라 바뀌는 것을 보여준다 — 이 서비스의 핵심 장면.

심사위원이 기억할 장면은 문제를 푸는 순간이 아니라 **커리큘럼이 바뀌는 순간**이다.
LLM 없이 규칙만으로 도므로 즉시 실행된다.

사용: python3 bench/plan_demo.py [파싱결과.md]
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from app.features.curriculum.grouping import Concept, group_into_sections  # noqa: E402
from app.features.curriculum.mastery import (  # noqa: E402
    SectionMastery,
    chapter_summary,
    label,
    record,
)
from app.features.curriculum.planner import bar, plan_course  # noqa: E402
from parsing_md import parse  # noqa: E402

md = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/파싱결과_필기핵심요약.md"
doc = parse(md)

# 목차별 절 만들기
chapters: dict[str, list[str]] = {}
for chunk in doc.chunks:
    concepts = [
        Concept(c.key, c.definition, c.prerequisites, c.order, str(chunk.index))
        for c in chunk.concepts
    ]
    for s in group_into_sections(concepts):
        chapters.setdefault(chunk.chapter, []).append(f"{chunk.index}-{s.order}")

names = list(chapters)
states: dict[str, list[SectionMastery]] = {
    ch: [SectionMastery(sid) for sid in ids] for ch, ids in chapters.items()
}


def show(title: str, carry: dict[str, tuple[str, ...]] | None = None) -> None:
    summaries = [chapter_summary(ch, states[ch]) for ch in names]
    plans = plan_course(summaries, carry)
    print(f"\n{'=' * 66}\n{title}\n{'=' * 66}")
    for p, s in zip(plans, summaries):
        head = f"  {p.order + 1}. {p.chapter[:22]:<24}"
        if s.sections_touched:
            head += f"이해도 {s.ratio:>4.0%} {label(s.status):<6}"
        else:
            head += f"{'—':>10} {label(s.status):<6}"
        print(f"{head} {bar(p)}  절 {p.sections_planned}/{p.sections_total}")
        if p.reason:
            print(f"       ⚡ {p.reason}")


show("① 시작 — 아직 아무것도 안 풀었다")

# ② 1장을 잘 풀었다
for st in states[names[0]][:6]:
    for _ in range(4):
        st_new = record(st, True, None)
        states[names[0]][states[names[0]].index(st)] = st_new
        st = st_new

# ③ 3장을 자꾸 틀렸다 — 같은 개념을 반복해서
weak_ch = names[2]
for st in states[weak_ch][:5]:
    idx = states[weak_ch].index(st)
    cur = st
    for r in (False, False, True, False):
        cur = record(cur, r, "정규화")
    states[weak_ch][idx] = cur

show("② 1장을 잘 풀고, 3장을 자꾸 틀렸다")

# ④ 3장 형성평가에서 '정규화'가 약했다 → 다음 목차 설명에 녹인다
carry = {names[3]: ("정규화",)}
show("③ 3장 형성평가 후 — 약점을 다음 목차 설명에 녹인다", carry)

print(f"\n{'=' * 66}")
print("목차 순서는 한 번도 바뀌지 않았다. 바뀐 것은 분량과 설명이다.")
print("(실측: 선수관계의 96~99%가 같은 목차 안에서 일어난다)")
