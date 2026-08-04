"""인출 품질 검사 — 생성된 빈칸·객관식이 **인출로서 성립하는지** 본다.

`parse_response`가 거르는 건 형식뿐이다(빈칸 표시 유무, 정답이 문장에 노출,
스키마 베끼기). 형식이 맞아도 인출이 안 되는 문항이 있다:

  · 정답이 **설명 본문에 없다** — 방금 읽은 글에서 못 꺼내니 인출이 아니라 퀴즈다
  · 정답이 **원문에 없다** — 모델이 지어낸 것
  · 정답이 조사·서술어다 — `이전 단계로 ____ 수 없다`는 문법으로 풀린다
  · 객관식 보기에 이 절 개념이 하나뿐 — 구별 문항이 성립하지 않는다

이걸 자동으로 세고, 걸린 문항은 눈으로 보라고 그대로 찍는다.

사용: python3 bench/retrieval_check.py [파싱결과.md] [절_개수]
"""
import json
import re
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
from app.features.curriculum.excerpt import normalize_spaces, section_source  # noqa: E402
from app.features.curriculum.grouping import Concept, group_into_sections  # noqa: E402
from app.features.curriculum.parsing_md import parse  # noqa: E402

KEY = ""
for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("UPSTAGE_API_KEY="):
        KEY = line.split("=", 1)[1].strip().strip("\"'")
if not KEY:
    sys.exit(".env에 UPSTAGE_API_KEY가 없다")

URL = "https://api.upstage.ai/v1/chat/completions"
MODEL = "solar-pro3"

md = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/파싱결과_실기요약노트.md"
want = int(sys.argv[2]) if len(sys.argv) > 2 else 6

# 한국어 서술어/조사 꼬리. 정답이 이걸로 끝나면 용어가 아니라 문법 조각이다.
_TAIL = re.compile(r"(할|한|하는|하다|되는|된|될|있는|없는|갈|간|온|든|는|을|를|이|가)$")


def squash(text: str) -> str:
    return re.sub(r"\s+", "", normalize_spaces(text))


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


# ── 절 고르기: 조각을 넓게 훑도록 한 조각당 하나씩 ──────────────────
doc = parse(md)
picked: list[tuple] = []
for chunk in doc.chunks:
    if len(picked) >= want:
        break
    concepts = [
        Concept(c.key, c.definition, c.prerequisites, c.order, str(chunk.index))
        for c in chunk.concepts
    ]
    sections = group_into_sections(concepts, chunk.text)
    body = [s for s in sections if 3 <= s.size <= 6]
    if body:
        picked.append((chunk, body[len(body) // 2]))

print(f"📄 {doc.title} · 절 {len(picked)}개 검사 · {MODEL}\n")

TOTALS = {
    "cloze": 0,
    "설명에 없음": 0,
    "원문에 없음": 0,
    "문법 조각": 0,
    "개념 라벨 없음": 0,
    "mcq": 0,
    "구별 안 됨": 0,
    "인출 누락": 0,
    "개념": 0,
}
flagged: list[str] = []

for chunk, section in picked:
    briefs = [ConceptBrief(c.key, c.definition) for c in section.concepts]
    src = section_source(
        chunk.text,
        [c.key for c in section.concepts],
        [c.key for c in chunk.concepts],
    )
    try:
        raw, took = call(build_prompt(section.title, briefs, "", src))
    except Exception as e:  # noqa: BLE001
        print(f"❌ {section.title}: {type(e).__name__}: {e}")
        continue

    blocks = parse_response(raw, briefs)
    explanation = next((b.content["text"] for b in blocks if b.type == "concept"), "")
    clozes = [b for b in blocks if b.type == "cloze"]
    mcq = next((b for b in blocks if b.type == "mcq"), None)
    covered, missing = coverage(blocks, briefs)
    gap = retrieval_gap(blocks, briefs)

    exp_sq, src_sq = squash(explanation), squash(src)
    keys = {c.key for c in section.concepts}
    bad_here: list[str] = []

    TOTALS["개념"] += len(briefs)
    TOTALS["인출 누락"] += len(gap)
    for cz in clozes:
        TOTALS["cloze"] += 1
        ans = cz.content["answer"]
        if squash(ans) not in exp_sq:
            TOTALS["설명에 없음"] += 1
            bad_here.append(f"    ⚠️ 설명에 없는 답: {ans!r} — {cz.content['sentence']}")
        if squash(ans) not in src_sq:
            TOTALS["원문에 없음"] += 1
            bad_here.append(f"    🔴 원문에 없는 답: {ans!r} — {cz.content['sentence']}")
        if _TAIL.search(ans) and ans not in keys:
            TOTALS["문법 조각"] += 1
            bad_here.append(f"    ⚠️ 문법으로 풀림: {ans!r} — {cz.content['sentence']}")
        if len(cz.concept_keys) != 1:
            TOTALS["개념 라벨 없음"] += 1

    if mcq:
        TOTALS["mcq"] += 1
        opts = mcq.content["options"]
        overlap = sum(1 for o in opts if o in keys)
        if overlap < 2:
            TOTALS["구별 안 됨"] += 1
            bad_here.append(
                f"    ⚠️ 절 개념이 보기에 {overlap}개뿐: {' / '.join(opts)}"
            )

    mark = "🔴" if bad_here else "✅"
    print(
        f"{mark} {section.title}  (개념 {len(briefs)})  {took:.0f}초 · "
        f"빈칸 {len(clozes)} · 객관식 {'O' if mcq else 'X'} · "
        f"언급 {covered}/{len(briefs)} · 인출누락 {len(gap)}"
    )
    for line in bad_here:
        print(line)
    flagged += bad_here

cz = max(TOTALS["cloze"], 1)
print("\n" + "=" * 66)
print(f"빈칸 {TOTALS['cloze']}개 / 개념 {TOTALS['개념']}개 · 객관식 {TOTALS['mcq']}개")
for k in ("설명에 없음", "원문에 없음", "문법 조각", "개념 라벨 없음"):
    print(f"   {k:<12} {TOTALS[k]:>3}개  {TOTALS[k]/cz:.0%}")
print(f"   {'구별 안 됨':<12} {TOTALS['구별 안 됨']:>3}개  (객관식 {TOTALS['mcq']}개 중)")
print(f"   {'인출 누락':<12} {TOTALS['인출 누락']:>3}개  (개념 {TOTALS['개념']}개 중)")
