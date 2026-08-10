"""⑤⑥ 프롬프트 빌더 — 고정 틀 + 슬롯 (docs/QUIZ.md §2-⑤).

틀은 과목 내용을 언급하지 않는다. 과목 지식은 전부 슬롯(파싱 결과)에서 온다.
"""
from app.features.quiz.schemas import ChunkWorkOrder, ParsedChunk

_TYPE_GUIDE = {
    "mcq": '객관식. data={"question":str,"options":[str,정확히 4개],"answerIndex":int,'
    '"explanation":str,"wrongExplanations":{"선지번호":str},'
    '"distractorPool":[{"text":str,"why":str}]}\n'
    "  · 선지는 반드시 4개. 오답 선지마다 왜 아닌지 필수\n"
    "  · distractorPool에 선지로 안 쓴 추가 오답 후보 3~4개를 why(왜 오답인지)와 함께 넣어라\n"
    "    — 시스템이 전체 후보 중에서 최선의 오답 3개를 고른다 (과생성 후 선별)\n"
    '  · 발문 끝은 "~은?" 또는 "~이 아닌 것은?"',
    "cloze": '빈칸. data={"sentence":"sN","answer":str,"aliases":[str]}\n'
    "  · sentence: 빈칸을 뚫을 근거 문장 번호 **하나** (evidence 후보 중에서)\n"
    "  · answer: 그 문장 안에 **글자 그대로** 존재하는 핵심 용어 (공백 포함 15자 이내 낱말).\n"
    "    번호(①)·기호(→)·조사 같은 무의미한 조각은 안 된다\n"
    "  · 지문은 시스템이 그 문장으로 자동 조립한다 — segments를 직접 만들지 마라\n"
    "  · aliases: 정답 표기 변형 (약어·한/영 등)",
    "shortAnswer": '단답. data={"prompt":str,"accepted":[str],"explanation":str}\n'
    "  · 정답은 용어·명사구여야 한다 (공백 포함 25자 이내). 문장 전체를 정답으로 요구하지 마라\n"
    '  · "~의 정의를 쓰시오"가 아니라, 설명을 주고 그 용어를 묻는 방향으로 출제하라\n'
    "  · accepted는 **최소 2개**: 한글 용어면 영문 표기를, 영문 용어면 한글 표기를\n"
    "    반드시 함께 넣어라 (채점이 표기 대조라, 없으면 맞은 답이 오답 처리된다)",
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

[계약 — 어기면 그 문항은 자동 폐기된다]
1. 근거: 모든 문항의 정답은 evidence 문장만으로 입증돼야 한다. 원문에 없는 사실 금지.
   evidence는 최상위 필드다 (data 안에 넣지 마라).
2. 채점: 정답은 문자열 완전일치로 자동 채점된다. 정답은 용어·명사구(25자 이내)여야
   하고, 사람마다 다르게 쓸 수 있는 서술·문장은 정답이 될 수 없다.
   표기 변형(약어·한/영·괄호 유무)은 accepted/aliases에 넣어라.
3. 표기: 원문 표기를 글자 그대로(①, →, 수식 문자). 키보드로 치기 어려운 표기가
   정답이면 입력 가능한 표기를 별칭에 병기하라 (예: "𝑎+4𝑐+𝑏" → "a+4c+b").
4. 문체: 발문·해설·선지·statement 전부 시험 문체 문어체 평서형("~이다", "~은?").
   "~입니다", "~해요", "~인가요?" 같은 경어체·구어체 금지.
5. 문장 번호(sN)는 evidence·sentence 필드 전용이다. 발문·해설·선지 텍스트에
   "s26에 따르면", "(s51)" 같은 표기를 쓰지 마라.
6. 유일성: 발문의 설명에 들어맞는 답이 원문에 하나뿐이어야 한다. 객관식 오답
   선지는 원문 어디에서도 정답이 되면 안 된다.
7. 인사말·학습 조언 등 시험 범위 밖 문장으로 출제하지 마라. 조건을 만족하는 문항을
   만들 수 없으면 건너뛰어라 — 억지 문항보다 적은 문항이 낫다. difficulty는 1~5.

[모범 예시 — **형식만** 따라 하라. 예시의 내용·개념을 출력에 복사하면 안 된다]
{{"items":[
{{"type":"shortAnswer","concept":"HTTP","data":{{"prompt":"요청-응답 구조로 웹 자원을 주고받는 프로토콜은 무엇인가?","accepted":["HTTP","HyperText Transfer Protocol","하이퍼텍스트 전송 프로토콜"],"explanation":"HTTP는 클라이언트의 요청에 서버가 응답하는 구조의 웹 프로토콜이다."}},"evidence":["s2"],"difficulty":2}},
{{"type":"cloze","concept":"라우터","data":{{"sentence":"s5","answer":"라우터","aliases":["router"]}},"evidence":["s5"],"difficulty":1}}
]}}

[출력] 위 예시와 같은 JSON 객체 하나만 출력하라. 다른 텍스트 금지. 문항은 items 배열에 전부 담는다."""


# 심판·풀이자·수정 프롬프트는 core/quality/prompts.py로 이동 —
# 검증은 기능(quiz/learning)에 묶이지 않는 공통 모듈이 담당한다.
