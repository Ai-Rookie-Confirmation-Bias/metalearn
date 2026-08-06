"""라벨 검증 이후 실측 — 무엇이 남고 무엇이 잘렸는가.

`gap_measure.py`와 같은 표본(같은 step)이라 81%/98% 기록과 직접 견줄 수 있다.
다른 점 두 가지.
  · `foreign_keys`를 넘긴다 — 라우터가 실제로 주는 값(문서 개념 − 이 화면 개념).
    안 넘기면 "다른 화면 개념이 정답" 규칙이 아예 안 돌아 실측이 아니다.
  · 빈칸을 **이름 인출 / 성질**로 갈라 센다. 커버리지가 이름 인출만 세도록
    바뀌었으니 총 문항 수만 보면 무엇을 잃었는지 안 보인다.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.features.curriculum.blocks import ConceptBrief  # noqa: E402
from app.features.curriculum.agents import explanation as exp_agent  # noqa: E402
from app.features.curriculum.agents import retrieval as ret_agent  # noqa: E402
from app.features.curriculum.retrieval_label import is_name_recall  # noqa: E402
from app.features.curriculum.retrieval_level import L1_RECALL  # noqa: E402
from app.features.curriculum.store import build_document  # noqa: E402

MD = Path("/app/tests/fixtures/파싱결과_필기핵심요약.md")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 14


async def main():
    doc = build_document(MD)
    sections = [s for ch in doc.chapters for s in ch.sections]
    all_keys = [k for ch in doc.chapters for s in ch.sections for k in s.concept_keys]
    step = max(1, len(sections) // N)
    picked = sections[::step][:N]

    covered = concepts_total = 0
    name_total = prop_total = mcq_total = l1_total = 0
    full = 0
    print(f"{'화면':<24}{'개념':>4}{'이름':>5}{'성질':>5}{'객관식':>6}{'L1':>4}{'표시':>5}  누락")
    for s in picked:
        briefs = [ConceptBrief(c.key, c.definition) for c in s.concepts]
        exp = await exp_agent.generate(s.title, briefs, "", s.source)
        if not exp.ok:
            print(f"{s.title[:22]:<24}   설명 실패")
            continue
        foreign = tuple(k for k in all_keys if k not in s.concept_keys)
        r = await ret_agent.generate(
            s.title, briefs, exp.text, s.source, foreign_keys=foreign
        )
        n = len(s.concepts)
        name = sum(1 for b in r.blocks if b.type == "cloze" and is_name_recall(b, briefs))
        prop = sum(1 for b in r.blocks if b.type == "cloze") - name
        mcq = sum(1 for b in r.blocks if b.type == "mcq")
        concepts_total += n
        covered += n - len(r.gap)
        name_total += name
        prop_total += prop
        mcq_total += mcq
        l1_total += round(r.l1_ratio * (name + prop + mcq))
        full += not r.gap
        mark = ("재" if r.retried else "") + (f"보{len(r.filled)}" if r.filled else "")
        print(
            f"{s.title[:22]:<24}{n:>4}{name:>5}{prop:>5}{mcq:>6}"
            f"{round(r.l1_ratio*100):>3}%{mark:>5}  {list(r.gap)}"
        )

    k = len(picked)
    total_q = name_total + prop_total + mcq_total
    print(f"\n화면 {k}개 · 개념 {concepts_total}개 · 문항 {total_q}개")
    print(f"  이름 인출된 개념  {covered}/{concepts_total} = {covered/max(concepts_total,1):.0%}")
    print(f"  빠짐 없는 화면    {full}/{k} = {full/max(k,1):.0%}")
    print(f"  빈칸 이름 {name_total} · 성질 {prop_total}(숙련도 미귀속) · 객관식 {mcq_total}")
    print(f"  L1 문항 추정      {l1_total}/{total_q} = {l1_total/max(total_q,1):.0%}  (L1={L1_RECALL})")


asyncio.run(main())
