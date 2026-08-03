"""실제 파싱 결과로 성향별 커리큘럼을 생성해 나란히 본다.

이게 이 담당의 최종 산출물 형태다 — 같은 절, 같은 원문에서 사람마다 다른
학습 콘텐츠가 나오는지를 눈으로 확인한다. 다르지 않으면 성향 축이 헛돈 것이다.

진단 평가는 아직 없으므로(파싱 팀 통합 후) 성향만 조합해 본다.

사용: python3 bench/curriculum_demo.py <파싱결과.md> [조각번호] [절번호]
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

from app.features.curriculum.blocks import (  # noqa: E402
    ConceptBrief,
    build_prompt,
    coverage,
    parse_response,
    retrieval_gap,
)
from app.features.curriculum.excerpt import section_source  # noqa: E402
from app.features.curriculum.grouping import Concept, group_into_sections  # noqa: E402
from app.features.curriculum.profile import (  # noqa: E402
    empty_profile,
    explain,
    observe,
    prompt_block,
)
from parsing_md import parse  # noqa: E402

KEY = ""
for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("UPSTAGE_API_KEY="):
        KEY = line.split("=", 1)[1].strip().strip("\"'")
if not KEY:
    sys.exit(".env에 UPSTAGE_API_KEY가 없다")

URL = "https://api.upstage.ai/v1/chat/completions"
MODEL = "solar-pro3"

md = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/파싱결과_필기핵심요약.md"
chunk_no = int(sys.argv[2]) if len(sys.argv) > 2 else 0
section_no = int(sys.argv[3]) if len(sys.argv) > 3 else 2


def call(prompt: str) -> tuple[str, float]:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = json.loads(r.read().decode())["choices"][0]["message"]["content"]
    return raw, time.time() - t0


def profile_for(rep: bool | None, dep: bool | None):
    p = empty_profile()
    for axis, toward in (("representation", rep), ("depth", dep)):
        if toward is None:
            continue
        for _ in range(2):
            p = observe(p, axis, toward)
    return p


# ── 절 하나 고르기 ────────────────────────────────────────────────
doc = parse(md)
chunk = next(c for c in doc.chunks if c.index == chunk_no)
concepts = [
    Concept(c.key, c.definition, c.prerequisites, c.order, str(chunk.index))
    for c in chunk.concepts
]
sections = group_into_sections(concepts)
section = sections[min(section_no, len(sections) - 1)]
briefs = [ConceptBrief(c.key, c.definition) for c in section.concepts]
src = section_source(
    chunk.text, [c.key for c in section.concepts], [c.key for c in chunk.concepts]
)

print(f"📄 {doc.title} · 조각 #{chunk.index} · {chunk.chapter}")
print(f"📚 절: {section.title}  ({section.size}개)")
print(f"   ⚡ {section.reason}")
for c in section.concepts:
    print(f"   · {c.key} — {c.definition[:44]}")
print(f"   원문 {len(src)}자 첨부\n")

CASES = [
    ("① 비유 · 왜까지", True, True),
    ("② 정의 · 결론만", False, False),
    ("③ 중립 (미측정)", None, None),
]

summary = []
for label, rep, dep in CASES:
    prof = profile_for(rep, dep)
    prompt = build_prompt(section.title, briefs, prompt_block(prof), src)
    try:
        raw, took = call(prompt)
    except Exception as e:  # noqa: BLE001
        print(f"{label} ❌ {type(e).__name__}: {e}")
        continue
    blocks = parse_response(raw, briefs)
    covered, missing = coverage(blocks, briefs)
    gap = retrieval_gap(blocks, briefs)

    exp = next((b for b in blocks if b.type == "concept"), None)
    ana = next((b for b in blocks if b.type == "analogy"), None)
    clozes = [b for b in blocks if b.type == "cloze"]
    mcq = next((b for b in blocks if b.type == "mcq"), None)
    exp_len = len(exp.content["text"]) if exp else 0
    summary.append(
        (label, exp_len, bool(ana), len(clozes), bool(mcq), len(gap), len(briefs), took)
    )

    print("=" * 70)
    print(f"{label}   {took:.1f}초 · 설명 {exp_len}자 · 빈칸 {len(clozes)}/{len(briefs)}"
          f" · 객관식 {'O' if mcq else 'X'} · 개념 언급 {covered}/{len(briefs)}")
    if explain(prof):
        print(f"  ⚡ {' · '.join(explain(prof))}")
    if missing:
        print(f"  ⚠️ 설명에 안 나온 개념: {', '.join(missing)}")
    if gap:
        print(f"  🔴 한 번도 안 꺼낸 개념: {', '.join(gap)}")
    print("-" * 70)
    if ana:
        print(f"💡 [{ana.content['label']}] {ana.content['text']}\n")
    if exp:
        print(exp.content["text"])
    for i, cz in enumerate(clozes, 1):
        print(f"\n✍️ {i}. {cz.content['sentence']}")
        print(f"     답: {cz.content['answer']}  ({', '.join(cz.concept_keys)})")
    if mcq:
        print(f"\n📝 {mcq.content['question']}")
        for o in mcq.content["options"]:
            mark = "✓" if o == mcq.content["answer"] else " "
            print(f"     {mark} {o}")
    print()

print("=" * 70)
print(f"{'조합':<18}{'설명':<8}{'비유':<6}{'빈칸':<8}{'객관식':<8}{'인출누락':<10}{'소요'}")
for label, ln, ana, cz, mq, gap, tot, took in summary:
    print(f"{label:<18}{ln:<8}{'O' if ana else 'X':<6}{f'{cz}/{tot}':<8}"
          f"{'O' if mq else 'X':<8}{gap:<10}{took:.1f}초")
if summary:
    lens = [s[1] for s in summary]
    print(f"\n길이 배율 {max(lens)/max(min(lens),1):.1f}x  "
          f"(1.5x 미만이면 성향이 결과를 충분히 바꾸지 못한 것)")
