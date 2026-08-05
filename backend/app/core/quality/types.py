"""검증기 입출력 타입 — 호출자(quiz/learning)가 이 모양으로 넘기고 돌려받는다."""
from pydantic import BaseModel, Field


class CandidateItem(BaseModel):
    """검증 대상 문항 하나. 어디 소속인지(블록/문제은행) 모른다."""

    type: str  # mcq | cloze | shortAnswer | trueFalse | (학습 쪽 확장 유형 허용)
    data: dict
    evidence_text: str  # 이 문항의 근거 원문 (호출자가 잘라서 제공)


class ItemVerdict(BaseModel):
    """문항 하나의 검증 결과. 입력과 같은 순서로 반환된다."""

    ok: bool
    stage: str = ""  # 탈락 단계: mechanical | judge | solve | revise
    reason: str = ""
    revised: bool = False  # 수정 루프를 거쳐 살아난 문항
    item: CandidateItem  # 최종 문항 (polish·수정 반영본)


class QualityConfig(BaseModel):
    batch_size: int = 5  # 심판·풀이자·수정 콜의 문항 묶음 크기
    enable_solve: bool = True  # 풀이 왕복 검증 (정답 유일성 실험)
    enable_revise: bool = True  # 불합격 문항 사유 첨부 수정 1회
    # 풀이 왕복을 적용할 유형 — 정답 키가 있는 유형만 (explainBack 등 rubric형 제외)
    solve_types: set[str] = Field(
        default_factory=lambda: {"mcq", "cloze", "shortAnswer", "trueFalse"}
    )
