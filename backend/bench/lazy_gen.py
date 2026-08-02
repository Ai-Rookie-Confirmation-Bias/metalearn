"""지연 생성 검증 — 구간을 나눠 요청했을 때 이어지는지, 빨라지는지.

과목 전체를 한 번에 만들면 실측 1시간 30분이다(목차 7개 × 12분). 첫 세트에
필요한 구간만 만들고 나머지를 뒤로 미루면 첫 화면까지의 대기가 사라진다.
여기서 확인하는 것:
  ① span_limit이 걸리면 실제로 빨라지는가
  ② next_span으로 이어받아 끝까지 도달하는가 (누락 없이)
  ③ 나눠 만든 문항 총합이 한 번에 만든 것과 비슷한가

사용: python3 bench/lazy_gen.py [chunk]    (backend/ 에서, 기본 4)
"""
import ast
import json
import sys
import time
import urllib.request
from pathlib import Path

_BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(_BENCH.parent))

_tree = ast.parse((_BENCH / "volume_test.py").read_text(encoding="utf-8"))
SOURCE = next(
    n.value.value
    for n in _tree.body
    if isinstance(n, ast.Assign) and n.targets[0].id == "SOURCE"  # type: ignore[attr-defined]
)
CHUNK = int(sys.argv[1]) if len(sys.argv) > 1 else 4


def call(offset: int, limit: int | None) -> tuple[dict, float]:
    payload = {
        "subject": "정보처리기사",
        "per_level": 5,
        "span_offset": offset,
        "concepts": [
            {
                "concept_id": "s_os_mem",
                "chapter_id": "ch_3",
                "chapter_title": "운영체제",
                "title": "기억장치 관리",
                "order": 1,
                "keywords": [],
                "source_page": 9,
                "source_text": SOURCE,
            }
        ],
    }
    if limit is not None:
        payload["span_limit"] = limit
    req = urllib.request.Request(
        "http://localhost:48011/api/agents/problems/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8"))["results"][0], time.time() - t0


print(f"── 나눠 생성 (구간 {CHUNK}개씩) ─────────────────────────────")
offset: int | None = 0
total, first_wait, elapsed_all = 0, 0.0, 0.0
rounds = 0
while offset is not None:
    res, took = call(offset, CHUNK)
    rounds += 1
    elapsed_all += took
    if rounds == 1:
        first_wait = took
    total += len(res["problems"])
    print(
        f"  {rounds}차  offset={offset:<3} {took:5.1f}초  "
        f"문항 {len(res['problems']):>2}  next={res['next_span']}"
    )
    print(f"        {res['coverage_note']}")
    offset = res["next_span"]

print(f"\n── 한 번에 생성 ───────────────────────────────────────────")
whole, whole_took = call(0, None)
print(f"  {whole_took:5.1f}초  문항 {len(whole['problems'])}  {whole['coverage_note']}")

print(f"\n{'=' * 58}")
print(f"첫 화면까지 대기   {first_wait:5.1f}초  ←→  {whole_took:5.1f}초 (한 번에)")
print(f"총 소요            {elapsed_all:5.1f}초 ({rounds}회)")
print(f"총 문항            {total}개  ←→  {len(whole['problems'])}개 (한 번에)")
