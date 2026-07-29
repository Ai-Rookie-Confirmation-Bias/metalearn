"""[순수로직] 문항 형식 품질 규칙 — 근거 대조(grounding) 밖의 출제 규칙.

DB·LLM 비의존. 프롬프트로 지시해도 모델이 반복해서 어기는 항목을
코드에서 확정적으로 차단한다(폐기 → 사유를 피드백으로 재생성).

실측 근거: 프롬프트 규칙에 "서술형 지시문 금지"를 명시했는데도
L3(심화) 문항이 계속 "…비교하여 설명하시오"로 생성됐다. 보기 4개를
주면서 서술을 요구하는 것은 형식 모순이고, 학습자에게는 무엇을 하라는
것인지 모호한 지문이 된다. 프롬프트는 확률이고 코드는 확정이므로
이런 규칙은 코드로 내린다.

일부 규칙은 feat/yoonhs-integration의 learning/generator.py에서 가져왔다
(IWF — Item-Writing Flaws 방지). 그쪽에서 이미 실측·대응한 결함이라
같은 실수를 반복할 이유가 없다.
"""
import re

# 서술을 요구하는 종결형 — 객관식 지문에 오면 형식 모순.
_FREE_RESPONSE_ENDINGS: tuple[str, ...] = (
    "설명하시오",
    "설명하라",
    "서술하시오",
    "서술하라",
    "기술하시오",
    "기술하라",
    "쓰시오",
    "작성하시오",
    "나열하시오",
    "논하시오",
    "제시하시오",
    "말하시오",
    "비교하시오",
    "구하시오",
)

# 지문 끝의 문장부호·따옴표는 판정에 무관하므로 걷어낸다.
_TRAILING = " \t\n.?!。'\"”’)"


def is_free_response_style(question: str) -> bool:
    """객관식인데 서술을 요구하는 지문이면 True(→ 폐기 대상).

    "다음 중 옳은 설명은?" 처럼 '설명'이 명사로 쓰인 경우는 통과시킨다
    (종결형만 보므로 오폐기가 나지 않는다).
    """
    return question.strip().rstrip(_TRAILING).endswith(_FREE_RESPONSE_ENDINGS)


# LLM이 보기 텍스트에 자체 라벨("A. ", "1) ")을 붙이면 화면 라벨과 겹쳐
# "A) A. FIFO"로 보이고, answer와 options의 글자 일치도 깨진다.
_OPTION_LABEL_RE = re.compile(r"^\s*(?:[A-Da-d]|[1-4])[.)]\s*")


def strip_option_label(text: str) -> str:
    """보기 앞에 붙은 자체 라벨을 제거한다."""
    return _OPTION_LABEL_RE.sub("", text.strip())


def _tight(s: str) -> str:
    """공백·문장부호를 걷어낸 비교용 표기."""
    return re.sub(r"[\s.,·'\"()\[\]]+", "", s)


def answer_leaked_in_title(answer: str, concept_title: str) -> bool:
    """정답 보기가 개념명 안에 통째로 들어있으면 유출(→ 폐기).

    개념명은 화면에 절 제목으로 노출되므로, 정답이 제목에 그대로 있으면
    학습자가 지문을 읽지 않고도 답을 안다. 부분 포함은 힌트 수준이라 살린다.
    (integration learning/generator.py `_mcq_answer_leaked` 이식)
    """
    a, t = _tight(answer), _tight(concept_title)
    return bool(a) and bool(t) and a in t
