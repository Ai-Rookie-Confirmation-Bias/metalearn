"""검증기 프롬프트 — 심판(체크리스트) · 풀이자(왕복 검증) · 수정(불합격 재작성).

식별 문구는 테스트·호출 분기의 계약이다:
심판 = "출제 검수자" / 풀이자 = "수험생" / 수정 = "검수 불합격".
"""
import json

from app.core.quality.checks import strip_answers
from app.core.quality.types import CandidateItem


def build_judge_prompt(items: list[CandidateItem], neutral_example: bool = False) -> str:
    """문항 묶음 심판 — 정답 유일성 + 근거 대조 체크리스트.

    neutral_example=True면 출력 예시에서 구체적 사유 문구를 뺀다 —
    K-EXAONE이 예시 문구("오답 선지 '피드백'…")를 판정 사유로 그대로
    복사하는 실측 문제 대응 (배심원단 2차 심판용).
    """
    blocks = [
        f"[문항 {i}] ({it.type})\n"
        f"내용: {json.dumps(it.data, ensure_ascii=False)}\n"
        f"근거: {it.evidence_text}"
        for i, it in enumerate(items)
    ]

    if neutral_example:
        example = (
            '[{"index":0,"pass":true,"reason":""},'
            '{"index":1,"pass":false,"reason":"<이 문항의 실제 불합격 사유 한 문장>"}]'
        )
        example += "\nreason은 반드시 해당 문항의 실제 내용에서 나온 사유여야 한다. 예시 문구를 복사하지 마라."
    else:
        example = (
            '[{"index":0,"pass":true,"reason":""},'
            '{"index":1,"pass":false,"reason":"오답 선지 \'피드백\'이 원문에서 참"}]'
        )

    return f"""너는 출제 검수자다. 각 문항을 근거 원문과 대조해 판정하라.

{chr(10).join(blocks)}

채점은 사람이 아니라 문자열 완전일치로 이뤄진다. 아래를 하나라도 어기면 불합격이다.

- Q1. 정답이 근거 원문으로 뒷받침되는가?
- Q2. (객관식) 오답 선지 중 원문에서 사실상 참이 되는 것이 있는가? 있으면 불합격 (정답이 2개가 됨)
- Q3. (객관식) 선지가 정확히 4개인가? 아니면 불합격
- Q4. 정답을 그대로 받아쓸 수 있는가? 정답이 한 문장만큼 길거나, 같은 뜻을 여러 표현으로
      쓸 수 있어 완전일치가 사실상 불가능하면 불합격
- Q5. (빈칸) 빈칸이 3개 이상이거나, 빈칸들이 순서가 바뀌어도 맞는 나열이면 불합격
      (채점이 빈칸 순서를 따지므로 정답이 유일하지 않게 된다)
- Q6. (빈칸) 빈칸을 정답으로 채운 문장이 자연스러운 한국어 문장인가? 비문이면 불합격
- Q7. 발문이 시험 문체인가? 구어체·경어체("~인가요?", "~합니다")면 불합격
- Q8. 발문의 설명에 들어맞는 답이 원문에 둘 이상 있지 않은가? 있으면 불합격 (정답이 유일하지 않다)
- Q9. 발문·해설에 문장 번호(s38 같은 표기)가 노출되지 않았는가? 노출되면 불합격
- Q10. (빈칸) 빈칸이 번호·기호처럼 의미 없는 자리가 아닌가? 그렇다면 불합격
- Q11. 문항 표현에 모순·모호함이 없는가?

[출력] JSON 배열만 출력하라. reason은 **결론만 한 문장(60자 이내)** — 판정 과정·Q번호
검토·중간 추론을 쓰면 응답이 잘려 전체가 무효 처리된다. 합격이면 빈 문자열.
{example}"""


def build_solve_prompt(items: list[CandidateItem]) -> str:
    """풀이 왕복 검증 — 정답을 가린 문항을 근거만 보고 실제로 풀게 한다.

    "정답이 유일한가?"를 묻지 않고 실험한다: 풀이자가 키 정답에 도달하지
    못하거나 복수 정답이라 판단하면 그 문항은 모호하다는 실험적 증거.
    """
    blocks = [
        f"[문항 {i}] ({it.type})\n"
        f"문제: {json.dumps(strip_answers(it.type, it.data), ensure_ascii=False)}\n"
        f"근거 원문: {it.evidence_text}"
        for i, it in enumerate(items)
    ]

    return f"""너는 수험생이다. 각 문항을 근거 원문만 보고 풀어라.

{chr(10).join(blocks)}

[답 형식 — 유형별]
- mcq: 정답이라고 볼 수 있는 선지 번호(0부터)를 전부 담은 배열. 확실히 하나면 [2]처럼 하나만,
  둘 이상이 정답으로 보이면 모두 나열하라 (억지로 하나를 고르지 마라)
- cloze: 빈칸 순서대로 답 문자열 배열
- shortAnswer: 답 문자열 하나
- trueFalse: true 또는 false

[출력] JSON 배열만 출력하라. 다른 텍스트 금지:
[{{"index":0,"answer":[2]}},{{"index":1,"answer":"델파이 기법"}}]"""


def build_revision_prompt(items: list[CandidateItem], reasons: list[str]) -> str:
    """검수 불합격 문항 재작성 — 사유를 반영해 data만 수정 (critique-revise 루프)."""
    blocks = [
        f"[문항 {i}] ({it.type})\n"
        f"원본 data: {json.dumps(it.data, ensure_ascii=False)}\n"
        f"불합격 사유: {reason}\n"
        f"근거 원문: {it.evidence_text}"
        for i, (it, reason) in enumerate(zip(items, reasons))
    ]

    return f"""아래 문항들이 검수 불합격했다. 각 불합격 사유를 해소하도록 data를 수정하라.

{chr(10).join(blocks)}

[규칙]
1. 사유를 해소하는 최소 수정만 하라. 문항의 개념·유형은 바꾸지 마라.
2. 정답의 근거는 반드시 근거 원문 안에 있어야 한다. 원문에 없는 사실 금지.
3. 사유를 해소할 수 없으면 그 문항은 출력에서 빼라 (억지 수정 금지).
4. 발문·해설에 문장 번호(s38 같은 표기)를 쓰지 마라.

[출력] 수정한 문항만 JSON 배열로. 다른 텍스트 금지:
[{{"index":0,"data":{{...수정된 data 전체...}}}}]"""
