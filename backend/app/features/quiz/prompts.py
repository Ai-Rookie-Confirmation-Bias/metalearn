"""⑤⑥ 프롬프트 빌더 — 고정 틀 + 슬롯 (docs/QUIZ.md §2-⑤).

틀은 과목 내용을 언급하지 않는다. 과목 지식은 전부 슬롯(파싱 결과)에서 온다.
"""
import json

from app.features.quiz.schemas import ChunkWorkOrder, GeneratedItem, ParsedChunk

_TYPE_GUIDE = {
    "mcq": '객관식. data={"question":str,"options":[str,정확히 4개],"answerIndex":int,'
    '"explanation":str,"wrongExplanations":{"선지번호":str}}\n'
    "  · 선지는 반드시 4개. 오답 선지마다 왜 아닌지 필수\n"
    '  · 발문 끝은 "~은?" 또는 "~이 아닌 것은?"',
    "cloze": '빈칸. data={"segments":[{"kind":"text","text":str}|{"kind":"blank","answer":str,"aliases":[str]}]}\n'
    "  · 빈칸은 1개, 많아도 2개. 3개 이상 뚫지 마라\n"
    "  · answer는 근거 문장에 있는 표기를 글자 그대로 복사 (원문자 ①, 기호 →, 수식 문자를 바꾸지 마라)\n"
    "  · answer는 용어·고유명사 같은 낱말 단위로. 구절이나 문장을 통째로 빈칸으로 만들지 마라\n"
    "  · 빈칸을 채운 문장이 자연스러운 한국어 문장이어야 한다\n"
    "  · 순서가 바뀌어도 맞는 나열 항목은 빈칸으로 만들지 마라 (채점이 순서를 따진다)",
    "shortAnswer": '단답. data={"prompt":str,"accepted":[str],"explanation":str}\n'
    "  · 정답은 용어·명사구여야 한다 (공백 포함 25자 이내). 문장 전체를 정답으로 요구하지 마라\n"
    '  · "~의 정의를 쓰시오"가 아니라, 설명을 주고 그 용어를 묻는 방향으로 출제하라\n'
    "  · accepted에 정답 표기 변형(약어·한/영·괄호 유무) 포함",
    "trueFalse": '참거짓. data={"statement":str,"answer":bool,"explanation":str}\n'
    "  · statement는 한 가지 사실만 진술한다 (두 사실을 묶으면 판정이 모호해진다)",
}


def build_generation_prompt(
    order: ChunkWorkOrder,
    chunk: ParsedChunk,
    stem_patterns: list[str] | None = None,
) -> str:
    """조각 하나에 대한 생성 프롬프트. stem_patterns = 기출 발문 스타일 (있을 때만)."""
    sentences = "\n".join(
        f"s{i}: {chunk.raw_text[a.start:a.end].strip()}"
        for i, a in enumerate(chunk.sentences)
    )
    directives = []
    for plan in order.concept_plans:
        types = ", ".join(plan.types)
        sids = ", ".join(f"s{i}" for i in plan.evidence_sentence_ids[:8])
        directives.append(f"- {plan.name} ({plan.form}) → {types} 각 1문항 · 근거 후보: {sids}")

    style = ""
    if stem_patterns:
        joined = "\n".join(f'  - "{p}"' for p in stem_patterns[:5])
        style = f"\n[발문 스타일] 아래는 이 시험의 실제 발문 예시다. 표현 방식만 따라 하고 내용은 참고하지 마라:\n{joined}\n"

    type_guides = "\n".join(
        f"- {t}: {g}"
        for t, g in _TYPE_GUIDE.items()
        if any(t in p.types for p in order.concept_plans)
    )

    return f"""너는 시험 출제자다. 아래 원문만을 근거로 문제를 만들어라.

[원문 문장 목록]
{sentences}

[출제 지시] 개념마다 지정된 유형으로 생성하라:
{chr(10).join(directives)}
{style}
[유형별 data 스키마]
{type_guides}

[규칙]
1. 모든 문항에 근거 문장 번호(sN)를 evidence로 반드시 기록하라. 근거 없는 문항은 폐기된다.
2. 원문에 없는 사실을 지어내지 마라. 정답의 근거는 반드시 evidence 문장 안에 있어야 한다.
3. 정답은 문자열 완전일치로 자동 채점된다. 정답이 한 문장만큼 길거나, 사람마다 다르게 쓸 수
   있거나, 답의 순서가 바뀔 수 있으면 그런 문항은 아예 만들지 마라.
4. 원문 표기를 글자 그대로 옮겨라. 원문자(①)를 "1."로, 화살표(→)를 "->"로, 수식 문자를
   일반 알파벳으로 바꾸면 근거 대조에 실패해 폐기된다.
   단, 정답이 특수문자·수식처럼 키보드로 그대로 치기 어려운 표기라면 aliases에 일반
   키보드로 입력 가능한 표기를 반드시 함께 넣어라 (예: "𝑎 + 4𝑐 + 𝑏" → "a + 4c + b").
5. 객관식 오답 선지는 그럴듯하되, 원문 어디에서도 정답이 되면 안 된다.
6. 발문은 시험 문체로 써라: "~은?", "~이 아닌 것은?", "~을 쓰시오".
   "~인가요?", "~일까요?", "~합니다" 같은 구어체·경어체 금지.
7. 빈칸 문항은 빈칸 1개가 기본이다. 원문이 여러 단계로 된 절차라도 전부 비우지 말고,
   1~2곳만 비우고 나머지 단계는 지문에 그대로 보여줘라.
   비우는 대상은 의미를 담은 용어여야 한다. 번호(①), 기호(▶), 조사처럼 그 자리를
   못 맞출 사람이 없는 것은 빈칸으로 만들지 마라.
8. 발문·해설은 학습자가 그대로 읽는 글이다. 문장 번호(s38 같은 표기)를 본문에 쓰지 마라.
   근거는 evidence 필드로만 남긴다.
9. 발문의 설명이 정답 하나만 가리키는지 확인하라. 같은 설명에 들어맞는 다른 용어가
   원문에 또 있으면 그 발문은 못 쓴다 — 그 용어만의 특징을 발문에 넣어라.
10. 인사말·광고·학습 조언처럼 시험 범위가 아닌 문장으로는 출제하지 마라.
11. 지정된 유형으로 위 조건을 만족하는 문항을 만들 수 없으면 그 문항은 건너뛰어라.
    억지로 만든 문항보다 문항 수가 적은 쪽이 낫다.
12. difficulty는 1(쉬움)~5(어려움).

[출력] JSON 배열만 출력하라. 다른 텍스트 금지:
[{{"type":"...","concept":"...","data":{{...}},"evidence":["s3","s4"],"difficulty":2}}]"""


def build_verification_prompt(
    items: list[GeneratedItem], chunk: ParsedChunk
) -> str:
    """문항 묶음(≤5개) 심판 프롬프트. 정답 유일성 + 근거 대조."""
    blocks = []
    for i, item in enumerate(items):
        evidence = " / ".join(
            chunk.raw_text[chunk.sentences[s].start : chunk.sentences[s].end].strip()
            for s in item.evidence_sentence_ids
            if 0 <= s < len(chunk.sentences)
        )
        blocks.append(
            f"[문항 {i}] ({item.type})\n"
            f"내용: {json.dumps(item.data, ensure_ascii=False)}\n"
            f"근거: {evidence}"
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

[출력] JSON 배열만 출력하라:
[{{"index":0,"pass":true,"reason":""}},{{"index":1,"pass":false,"reason":"오답 선지 '피드백'이 원문에서 참"}}]"""
