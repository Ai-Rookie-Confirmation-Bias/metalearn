"""성향 축 검증 — 같은 개념을 4조합으로 생성해 나란히 본다.

왜 필요한가:
    축을 아무리 잘 나눠도 **결과물이 비슷하면 사용자는 맞춤을 못 느낀다.**
    지시문을 넣었을 때 실제로 눈에 띄게 달라지는지를 먼저 확인해야,
    축 설계가 맞았는지 알 수 있다. 다르지 않으면 축으로 돌아가야 한다.

같이 확인하는 것:
    원문에 띄어쓰기가 없다(`•이전단계로돌아갈수없다는`). 실제 파싱 출력이
    이 상태라, LLM이 이걸 읽어내는지도 여기서 드러난다.

의존성 없이 urllib로 직접 호출한다(호스트에서 바로 실행 가능).
사용: python3 bench/profile_compare.py     (backend/ 에서)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.curriculum.profile import (  # noqa: E402
    empty_profile,
    explain,
    observe,
    prompt_block,
)

# API 키는 .env에서만 읽고 출력하지 않는다.
# .env 값이 따옴표로 감싸여 있을 수 있다(pydantic-settings는 벗겨주지만 여기선 직접 읽는다).
_ENV = Path(__file__).resolve().parents[1] / ".env"
KEY = ""
for line in _ENV.read_text(encoding="utf-8").splitlines():
    if line.startswith("UPSTAGE_API_KEY="):
        KEY = line.split("=", 1)[1].strip().strip("\"'")
if not KEY:
    sys.exit(".env에 UPSTAGE_API_KEY가 없다")

URL = "https://api.upstage.ai/v1/chat/completions"
MODEL = "solar-pro3"

# 실제 파싱 출력 그대로 — 띄어쓰기 없음, 줄 중간 절단, 노이즈(`초/치기`) 포함.
# 절 단위를 흉내내려고 항목 셋을 이어 붙였다(001·002·005).
SOURCE = """001

소프트웨어 공학의 기본 원칙

- •현대적인프로그래밍기술을계속적으로적용해야한다.
- •개발된소프트웨어의품질이유지되도록지속적으로검
- 증해야한다.
- •소프트웨어개발관련사항및결과에대한명확한기록
- 을유지해야한다.

002

폭포수 모형

초

치기

- •이전단계로돌아갈수없다는전제하에각단계를확
- 실히매듭짓고다음단계를진행하는개발방법론이다.
- •보헴이제시한고전적생명주기모형이다.
- •요구사항을반영하기어렵다.

초

치기

- •나선을따라돌듯이점진적으로완벽한최종소프트웨
- 어를개발하는것이다.
- •‘계획수립→위험분석→개발및검증→고객평가’
- 과정이반복적으로수행된다.

005

애자일 개발 4가지 핵심 가치

- •개인과상호작용,실행되는소프트웨어,고객과의협업,
- 변화에대한대응을중시한다."""

CONCEPT = "소프트웨어 개발 방법론"


def build_prompt(profile_block: str) -> str:
    """학습 블록 생성 프롬프트. 성향 지시는 블록으로 끼운다.

    ⚠️ 1차 실험 실패에서 배운 것:
        "원문에 있는 사실만 써라"와 "비유를 먼저 놓아라"가 충돌해서 모델이
        안전한 쪽(원문 복창)을 택했고, 5조합이 전부 같은 글이 됐다.
        비유·배경은 본질적으로 원문 밖 정보다. **설명 본문은 원문에 묶고,
        비유는 별도 필드로 빼서 원문 밖을 허용**해야 성향이 작동한다.
    """
    tail = f"\n{profile_block}\n" if profile_block else "\n"
    return f"""너는 학습 콘텐츠를 쓰는 에이전트다. 아래 <원문>으로 "{CONCEPT}"를 설명하라.

[규칙]
1. **설명 본문(explanation)**: <원문>에 있는 사실만 쓴다. 없는 사실을 지어내지 마라.
   단 **설명하는 방식·순서·분량은 자유**다 — 아래 [설명 방식]을 따르라.
2. 원문의 **모든 항목을 빠뜨리지 마라.** 요약하지 말고 전부 다뤄라.
3. **비유(analogy)**: 이해를 돕는 장치이므로 **원문 밖에서 가져와도 된다.**
   일상 경험에 빗대라. 쓰지 않을 거면 null.
4. 원문은 PDF 추출본이라 띄어쓰기가 없고 항목 번호(001 등)와 잡음이 섞여 있다.
   읽어서 이해하되, 잡음은 버리고 설명은 정상적인 한국어로 써라.
5. 학습자가 읽을 글이다. "원문에 따르면" 같은 메타 표현은 쓰지 마라.
{tail}
<원문>
{SOURCE}
</원문>

아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{{"explanation": "설명 본문", "analogy": "비유 (안 쓸 거면 null)"}}"""


def call(prompt: str) -> tuple[dict, float]:
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
    took = time.time() - t0
    return json.loads(raw[raw.find("{") : raw.rfind("}") + 1]), took


def profile_for(rep_high: bool | None, depth_high: bool | None):
    """축을 2회씩 관찰해 확정 상태로 만든다. None이면 중립(미측정)."""
    p = empty_profile()
    for axis, toward in (("representation", rep_high), ("depth", depth_high)):
        if toward is None:
            continue
        for _ in range(2):
            p = observe(p, axis, toward)
    return p


CASES = [
    ("① 비유 · 왜까지", True, True),
    ("② 비유 · 결론만", True, False),
    ("③ 정의 · 왜까지", False, True),
    ("④ 정의 · 결론만", False, False),
    ("⑤ (중립 — 미측정)", None, None),
]

print(f"개념: {CONCEPT}")
print(f"원문: {len(SOURCE)}자 (띄어쓰기 없음, 노이즈 포함)\n")

results = []
for label, rep, dep in CASES:
    prof = profile_for(rep, dep)
    block = prompt_block(prof)
    try:
        out, took = call(build_prompt(block))
    except Exception as e:  # noqa: BLE001
        print(f"{label}  ❌ {type(e).__name__}: {e}")
        continue
    exp = (out.get("explanation") or "").strip()
    ana = (out.get("analogy") or "")
    ana = ana.strip() if isinstance(ana, str) else ""
    results.append((label, exp, ana, took))

    print("=" * 66)
    print(f"{label}   {took:.1f}초 · 설명 {len(exp)}자 · 비유 {'있음' if ana else '없음'}")
    if explain(prof):
        print(f"  ⚡ {' · '.join(explain(prof))}")
    print("-" * 66)
    if ana:
        print(f"💡 {ana}\n")
    print(exp)
    print()

print("=" * 66)
print(f"{'조합':<20}{'설명 길이':<12}{'비유':<8}{'소요'}")
for label, exp, ana, took in results:
    print(f"{label:<20}{len(exp):<12}{'O' if ana else 'X':<8}{took:.1f}초")

if results:
    lens = [len(e) for _, e, _, _ in results]
    print(f"\n길이 편차: 최소 {min(lens)}자 ~ 최대 {max(lens)}자 (배율 {max(lens)/max(min(lens),1):.1f}x)")
    print("→ 배율이 1.5배 미만이면 축이 결과를 충분히 바꾸지 못하는 것이다.")
