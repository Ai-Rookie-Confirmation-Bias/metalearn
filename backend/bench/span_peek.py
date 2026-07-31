"""분할 결과를 눈으로 확인 — 구간 수·경계가 호출 수와 문항 품질을 결정한다.

`spans.split`을 고칠 때마다 여기부터 돌린다. 실측에서 표의 한 행이 두 구간으로
갈라져 용어("**최적 적합**")와 설명("단편화를 '최소화'…")이 떨어진 적이 있는데,
숫자만 봐서는 드러나지 않고 구간 본문을 눈으로 봐야 잡힌다.

사용: python3 bench/span_peek.py    (backend/ 에서, LLM 호출 없음)
"""
import ast
import sys
from pathlib import Path

_BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(_BENCH.parent))

from app.features.problems import spans  # noqa: E402

# volume_test는 import하면 실제 요청을 쏘므로, 원문 상수만 정적으로 꺼낸다.
_tree = ast.parse((_BENCH / "volume_test.py").read_text(encoding="utf-8"))
SOURCE = next(
    n.value.value
    for n in _tree.body
    if isinstance(n, ast.Assign) and n.targets[0].id == "SOURCE"  # type: ignore[attr-defined]
)

result = spans.split(SOURCE)
pairs = spans.pair_indices(result, 11)
print(f"구간 {len(result)}개, 쌍(limit=11) {len(pairs)}개 → {pairs}\n")
for s in result:
    head = f"[{s.heading}]" if s.heading else "[-]"
    print(f"#{s.index:<2} {s.length:>3}자 {head}")
    print("    " + s.text.replace("\n", " ⏎ ")[:110])
