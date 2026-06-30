"""[3.Service] 핵심 비즈니스 로직 + LLM 연동.

- generate: 기존 데모(주제 → 자유 텍스트).
- generate_curriculum: 적응형 라우팅 + JIT 브릿지 생성.
    진단 점수로 구성(메인100% / 선수+메인)을 결정하고,
    정답을 떠먹이지 않는 인출(Retrieval) 블록으로 생성한다.
"""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.learning.repository import LearningRepository
from app.features.learning.schemas import (
    CURRICULUM_ADAPTER,
    CurriculumRequest,
    CurriculumResponse,
    GenerateRequest,
    GenerateResponse,
)
from app.features.learning.models import Curriculum
from app.features.materials.models import Concept

_CURRICULUM_SYSTEM = (
    "너는 교과서형 이론 설명 + 인출(retrieval) 연습을 결합한 학습자료 생성기다. "
    "각 챕터마다 이론을 먼저 충분히 설명하고, 그다음 인출 문제로 확인하게 한다. "
    "출력은 지정한 JSON 스키마만 따른다."
)


def _curriculum_prompt(
    concept: Concept,
    prereqs: list[Concept],
    *,
    high: bool,
    prereq_ratio: float,
    main_ratio: float,
) -> str:
    if high:
        composition = (
            "이미 충분히 아는 학습자다. 메인 개념에만 100% 집중하라. "
            "선수개념 복습·사후 요약·심화·게이미피케이션 등 사족을 일절 넣지 말고 밀도 높게."
        )
        prereq_section = ""
    else:
        names = ", ".join(p.name for p in prereqs) or "(직접 선수개념 없음)"
        composition = (
            f"아직 약한 학습자다. 분량의 약 {int(prereq_ratio * 100)}%는 약한 "
            f"선수개념({names}) 브릿지를 쉬운 말로 풀고, 약 {int(main_ratio * 100)}%는 "
            "메인 개념으로 자연스럽게 이어라."
        )
        prereq_section = "선수개념:\n" + "\n".join(
            f"- {p.name}: {p.description}" for p in prereqs
        )

    return (
        f"개념 '{concept.name}'에 대한 JIT 학습 자료를 한국어로 생성하라.\n"
        f"개념 설명: {concept.description}\n"
        f"{prereq_section}\n\n"
        f"구성: {composition}\n\n"
        "설계 원칙(필수):\n"
        "- 교과서 챕터처럼 '이론 설명 → 인출 확인' 순서로 blocks 배열을 구성한다.\n"
        "- blocks kind:\n"
        '  - "chapter": {"kind":"chapter","title":str,"text":str}\n'
        "     → 챕터 제목 + 2~4문단 이론 설명(정의, 원리, 예시, 주의점). "
        "학습자가 개념을 처음 읽고 이해할 수 있게 충분히 서술.\n"
        '  - "cloze": {"kind":"cloze","text":"... ____ ...","answer":str}\n'
        "     → 해당 챕터 직후 핵심 용어 빈칸 인출 1~2개\n"
        '  - "inverse": {"kind":"inverse","prompt":str,"answer":str}\n'
        "     → 해당 챕터 직후 원리/이유 역질문 1개\n"
        '  - "prose": {"kind":"prose","heading":str,"text":str} (보조 맥락용, 최소 사용)\n\n'
        "구조 예시 (bridge 모드):\n"
        "  [chapter: 선수개념A 이론] → [cloze] → [chapter: 선수개념B 이론] → [cloze] "
        "→ [chapter: 메인 개념 이론] → [cloze] → [inverse]\n"
        "구조 예시 (focused 모드):\n"
        "  [chapter: 메인 개념 이론 1] → [cloze] → [chapter: 심화 이론 2] → [inverse]\n\n"
        'JSON: {"blocks":[ ... ]}'
    )


class LearningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = LearningRepository(db)

    async def generate(self, req: GenerateRequest) -> GenerateResponse:
        content = await solar_client.generate(f"다음 주제로 학습 항목을 만들어줘: {req.topic}")
        self.repo.add(content=content)
        return GenerateResponse(content=content)

    # ── 적응형 라우팅 / JIT ───────────────────────────────────
    async def generate_curriculum(self, req: CurriculumRequest) -> CurriculumResponse:
        concept = self.repo.get_concept(req.concept_id)
        if concept is None:
            raise HTTPException(status_code=404, detail="개념을 찾을 수 없습니다.")

        # 존재하지 않는 세션 ID(예: DB 리셋/stale 상태)는 우아하게 무시 → 세션 없이 생성.
        session_id = req.session_id
        if session_id is not None and not self.repo.session_exists(session_id):
            session_id = None

        score = self._score(session_id, concept.id)
        high = score >= settings.LEARNING_HIGH_THRESHOLD

        if high:
            mode, prereq_ratio, main_ratio = "focused", 0.0, 1.0
            used_prereqs: list[Concept] = []
        else:
            mode = "bridge"
            prereq_ratio = settings.LEARNING_PREREQ_RATIO
            main_ratio = settings.LEARNING_MAIN_RATIO
            used_prereqs = self._weak_prerequisites(session_id, concept.id)

        if not req.force_regenerate:
            cached = self.repo.get_latest_curriculum(
                concept_id=concept.id, session_id=session_id
            )
            if cached is not None:
                return self._response(cached, concept, [p.name for p in used_prereqs])

        raw = await solar_client.generate_json(
            _curriculum_prompt(
                concept,
                used_prereqs,
                high=high,
                prereq_ratio=prereq_ratio,
                main_ratio=main_ratio,
            ),
            system=_CURRICULUM_SYSTEM,
        )
        try:
            draft = CURRICULUM_ADAPTER.validate_python(raw)
        except ValidationError as exc:
            raise HTTPException(
                status_code=502, detail=f"커리큘럼 JSON 검증 실패: {exc}"
            ) from exc

        curriculum = self.repo.save_curriculum(
            concept_id=concept.id,
            session_id=session_id,
            score=score,
            mode=mode,
            prerequisite_ratio=prereq_ratio,
            main_ratio=main_ratio,
            blocks=[b.model_dump() for b in draft.blocks],
        )
        return self._response(curriculum, concept, [p.name for p in used_prereqs])

    # ── 내부 ──────────────────────────────────────────────────
    def _score(self, session_id: int | None, concept_id: int) -> float:
        """진단 숙련도를 점수로. 세션/숙련도가 없으면 보수적으로 사전값(낮음)."""
        if session_id is None:
            return settings.BKT_P_INIT
        mastery = self.repo.get_mastery(session_id=session_id, concept_id=concept_id)
        return mastery.p_known if mastery is not None else settings.BKT_P_INIT

    def _weak_prerequisites(
        self, session_id: int | None, concept_id: int
    ) -> list[Concept]:
        """직접 선수개념 중 아직 약한 것만. 세션 없으면 직접 선수 전체."""
        direct = self.repo.get_direct_prerequisites(concept_id)
        if session_id is None or not direct:
            return direct
        weak = [
            p
            for p in direct
            if (m := self.repo.get_mastery(session_id=session_id, concept_id=p.id))
            is None
            or m.p_known < settings.LEARNING_HIGH_THRESHOLD
        ]
        return weak or direct

    @staticmethod
    def _response(
        curriculum: Curriculum, concept: Concept, prerequisite_names: list[str]
    ) -> CurriculumResponse:
        return CurriculumResponse(
            id=curriculum.id,
            concept_id=curriculum.concept_id,
            concept_name=concept.name,
            score=round(curriculum.score, 4),
            mode=curriculum.mode,
            prerequisite_ratio=curriculum.prerequisite_ratio,
            main_ratio=curriculum.main_ratio,
            prerequisite_names=prerequisite_names,
            blocks=list(curriculum.blocks),
        )
