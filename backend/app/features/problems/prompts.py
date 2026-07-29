"""문제 생성 프롬프트 빌더.

원칙(v1): **원문(source_text)에서만 출제. 외부 지식 소싱 금지.**
→ 검증(원문대조)·저작권 논리("파생 문항만 자산화")가 이 원칙 위에서 성립한다.
"""
from app.features.problems.schemas import ConceptInput

# 레벨 정의 — 프롬프트에 그대로 주입해 난이도 축을 고정.
_LEVEL_GUIDE = """레벨 정의:
- level 1 (암기): 원문의 용어·정의·사실을 그대로 재인출. 단순 확인.
- level 2 (적용): 원문 개념을 예시·상황에 적용하거나 개념 간 관계를 묻는다.
- level 3 (심화): 비교·구분·원인/결과 등 원문 내용을 종합해야 풀린다."""

_OUTPUT_SCHEMA = """반드시 아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{
  "problems": [
    {
      "level": <1|2|3>,
      "type": "mcq",
      "question": "질문(한국어)",
      "options": ["보기1", "보기2", "보기3", "보기4"],
      "answer": "options 중 정답과 글자까지 동일한 문자열",
      "explanation": "정답 근거 해설",
      "source_evidence": "원문에 실제로 존재하는 근거 문구를 그대로 인용"
    }
  ],
  "coverage_note": "원문이 특정 레벨을 뒷받침하기 부족하면 그 사실을 여기에 정직하게 적는다(없으면 빈 문자열)"
}"""


def build_generation_prompt(
    subject: str,
    concept: ConceptInput,
    per_level: int,
    feedback: str | None = None,
) -> str:
    keywords = ", ".join(concept.keywords) if concept.keywords else "(없음)"
    # 재시도 시 직전 부족/폐기 사유를 최상단에 주입 — 모델이 무엇을 고쳐야
    # 하는지 먼저 읽게 한다(자기수정 루프의 신호).
    feedback_block = (
        f"[직전 시도 피드백 — 반드시 반영]\n{feedback}\n\n" if feedback else ""
    )
    return f"""{feedback_block}너는 검증된 문제은행을 위한 출제 에이전트다. 과목은 "{subject}", 개념은 "{concept.title}".

[핵심 규칙]
1. 아래 <원문>에 실제로 적힌 내용만으로 출제한다. 원문에 없는 사실·수치·용어를 지어내지 마라.
2. 각 문항의 source_evidence는 <원문>에 그대로 존재하는 문구여야 한다(요약·창작 금지).
2-1. 비교·종합 문항처럼 원문 **여러 곳**을 근거로 쓸 때는, 각 인용을 원문 그대로
   옮기고 **줄바꿈(\n)으로 구분**해 이어 붙여라. 두 인용을 한 문장으로 합치거나
   연결어를 끼워 넣으면 원문과 글자가 달라져 폐기된다.
3. answer는 반드시 options 중 하나와 글자까지 동일해야 한다.
4. 오답 보기도 그 개념 맥락에서 그럴듯해야 한다(무관하거나 명백히 우스운 보기 금지).
5. 개념명이 곧 정답이 되어 정답이 유출되는 문항을 만들지 마라.
6. 원문이 특정 레벨을 뒷받침하지 못하면 그 레벨 문항 수를 줄이고 coverage_note에 사유를 적는다.
7. 모든 문항은 4지선다 객관식이다. question은 "다음 중 …은?", "…에 해당하는 것은?"처럼
   보기 선택을 요구하는 어투로 쓴다. "설명하시오/서술하시오/기술하시오" 같은 서술형 지시문은
   레벨과 무관하게 금지한다(L3 심화도 반드시 선택형 지문).

{_LEVEL_GUIDE}

목표: level 1/2/3 각각 최대 {per_level}문항의 4지선다(mcq)를 만든다.
참고 키워드: {keywords}

<원문>
{concept.source_text}
</원문>

{_OUTPUT_SCHEMA}"""
