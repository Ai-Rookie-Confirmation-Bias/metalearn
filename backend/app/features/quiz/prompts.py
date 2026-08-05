"""⑤⑥ 프롬프트 빌더 — 고정 틀 + 슬롯 (docs/QUIZ.md §2-⑤).

틀은 과목 내용을 언급하지 않는다. 과목 지식은 전부 슬롯(파싱 결과)에서 온다.
"""
import json

from app.features.quiz.schemas import ChunkWorkOrder, GeneratedItem, ParsedChunk

_TYPE_GUIDE = {
    "mcq": '객관식. data={"question":str,"options":[str,4개],"answerIndex":int,'
    '"explanation":str,"wrongExplanations":{"선지번호":str}} — 오답 선지마다 왜 아닌지 필수',
    "cloze": '빈칸. data={"segments":[{"kind":"text","text":str}|{"kind":"blank","answer":str,"aliases":[str]}]}'
    " — blank의 answer는 근거 문장에 실제로 등장하는 표현이어야 함",
    "shortAnswer": '단답. data={"prompt":str,"accepted":[str],"explanation":str}'
    " — accepted에 정답 표기 변형(약어·한/영) 포함",
    "trueFalse": '참거짓. data={"statement":str,"answer":bool,"explanation":str}',
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
3. 객관식 오답 선지는 그럴듯하되, 원문 어디에서도 정답이 되면 안 된다.
4. difficulty는 1(쉬움)~5(어려움).

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

각 문항에 대해:
- Q1. 정답이 근거 원문으로 뒷받침되는가?
- Q2. (객관식) 오답 선지 중 원문에서 사실상 참이 되는 것이 있는가? 있으면 불합격 (정답이 2개가 됨)
- Q3. 문항 표현에 모순·모호함이 없는가?

[출력] JSON 배열만 출력하라:
[{{"index":0,"pass":true,"reason":""}},{{"index":1,"pass":false,"reason":"오답 선지 '피드백'이 원문에서 참"}}]"""
