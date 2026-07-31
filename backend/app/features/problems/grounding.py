"""[순수로직] 근거 대조 — source_evidence가 원문에 실재하는지 판정.

DB·LLM 비의존. 문제 생성 에이전트의 1차 방어선이며,
검증 에이전트 v1(원문 대조)의 품질 상한을 결정한다.

판정 원칙 — **정규화 후 정확 일치만 통과시킨다.**
  마크다운 장식(불릿·표 파이프·굵게)과 줄바꿈 차이는 정규화로 흡수하되,
  글자가 달라지면 폐기한다. 유사도/토큰오버랩 같은 퍼지 판정은 쓰지 않는다:
  원문의 "내부 단편화"를 "외부 단편화"로 한 단어만 바꾼 거짓 근거가
  유사도 0.98·토큰오버랩 100%로 통과해 버리기 때문이다(교육 콘텐츠에서
  가장 위험한 오류 유형). 프롬프트가 "그대로 인용"을 지시하므로
  불일치 = LLM이 지시를 어긴 것 → 폐기 후 재생성이 맞다(fail-closed).

책임 경계: 여기서 보는 것은 "원문을 실제로 인용했는가"까지다.
정답이 옳은지·보기가 타당한지 같은 의미 판정은 검증 에이전트 몫.
  └ 알려진 한계: 두 곳을 나눠 인용한 근거는 조각별로만 실재를 확인하므로,
    조각끼리 잘못 짝지은 주장(예: LRU 항목에 LFU 설명을 붙임)은 여기서
    걸리지 않는다. 짝짓기의 타당성은 의미 판정이라 검증 에이전트가 본다.
    단 한 문장으로 짜깁기한 창작은 조각이 1개라 이 단계에서 폐기된다.
"""
import re

# 인용이 너무 짧으면 근거 구실을 못 한다(예: "페이징" 한 단어).
MIN_EVIDENCE_CHARS = 12
# 문장 조각 중 이보다 짧은 파편은 판정 대상에서 제외(구두점 잔재 등).
MIN_SEGMENT_CHARS = 8

# 줄머리 목록 기호(불릿·번호) — 인용 시 흔히 탈락한다.
_BULLET_RE = re.compile(r"^\s*(?:[-*•▶▪·※]+|\d+[.)])\s*")
# 인라인 마크다운 장식 — 의미에 영향 없음.
_DECOR_RE = re.compile(r"[*_`#>]+")
# 표 구분행(`| --- | :--- |`)은 내용이 아니다.
_TABLE_RULE_RE = re.compile(r"^[\s|:-]+$")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+")


def normalize(text: str) -> str:
    """마크다운 장식·줄바꿈 차이를 걷어내고 한 줄로 정규화한다.

    파싱 에이전트 출력이 표 마크다운(`| 전략 | 종류 | 설명 |`)이라
    이 정규화 없이는 정상 인용도 완전일치에 실패한다.
    """
    lines: list[str] = []
    for line in text.splitlines():
        if _TABLE_RULE_RE.match(line):
            continue
        line = _BULLET_RE.sub("", line)
        line = line.replace("|", " ")  # 표 셀 구분자
        line = _DECOR_RE.sub("", line)
        lines.append(line)
    return " ".join(" ".join(lines).split())


def _segments(evidence: str) -> list[str]:
    """근거를 대조 단위로 쪼갠다 — 줄·표 셀·문장 경계를 모두 쓴다.

    마침표에만 의존하면 안 된다. 표 마크다운의 셀은 마침표로 끝나지 않는 경우가
    대부분이라("… 페이지를 교체"), 원문 두 곳을 이어 인용한 근거가 한 덩어리로
    남아 통째 부분일치에 실패한 뒤 그대로 폐기된다. 비교·종합(L3) 문항은
    본질적으로 두 곳을 인용하므로 이 경로가 죽으면 L3가 전멸한다(실측 L3 0/2).

    ※ 정규화 **전의** 원본을 받는다 — normalize()가 줄바꿈·파이프를 공백으로
      바꿔 경계 정보를 지우므로, 먼저 쪼갠 뒤 조각별로 정규화한다.
    """
    out: list[str] = []
    for line in evidence.splitlines():  # ① 줄 경계
        for cell in line.split("|"):  # ② 표 셀 경계
            for sentence in _SENT_SPLIT_RE.split(cell):  # ③ 문장 경계
                seg = normalize(sentence)
                if len(seg) >= MIN_SEGMENT_CHARS:
                    out.append(seg)
    return out


def items_not_in_source(items: list[str], source: str) -> list[str]:
    """원문에 실재하지 않는 항목만 골라 돌려준다(빈 목록이면 전부 실재).

    보기(option)처럼 짧은 문구용이라 MIN_EVIDENCE_CHARS를 적용하지 않는다.

    왜 필요한가(실측): 순서 배열 문항이 근거로는 원문 한 줄을 인용하면서
    보기에는 원문에 없는 단계("페이지 참조·교체 전략 선택·페이지 적재")를
    지어내 게이트를 통과했다. source_evidence만 대조하면 **보기의 창작**은
    잡히지 않는다 — 학습자가 실제로 읽는 것은 보기인데도.
    """
    norm_source = normalize(source)
    return [i for i in items if normalize(i) and normalize(i) not in norm_source]


def citation_spans(evidence: str, source: str) -> int:
    """근거가 원문의 **서로 다른 몇 곳**을 인용했는지 센다.

    레벨 판정의 입력이다. 한 곳을 통째로 인용했으면 1, 떨어진 두 곳을 이어
    인용했으면 2 이상. 비교·종합(L3)은 본질적으로 여러 곳을 필요로 하므로,
    이 수가 1이면 그 문항이 정말 L3인지 의심할 근거가 된다.

    근거가 원문에 실재한다는 전제(evidence_in_source 통과)에서 호출한다.
    """
    norm_evidence, norm_source = normalize(evidence), normalize(source)
    if not norm_evidence or not norm_source:
        return 0
    if norm_evidence in norm_source:
        return 1
    segments = _segments(evidence)
    return sum(1 for seg in segments if seg in norm_source)


def evidence_in_source(evidence: str, source: str) -> bool:
    """근거 문구가 원문에 실재하면 True.

    1) 정규화 후 통째로 부분일치하면 통과(정상 인용 — 인접한 여러 줄 인용 포함).
    2) 아니면 문장 조각으로 쪼개 **모든 조각이 각각 원문에 정확히 존재**해야 통과.
       (원문 서로 다른 위치의 문장을 이어 인용한 경우를 살리기 위함)
       조각 하나라도 원문에 없으면 창작이 섞인 것으로 보고 폐기한다.
    """
    if not evidence or not source:
        return False

    norm_evidence = normalize(evidence)
    norm_source = normalize(source)
    if len(norm_evidence) < MIN_EVIDENCE_CHARS:
        return False

    if norm_evidence in norm_source:
        return True

    segments = _segments(evidence)
    # 조각이 하나뿐이면 위 부분일치에서 이미 걸렀어야 한다(중복 판정 방지).
    # → 흩어진 단어를 짜깁기한 한 문장짜리 창작은 여기서 폐기된다.
    if len(segments) < 2:
        return False

    return all(seg in norm_source for seg in segments)
