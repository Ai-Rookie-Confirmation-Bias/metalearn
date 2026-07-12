"""학습 목적(enrollment.purpose) → 학습 엔진 정책 프리셋.

위저드 STEP 3의 "왜 배우세요?"를 엔진 다이얼로 변환한다. 원칙:
  - 목적은 '강도'만 조절한다 — 내용 범위·난이도(§2.3 표준 고정)는 불변.
  - 게이트 로직을 분기하지 않는다. 정책은 전부 데이터(생성물 속성·상수)로
    표현하고, 기존 로직(「풀면 진행」·read-complete·복습 주입)이 따라온다.
    예: 취미의 게이트 완화 = tracked_retrieval=False 생성 →
        complete_section_by_reading의 기존 "tracked 0개면 열람 완료" 규칙이
        코드 수정 없이 발동.
  - 미설정(None)/미지 값 = 현행 동작 그대로(하위호환).

스타일 지시문(말투·예시)은 generator.purpose_directive_of가 담당하고,
여기는 문항 밀도·유형(retrieval_directive)과 엔진 상수만 다룬다.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PurposePolicy:
    # 생성 프롬프트에 붙는 인출 문항 밀도·유형 지시(빈 문자열 = 중립).
    retrieval_directive: str = ""
    # False면 인출 블록을 채점 대상에서 제외(tracked=False) — 퀴즈는 보너스가
    # 되고, 절은 '다 읽었어요'로 완료 가능(기존 read-complete 규칙).
    tracked_retrieval: bool = True
    # 챕터 경계 복습 섹션의 개념 수 상한. 0 = 복습 섹션을 넣지 않는다.
    review_cap: int = 5
    # SM-2 복습 간격 계수. <1 = 더 자주 돌아옴(시험), >1 = 느슨(교양).
    sm2_interval_factor: float = 1.0


_DEFAULT = PurposePolicy()

_POLICIES: dict[str, PurposePolicy] = {
    # 시험·자격증 — "많이 풀고, 자주 돌아온다". 오답 재큐는 기존 오답노트
    # 우선 복습 수집이 이미 수행하므로 cap·주기 강화로 충분.
    "exam": PurposePolicy(
        retrieval_directive=(
            "- [문항 구성: 시험 대비] 인출 문제를 넉넉히 배치하라(개념당 3~4개). "
            "mcq·cloze 중심으로 실제 시험과 같은 형식을 유지하고, mcq 선지에는 "
            "헷갈리기 쉬운 유사 개념을 포함해 구분 훈련이 되게 하라. 암기가 필요한 "
            "항목에는 니모닉·정리 표현 같은 암기 장치를 곁들여라."
        ),
        tracked_retrieval=True,
        review_cap=8,
        sm2_interval_factor=0.7,
    ),
    # 실무·커리어 — 암기보다 판단. 밀도는 표준, 유형만 적용형으로.
    "career": PurposePolicy(
        retrieval_directive=(
            "- [문항 구성: 실무 적용] 단순 암기형(용어 빈칸)은 최소화하고, 실무 "
            "상황을 가정한 적용·판단형 문제(시나리오 mcq, explainBack) 중심으로 "
            "구성하라."
        ),
        tracked_retrieval=True,
        review_cap=5,
        sm2_interval_factor=1.0,
    ),
    # 교양·흥미 — 다큐 보듯. 확인 문항 소수, 복습 느슨.
    "culture": PurposePolicy(
        retrieval_directive=(
            "- [문항 구성: 교양] 인출 문제는 핵심 아이디어를 잡았는지 확인하는 "
            "수준으로 1~2개만 배치하라. 세부 용어 암기를 요구하는 문항은 만들지 "
            "마라."
        ),
        tracked_retrieval=True,
        review_cap=3,
        sm2_interval_factor=1.5,
    ),
    # 취미 — 숙제 없는 앱. 퀴즈는 보너스(tracked 해제), 복습 주입 없음.
    "hobby": PurposePolicy(
        retrieval_directive=(
            "- [문항 구성: 취미] 부담 없는 가벼운 퀴즈 1개만 곁들여라. 시험처럼 "
            "느껴지는 문항은 만들지 마라."
        ),
        tracked_retrieval=False,
        review_cap=0,
        sm2_interval_factor=1.0,
    ),
}


def policy_of(purpose: str | None) -> PurposePolicy:
    """enrollment.purpose → 정책. 미설정/미지 값이면 현행 동작(기본 정책)."""
    return _POLICIES.get(purpose or "", _DEFAULT)
