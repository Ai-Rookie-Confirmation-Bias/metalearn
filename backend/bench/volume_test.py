"""볼륨 검증 — per_level을 올려가며 무엇이 깨지는지 본다.

전환 전(whole-concept, 개념 1콜) → 전환 후(span 단위 병렬) 실측:
    per_level=2   177.6초 커버 39% L1/2/3=3/1/1  →   47.3초 커버 31% 2/2/0
    per_level=5   303.5초 커버 33% L1/2/3=6/2/1  →   81.3초 커버 50% 5/3/2
    per_level=10  338.3초 커버 59% L1/2/3=6/4/4  →   76.6초 커버 76% 10/4/3
전환 전에는 매 실행마다 생성 호출 1회가 타임아웃됐고, 전환 후에는 0회다.
레벨 게이트가 의미를 가지려면 per_level 10~15가 필요하므로 판단 기준은 10 쪽이다.

주의: 1회 측정이라 몇 %p 차이는 노이즈다. 추세(시간·커버리지 단조성)만 읽어라.

사용: python3 bench/volume_test.py [per_level ...]     (backend/ 에서, 기본 2 5 10)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.features.problems import coverage  # noqa: E402
from app.features.problems.grounding import evidence_in_source  # noqa: E402

SOURCE = """### ■ 기억장치 관리 전략

| **전략** | **종류** | **설명** |
| --- | --- | --- |
| **반입 전략**

(Fetch) | 요구 반입 | 특정 프로그램/데이터의 참조를 '요구'할 때 적재 |
|  | 예상 반입 | 미래의 참조가 '예상'되는 데이터를 미리 적재 |
| **배치 전략**

(Placement) | **최초 적합**

(First Fit) | 사용 가능한 '첫 번째' 분할 영역에 데이터 배치 |
|  | **최적 적합**

(Best Fit) | 단편화를 '최소화'하는 분할 영역에 데이터 배치 |
|  | **최악 적합**

(Worst Fit) | 단편화를 '최대화'하는 분할 영역에 데이터 배치 |
| **교체 전략**

(Replacement) | - | 새로운 데이터를 배치하고자 할 때 기존 사용 중 데이터를 교체

ex. FIFO, OPT, LRU, LFU, NUR ··· |

### ■ 페이지 교체 알고리즘

| **알고리즘** | **설명** |
| --- | --- |
| **OPT** | • 앞으로 가장 오랫동안 사용하지 않을 페이지를 교체

• 페이지 부재 횟수가 가장 적게 발생 / 효율적 교체 알고리즘 |
| **FIFO** | • First-in First-out

• 가장 먼저 들어와 가장 오래 있었던 페이지를 교체 |
| **LRU** | • Least Recently Used

• 최근에 가장 오랫동안 사용하지 않은(오래 전에 사용된) 페이지를 교체 |
| **LFU** | • Least Frequently Used

• 사용 빈도가 가장 적은 페이지를 교체 / 활발한 페이지는 교체 X |"""


def run(per_level: int) -> None:
    payload = {
        "subject": "정보처리기사",
        "per_level": per_level,
        "concepts": [
            {
                "concept_id": "s_os_mem",
                "chapter_id": "ch_3",
                "chapter_title": "운영체제",
                "title": "기억장치 관리",
                "order": 1,
                "keywords": ["반입 전략", "배치 전략", "교체 전략", "페이지 교체 알고리즘"],
                "source_page": 9,
                "source_text": SOURCE,
            }
        ],
    }
    req = urllib.request.Request(
        "http://localhost:48011/api/agents/problems/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"per_level={per_level:<3} ❌ 실패: {type(exc).__name__} {exc}")
        return
    elapsed = time.time() - t0

    res = resp["results"][0]
    problems = res["problems"]
    lv: dict[int, int] = {1: 0, 2: 0, 3: 0}
    ty: dict[str, int] = {}
    bad_ev = 0
    for p in problems:
        lv[p["level"]] += 1
        ty[p["type"]] = ty.get(p["type"], 0) + 1
        if not evidence_in_source(p["source_evidence"], SOURCE):
            bad_ev += 1
    rep = coverage.analyze([p["source_evidence"] for p in problems], SOURCE)

    target = per_level * 3
    print(
        f"per_level={per_level:<3} {elapsed:6.1f}초  "
        f"생성 {len(problems):>2}/{target:<2} (수율 {len(problems)/target:.0%})  "
        f"L1={lv[1]} L2={lv[2]} L3={lv[3]}  "
        f"커버 {rep.percent:>3}%  근거불일치 {bad_ev}"
    )
    print(f"           유형 {ty}")
    print(f"           note: {res['coverage_note']}")


for arg in sys.argv[1:] or ["2", "5", "10"]:
    run(int(arg))
