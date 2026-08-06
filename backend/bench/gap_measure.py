"""인출 커버리지 실측 — 절의 개념이 실제로 몇 개나 꺼내지는가.

고치기 전/후를 같은 절 집합으로 잰다. 절마다 LLM 2~3콜이라 표본은 적당히.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.features.curriculum.blocks import ConceptBrief  # noqa: E402
from app.features.curriculum.agents import explanation as exp_agent  # noqa: E402
from app.features.curriculum.agents import retrieval as ret_agent  # noqa: E402
from app.features.curriculum.store import build_document  # noqa: E402

MD = Path("/app/tests/fixtures/파싱결과_필기핵심요약.md")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 14


async def one(sec):
    briefs = [ConceptBrief(c.key, c.definition) for c in sec.concepts]
    exp = await exp_agent.generate(sec.title, briefs, "", sec.source)
    if not exp.ok:
        return None
    return await ret_agent.generate(sec.title, briefs, exp.text, sec.source)


async def main():
    doc = build_document(MD)
    sections = [s for ch in doc.chapters for s in ch.sections]
    # 개념 수가 고른 표본을 뽑는다 — 앞에서 N개만 쓰면 한 목차에 몰린다
    step = max(1, len(sections) // N)
    picked = sections[::step][:N]

    covered_total = concepts_total = 0
    cloze_total = mcq_total = 0
    full = mcqless = 0
    print(f"{'절':<24}{'개념':>4}{'빈칸':>5}{'객관식':>6}{'재시도':>6}  누락")
    for s in picked:
        r = await one(s)
        if r is None:
            print(f"{s.title[:22]:<24}   생성 실패")
            continue
        n = len(s.concepts)
        cl = sum(1 for b in r.blocks if b.type == "cloze")
        mc = sum(1 for b in r.blocks if b.type == "mcq")
        concepts_total += n
        covered_total += n - len(r.gap)
        cloze_total += cl
        mcq_total += mc
        full += not r.gap
        mcqless += mc == 0
        mark = ("재" if r.retried else "") + (f"보{len(r.filled)}" if r.filled else "")
        print(f"{s.title[:22]:<24}{n:>4}{cl:>5}{mc:>6}{mark:>6}  {list(r.gap)}")

    k = len(picked)
    print(f"\n절 {k}개 · 개념 {concepts_total}개")
    print(f"  인출된 개념      {covered_total}/{concepts_total} = {covered_total/max(concepts_total,1):.0%}")
    print(f"  빠짐 없는 절     {full}/{k} = {full/max(k,1):.0%}")
    print(f"  객관식 없는 절   {mcqless}/{k}")
    print(f"  빈칸 {cloze_total}개 (개념당 {cloze_total/max(concepts_total,1):.2f}) · 객관식 {mcq_total}개")


asyncio.run(main())
