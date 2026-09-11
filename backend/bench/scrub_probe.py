"""라벨 검증이 **무엇을 왜 버렸는지** — 실제 생성물로 센다.

`generate()` 안에서 스크럽이 끝나 버려서 결과만 보면 잘려 나간 문항이 안 보인다.
소스를 고치지 않고 `scrub_blocks`를 감싸 전/후를 기록한다.

특히 보려는 것: `foreign_keys` 규칙의 **오폭**. 상대가 문서 개념 371개인데
`_answer_concept`가 서로 포함이면 같다고 보므로, 성질 정답에 짧은 남의 개념명이
우연히 들어 있으면 멀쩡한 문항이 죽는다.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.features.curriculum import retrieval_label  # noqa: E402
from app.features.curriculum.agents import explanation as exp_agent  # noqa: E402
from app.features.curriculum.agents import retrieval as ret_agent  # noqa: E402
from app.features.curriculum.blocks import ConceptBrief, _answer_concept  # noqa: E402
from app.features.curriculum.store import build_document  # noqa: E402

MD = Path("/app/tests/fixtures/파싱결과_필기핵심요약.md")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 14

real = retrieval_label.scrub_blocks
log: list[tuple[str, str, str, str]] = []  # (사유, kind, answer, 붙은 것)


def spy(blocks, concepts, *, foreign_keys=()):
    kept = real(blocks, concepts, foreign_keys=foreign_keys)
    kept_ids = {id(b) for b in kept}
    # 살아남은 것 중 원본과 다른 객체(키가 바뀐 것)는 문장으로 되짚는다
    kept_sent = {b.content.get("sentence") for b in kept if b.type == "cloze"}
    for b in blocks:
        if b.type != "cloze" or id(b) in kept_ids:
            continue
        if b.content.get("sentence") in kept_sent:
            continue
        answer = str(b.content.get("answer") or "")
        kind = str(b.content.get("kind") or "")
        labeled = b.concept_keys[0] if len(b.concept_keys) == 1 else None
        pointed = _answer_concept(answer, concepts)
        if pointed is not None and labeled is not None and pointed != labeled:
            log.append(("같은 화면 다른 개념", kind, answer, f"{labeled}→{pointed}"))
        elif pointed is None and foreign_keys:
            out = _answer_concept(answer, [ConceptBrief(k, "") for k in set(foreign_keys)])
            if out is not None:
                log.append(("남의 화면 개념", kind, answer, f"{labeled} / 걸린말={out}"))
                continue
            log.append(("정의·상황 위장", kind, answer, str(labeled)))
        else:
            log.append(("정의·상황 위장", kind, answer, str(labeled)))
    return kept


retrieval_label.scrub_blocks = spy
ret_agent.scrub_blocks = spy


async def main():
    doc = build_document(MD)
    sections = [s for ch in doc.chapters for s in ch.sections]
    all_keys = [k for ch in doc.chapters for s in ch.sections for k in s.concept_keys]
    step = max(1, len(sections) // N)
    for s in sections[::step][:N]:
        briefs = [ConceptBrief(c.key, c.definition) for c in s.concepts]
        exp = await exp_agent.generate(s.title, briefs, "", s.source)
        if not exp.ok:
            continue
        foreign = tuple(k for k in all_keys if k not in s.concept_keys)
        await ret_agent.generate(s.title, briefs, exp.text, s.source, foreign_keys=foreign)

    print(f"폐기된 빈칸 {len(log)}개")
    for reason in ("남의 화면 개념", "같은 화면 다른 개념", "정의·상황 위장"):
        rows = [r for r in log if r[0] == reason]
        print(f"\n[{reason}] {len(rows)}개")
        for _, kind, answer, note in rows[:12]:
            print(f"  kind={kind:<4} answer='{answer}'  ({note})")


asyncio.run(main())
