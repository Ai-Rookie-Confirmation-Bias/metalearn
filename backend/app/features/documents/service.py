"""[3.Service] Ingestion: users → documents → courses → concepts."""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.auth.repository import AuthRepository
from app.features.diagnostic.repository import DiagnosticRepository
from app.features.documents.repository import DocumentRepository
from app.features.documents.schemas import (
    ConceptNode,
    ConceptOut,
    CourseDetail,
    CourseSummary,
    ExtractionResult,
)

_EXTRACTION_SYSTEM = (
    "너는 학습 자료를 '개념(Concept)' 단위로 파편화하는 지식 그래프 추출기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다. 설명·사족·마크다운 펜스 금지."
)


def _extraction_prompt(raw_text: str) -> str:
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
        "=== 자료 ===\n"
        f"{raw_text}"
    )


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DocumentRepository(db)
        self.auth_repo = AuthRepository(db)
        self.diag_repo = DiagnosticRepository(db)

    async def ingest(self, *, file_bytes: bytes, filename: str, title: str | None) -> CourseDetail:
        user = self.auth_repo.get_default_user()
        document = self.repo.create_document(user_id=user.id, filename=filename)
        self.db.commit()

        course: object | None = None
        try:
            parsed = await solar_client.parse_document(file_bytes, filename)
            if not parsed.strip():
                raise ValueError("Document Parse 결과가 비어 있습니다.")
            document.raw_text = parsed
            self.db.commit()

            course = self.repo.create_course(
                document_id=document.id,
                user_id=user.id,
                title=title or filename,
            )
            self.diag_repo.ensure_enrollment(user_id=user.id, course_id=course.id)
            self.db.commit()

            extraction = await self._extract_concepts(parsed)
            await self._persist_graph(course.id, extraction)

            document.status = "ready"
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            document.status = "failed"
            document.error = str(exc)[:2000]
            self.db.commit()
            raise HTTPException(
                status_code=502,
                detail=f"섭취 실패(document={document.id}): {exc}",
            ) from exc

        assert course is not None
        return self.get_course_detail(course.id)

    async def _extract_concepts(self, raw_text: str) -> ExtractionResult:
        raw = await solar_client.generate_json(
            _extraction_prompt(raw_text), system=_EXTRACTION_SYSTEM
        )
        try:
            return ExtractionResult.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(
                f"추출 JSON이 스키마 검증을 통과하지 못했습니다: {exc}"
            ) from exc

    async def _persist_graph(self, course_id: int, extraction: ExtractionResult) -> None:
        created: dict[str, int] = {}
        edges: set[tuple[int, int]] = set()

        async def upsert(node: ConceptNode, depth_level: int) -> int:
            cid = created.get(node.name)
            if cid is None:
                embedding = await solar_client.embed(f"{node.name}\n{node.description}")
                concept = self.repo.add_concept(
                    course_id=course_id,
                    name=node.name,
                    description=node.description,
                    depth_level=depth_level,
                    embedding=embedding,
                )
                created[node.name] = concept.id
                cid = concept.id

            for child in node.prerequisites:
                child_id = await upsert(child, depth_level + 1)
                edge = (cid, child_id)
                if edge not in edges and cid != child_id:
                    self.repo.add_edge(from_concept_id=cid, to_concept_id=child_id)
                    edges.add(edge)
            return cid

        for root in extraction.concepts:
            await upsert(root, 0)

    def get_course_detail(self, course_id: int) -> CourseDetail:
        course = self.repo.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")

        concepts = [
            ConceptOut(
                id=c.id,
                name=c.name,
                description=c.description,
                depth_level=c.depth_level,
                prerequisite_ids=[e.to_concept_id for e in c.prerequisite_edges],
            )
            for c in sorted(course.concepts, key=lambda c: (c.depth_level, c.id))
        ]
        doc = course.document
        return CourseDetail(
            id=course.id,
            document_id=course.document_id,
            title=course.title,
            filename=doc.filename,
            status=doc.status,
            created_at=course.created_at,
            concept_count=len(concepts),
            concepts=concepts,
        )

    def list_courses(self) -> list[CourseSummary]:
        return [
            CourseSummary(
                id=c.id,
                document_id=c.document_id,
                title=c.title,
                filename=c.document.filename,
                status=c.document.status,
                created_at=c.created_at,
            )
            for c in self.repo.list_courses()
        ]
