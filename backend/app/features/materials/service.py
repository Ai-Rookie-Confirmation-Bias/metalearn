"""[3.Service] Ingestion 파이프라인.

PDF → (Solar Document Parse) 마크다운 → (Solar JSON) 개념 트리 추출
   → 평탄화 → 개념별 임베딩 → 개념/선수지식 그래프 영속.

데이터는 전 구간 '개념(Concept)' 단위로 추적된다.
"""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.materials.repository import MaterialRepository
from app.features.materials.schemas import (
    ConceptNode,
    ConceptOut,
    ExtractionResult,
    MaterialDetail,
    MaterialSummary,
)

_EXTRACTION_SYSTEM = (
    "너는 학습 자료를 '개념(Concept)' 단위로 파편화하는 지식 그래프 추출기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다. 설명·사족·마크다운 펜스 금지."
)


def _extraction_prompt(markdown: str) -> str:
    return (
        "다음 학습 자료에서 타겟 개념과 그 '직접 선수지식'을 추출하라.\n"
        "규칙:\n"
        f"1. 트리 중첩 깊이는 최대 {settings.MAX_CONCEPT_DEPTH}단계까지만 (N-2 제한). "
        f"초과 깊이는 자동 삭제되므로 반드시 {settings.MAX_CONCEPT_DEPTH}단계 이내로 유지할 것.\n"
        "2. prerequisites 에는 해당 개념을 이해하기 위해 '직접' 선행돼야 하는 개념만.\n"
        "3. name 은 간결한 명사구, description 은 한국어 한 문장.\n"
        "4. 같은 개념은 한 번만 정의하고 중복 생성하지 말 것.\n\n"
        'JSON 형식: {"concepts":[{"name":str,"description":str,'
        '"prerequisites":[{ ...동일 구조... }]}]}\n\n'
        "=== 자료(markdown) ===\n"
        f"{markdown}"
    )


class MaterialService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MaterialRepository(db)

    async def ingest(self, *, file_bytes: bytes, filename: str, title: str | None) -> MaterialDetail:
        material = self.repo.create_material(
            title=title or filename, filename=filename
        )
        self.db.commit()

        try:
            markdown = await solar_client.parse_document(file_bytes, filename)
            if not markdown.strip():
                raise ValueError("Document Parse 결과가 비어 있습니다.")
            material.markdown = markdown
            material.status = "extracting"
            self.db.commit()

            extraction = await self._extract_concepts(markdown)
            await self._persist_graph(material.id, extraction)

            material.status = "ready"
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 — 실패 사유를 자료에 기록 후 재전파
            self.db.rollback()
            material.status = "failed"
            material.error = str(exc)[:2000]
            self.db.commit()
            raise HTTPException(
                status_code=502, detail=f"섭취 실패(material={material.id}): {exc}"
            ) from exc

        return self.get_detail(material.id)

    async def _extract_concepts(self, markdown: str) -> ExtractionResult:
        raw = await solar_client.generate_json(
            _extraction_prompt(markdown), system=_EXTRACTION_SYSTEM
        )
        try:
            return ExtractionResult.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(
                f"추출 JSON이 스키마 검증을 통과하지 못했습니다: {exc}"
            ) from exc

    async def _persist_graph(self, material_id: int, extraction: ExtractionResult) -> None:
        """개념 트리를 평탄화해 노드/엣지로 저장. 이름 기준 중복 제거."""
        created: dict[str, int] = {}
        edges: set[tuple[int, int]] = set()

        async def upsert(node: ConceptNode, depth: int) -> int:
            cid = created.get(node.name)
            if cid is None:
                embedding = await solar_client.embed(f"{node.name}\n{node.description}")
                concept = self.repo.add_concept(
                    material_id=material_id,
                    name=node.name,
                    description=node.description,
                    depth=depth,
                    embedding=embedding,
                )
                created[node.name] = concept.id
                cid = concept.id

            for child in node.prerequisites:
                child_id = await upsert(child, depth + 1)
                edge = (cid, child_id)
                if edge not in edges and cid != child_id:
                    self.repo.add_prerequisite(
                        concept_id=cid, prerequisite_concept_id=child_id
                    )
                    edges.add(edge)
            return cid

        for root in extraction.concepts:
            await upsert(root, 0)

    # ── 조회 ──────────────────────────────────────────────────
    def get_detail(self, material_id: int) -> MaterialDetail:
        material = self.repo.get_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="자료를 찾을 수 없습니다.")

        concepts = [
            ConceptOut(
                id=c.id,
                name=c.name,
                description=c.description,
                depth=c.depth,
                prerequisite_ids=[e.prerequisite_concept_id for e in c.prerequisite_edges],
            )
            for c in sorted(material.concepts, key=lambda c: (c.depth, c.id))
        ]
        return MaterialDetail(
            id=material.id,
            title=material.title,
            filename=material.filename,
            status=material.status,
            created_at=material.created_at,
            concept_count=len(concepts),
            concepts=concepts,
        )

    def list_materials(self) -> list[MaterialSummary]:
        return [MaterialSummary.model_validate(m) for m in self.repo.list_materials()]
