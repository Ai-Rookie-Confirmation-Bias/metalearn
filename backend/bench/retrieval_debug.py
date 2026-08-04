"""인출 에이전트가 만든 것과 걸러진 것을 나란히 본다.

문항이 0개인 절이 생기면 여기부터 본다. 막는 규칙이 늘 때마다 겪은 문제라
(예시 베끼기 차단 → 인출 0개 3/6) 어디서 잘리는지 눈으로 봐야 한다.

사용: docker compose exec -T -w /app backend python bench/retrieval_debug.py [절번호…]
"""
import json
import sys
import urllib.request
from pathlib import Path

_ROOT = Path("/app") if Path("/app/app").exists() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.features.curriculum.agents import retrieval  # noqa: E402
from app.features.curriculum.blocks import (  # noqa: E402
    _TEMPLATE_MARKERS,
    ConceptBrief,
    _grounded,
    parse_response,
)
from app.features.curriculum.store import build_document  # noqa: E402

KEY = ""
for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line.startswith("UPSTAGE_API_KEY="):
        KEY = line.split("=", 1)[1].strip().strip("\"'")

IDS = [int(x) for x in sys.argv[1:]] or [0, 3]


def call(prompt: str) -> str:
    body = {
        "model": "solar-pro3",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        "https://api.upstage.ai/v1/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=200) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]


doc = build_document(_ROOT / "tests/fixtures/파싱결과_실기요약노트.md")
for idx in IDS:
    sec = doc.chapters[0].sections[idx]
    briefs = [ConceptBrief(c.key, c.definition) for c in sec.concepts]
    exp = " ".join(f"{c.key}는 {c.definition}" for c in sec.concepts)
    raw = call(retrieval.build_prompt(sec.title, briefs, exp, sec.source))
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
    except ValueError:
        print(f"── {sec.title}: JSON 깨짐\n{raw[:200]}")
        continue

    grounds = "\n".join(x for x in (sec.source, exp) if x)
    print(f"── [{idx}] {sec.title} · 개념 {[c.key for c in sec.concepts]}")
    items = data.get("cloze") or []
    if not items:
        print("   cloze 자체가 없다. 응답 키:", list(data))
    for it in items:
        s, a = it.get("sentence", ""), it.get("answer", "")
        why = []
        if "____" not in s:
            why.append("빈칸표시없음")
        if a and a in s.replace("____", ""):
            why.append("정답노출")
        if any(m in s for m in _TEMPLATE_MARKERS):
            why.append("템플릿")
        if len(s.replace("____", "").strip()) < 10:
            why.append("문맥짧음")
        if not _grounded(a, briefs, grounds):
            why.append("근거없음")
        print(f"   {'❌ ' + ','.join(why) if why else '✅'}  {a!r} ← {s[:52]}")
    kept = parse_response(raw, briefs, grounds)
    print(f"   → 남은 {[b.type for b in kept]}\n")
