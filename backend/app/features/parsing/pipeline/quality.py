"""1단계 품질 진단 — OCR 결과가 쓸 만한지 수치로 가른다. Solar 0회.

원문을 눈으로 훑는 것만으로는 "이 정도면 괜찮은가"를 판단할 수 없다.
그보다 나쁜 경우도 있다 — **눈에 보이지도 않는 손상.**

실측 사고(정처기 필기 요약, ocr=auto): 본문이 "현대적인프로그래밍기술을"처럼
붙어 보여서 공백 소실로 판단했는데, 실제 바이트를 세어보니 어절 사이가
U+0007(BEL) 제어문자였다. 문서 전체에 13,730개 — 정상 스페이스의 29%다.
BEL은 화면에도 마크다운에도 안 그려지므로 사람 눈으로는 절대 못 찾는다.
그런데 정규식 \\s에도 안 걸려서 문장 분리·임베딩·LLM 입력이 전부 망가진다.

그래서 여기서는 **보이지 않는 것부터 센다.** 재는 것은 파서가 준 텍스트의
표면 품질이지 내용의 정확도가 아니다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.features.parsing.pipeline import segment as segment_module
from app.features.parsing.schemas import Element

# 공백 없이 이어붙은 글자 덩어리. 한국어 어절은 평균 3~4자라 25자가 공백
# 없이 붙어 있으면 스페이스가 소실된 것으로 본다. 영문 단어나 식별자
# (setInterval, ISO/IEC 9126)가 걸리는 걸 피하려고 문턱을 넉넉히 잡았다.
_GLUED_RE = re.compile(r"[0-9A-Za-z가-힣]{25,}")

# 문장이 끝났다고 볼 표시. 한국어 요약 자료는 마침표를 생략하는 일이 잦아
# 종결어미도 함께 본다("~한다", "~함", "~임").
_TERMINATORS = ".!?。！？:;…"
_TERMINAL_SUFFIXES = ("다", "음", "함", "임", "됨", "요")

# 표·코드·수식·이미지 마크다운은 문장이 아니다 — 끊김 비율에서 뺀다.
_MARKUP_PREFIXES = ("|", "```", "$$", "<", "![", "#")
# 이보다 짧은 요소는 제목·번호·페이지 표기라 끊김 판정 대상이 아니다.
_SENTENCE_MIN_CHARS = 12

# 안 보이는 제어문자. 탭·개행·캐리지리턴은 정상 서식이라 뺀다.
# 실측: 이 PDF는 스페이스 자리에 U+0007(BEL)이 들어온다.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# ── 판정 문턱 ──────────────────────────────────────────────────────
# 한국어 산문의 공백 비율은 보통 15~20%. 표·기호가 섞이는 걸 감안해
# 10% 아래면 스페이스가 사라진 것으로 본다.
MIN_SPACE_RATIO = 10
# 제어문자는 원래 0개여야 한다. 0.5%만 넘어도 우연이 아니라 인코딩 문제다.
MAX_CONTROL_RATIO = 1
# 공백 소실 덩어리가 이 비율을 넘으면 국소 오류가 아니라 전면적 손상이다.
MAX_GLUED_RATIO = 5
# 참고 수치 전용 — **판정에는 쓰지 않는다.**
# 시각적 줄바꿈이 문장을 끊으면 오를 거라 기대했지만, 실측에서 구분력이
# 없었다: 깨진 원문 77% vs 정상 한국어 94%로 오히려 정상 쪽이 더 높다.
# 종결부호 없이 명사로 끝나는 항목("… 소프트웨어 품질 표준")이 한국어
# 요약 자료에서는 정상이기 때문이다. 경보를 울리면 거짓말이 되므로
# 숫자만 보여주고 판단은 사람에게 맡긴다.
MAX_UNTERMINATED_RATIO = 40


@dataclass
class ParseQuality:
    """1단계 산출물의 표면 품질. 전부 0~100 정수(%)."""

    elements: int = 0
    pages: int = 0
    chars: int = 0
    avg_chars: int = 0
    space_ratio: int = 0          # 전체 문자 중 공백 비율
    control_ratio: int = 0        # 안 보이는 제어문자 비율
    control_chars: int = 0        # 제어문자 개수 (0이어야 정상)
    control_names: list[str] = field(default_factory=list)  # 예: "U+0007 ×13,730"
    glued_ratio: int = 0          # 공백 없이 25자+ 이어진 구간의 문자 비율
    unterminated_ratio: int = 0   # 종결 없이 끝난 본문 요소 비율
    problems: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.problems

    @property
    def verdict(self) -> str:
        return "정상" if self.is_clean else " · ".join(self.problems)

    def to_summary(self) -> dict[str, object]:
        """디버그 화면의 요약 표에 그대로 들어갈 형태."""
        return {
            "제어문자": (
                f"{self.control_chars:,}개 ({self.control_ratio}%) — "
                + ", ".join(self.control_names)
                if self.control_chars
                else "없음"
            ),
            "공백 비율": f"{self.space_ratio}% (기준 {MIN_SPACE_RATIO}% 이상)",
            "붙은 글자": f"{self.glued_ratio}% (기준 {MAX_GLUED_RATIO}% 이하)",
            # 판정에 안 쓰는 참고 수치라 기준값을 적지 않는다.
            "끊긴 요소": f"{self.unterminated_ratio}% (참고)",
            "판정": self.verdict,
        }


def measure(elements: list[Element]) -> ParseQuality:
    """요소 배열의 표면 품질을 잰다. 원문은 건드리지 않는다."""
    texts = [segment_module.element_text(el) for el in elements]
    texts = [t for t in texts if t]
    if not texts:
        return ParseQuality(elements=len(elements))

    joined = "\n".join(texts)
    chars = len(joined)
    spaces = sum(1 for c in joined if c.isspace())

    controls = _CONTROL_RE.findall(joined)
    counted: dict[str, int] = {}
    for char in controls:
        key = f"U+{ord(char):04X}"
        counted[key] = counted.get(key, 0) + 1

    # 제어문자는 대개 공백 자리에 들어온다. 붙음·끊김 판정에서는 공백으로
    # 되돌려놓고 본다 — 안 그러면 같은 손상이 세 지표에 중복으로 잡힌다.
    normalized = [_CONTROL_RE.sub(" ", t) for t in texts]

    glued_chars = 0
    worst: list[tuple[int, str]] = []
    for text in normalized:
        for match in _GLUED_RE.finditer(text):
            glued_chars += len(match.group())
            worst.append((len(match.group()), match.group()))

    sentences = [t for t in normalized if _is_sentence_like(t)]
    unterminated = [t for t in sentences if not _looks_terminated(t)]

    quality = ParseQuality(
        elements=len(elements),
        pages=max((int(el.get("page") or 0) for el in elements), default=0),
        chars=chars,
        avg_chars=chars // len(texts),
        space_ratio=round(spaces * 100 / chars),
        control_ratio=round(len(controls) * 100 / chars),
        control_chars=len(controls),
        control_names=[
            f"{key} ×{n:,}"
            for key, n in sorted(counted.items(), key=lambda kv: -kv[1])
        ],
        glued_ratio=round(glued_chars * 100 / chars),
        unterminated_ratio=(
            round(len(unterminated) * 100 / len(sentences)) if sentences else 0
        ),
        samples=[t for _, t in sorted(worst, reverse=True)[:3]],
    )

    # 제어문자가 있으면 그게 1순위 증거다 — 안 보이는 손상이라 실물을
    # 보여줘야 한다. 화면에 그리려고 여기서 보이는 기호로 바꾼다.
    if controls:
        quality.samples = [
            _CONTROL_RE.sub("␇", t)[:120] for t in texts if _CONTROL_RE.search(t)
        ][:3]

    # 제어문자를 공백으로 세어준 값. 이게 정상이면 "공백이 없는" 게 아니라
    # "공백이 다른 문자로 들어온" 것이다 — 원인이 다르면 처방도 다르다.
    restored_space_ratio = round((spaces + len(controls)) * 100 / chars)

    if quality.control_ratio >= MAX_CONTROL_RATIO:
        quality.problems.append(
            f"제어문자 혼입({quality.control_chars:,}개, {quality.control_ratio}%)"
        )
    if restored_space_ratio < MIN_SPACE_RATIO:
        quality.problems.append(f"공백 소실(공백 {quality.space_ratio}%)")
    if quality.glued_ratio > MAX_GLUED_RATIO:
        quality.problems.append(f"글자 붙음({quality.glued_ratio}%)")

    return quality


def _is_sentence_like(text: str) -> bool:
    """문장으로 볼 요소인가. 표·코드·제목·번호는 제외한다."""
    stripped = text.lstrip("-*•· \t")
    if len(stripped) < _SENTENCE_MIN_CHARS:
        return False
    return not stripped.startswith(_MARKUP_PREFIXES)


def _looks_terminated(text: str) -> bool:
    """문장이 끝맺어졌는가. 종결부호 또는 종결어미."""
    tail = text.rstrip().rstrip("\"')]』」”’")
    if not tail:
        return False
    return tail[-1] in _TERMINATORS or tail.endswith(_TERMINAL_SUFFIXES)
