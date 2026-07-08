"""[3.Service] 씨앗 조립 — 계약(docs/ii.md) 산출물 생성 (ISSUE-017, ISSUE-004).

build(course_id):
1. 커리큘럼 트리 — 정제 스캔의 파트를 chapters로, 섹션 대표 개념(depth 0,
   book)을 sections로. order_index는 10/20/30 간격 (계약 규약).
2. concepts.key — 영문 슬러그 배치 생성 (LLM), 코스 내 유니크 보장.
3. enrollment 확정 — floor/ceiling/floor_found/purpose (계약: 진단 완료 시점).
4. 시드 JSON 반환 — mastery 초기값(mastered/todo/locked + strength)을 계약
   포맷으로. 사용자 단위 concept_mastery 테이블 기록은 UUID 이관 시점에.
"""
import logging
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.auth.repository import AuthRepository
from app.features.curriculum.models import Chapter, Section
from app.features.diagnostic.models import DiagnosticSession
from app.features.learning.models import ConceptMastery, Enrollment
from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, Course

_log = logging.getLogger("uvicorn.error")

_SLUG_BATCH = 80
_SLUG_SYSTEM = (
    "너는 개념 이름을 영문 슬러그로 변환하는 도구다. "
    "출력은 지정한 JSON 스키마만 따른다."
)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _slug_prompt(items: list[tuple[int, str]]) -> str:
    # UUID 포팅 주: LLM에 UUID를 에코시키면 오타 위험이 크므로 배치 내
    # 로컬 번호(int)를 id로 쓰고, 응답을 배치 인덱스로 되매핑한다.
    lines = [
        "아래 개념들의 영문 슬러그를 만들어라. 규칙: 소문자 영단어를 '-'로 연결, "
        "간결한 의미 번역(음차 금지, 예: '이진 탐색 트리'→'binary-search-tree').\n",
        '출력 JSON: {"slugs": [{"id": int, "slug": str}, ...]} — 전 항목 필수.\n\n',
    ]
    for cid, name in items:
        lines.append(f"- id={cid}: {name}\n")
    return "".join(lines)


class SeedService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _course_documents(
        self, course_id: uuid.UUID, *, role: str | None = None
    ) -> list[Document]:
        """코스의 문서를 seq 순서로. role 지정 시 필터(primary=척추, supplementary=RAG).

        하위호환: course_id로 연결된 문서가 없으면(옛 단일 코스) course.document_id 폴백.
        """
        stmt = select(Document).where(Document.course_id == course_id)
        if role is not None:
            stmt = stmt.where(Document.role == role)
        docs = list(self.db.scalars(stmt.order_by(Document.seq, Document.created_at)))
        if not docs:
            course = self.db.get(Course, course_id)
            single = self.db.get(Document, course.document_id) if course else None
            docs = [single] if single is not None else []
        return docs

    async def build_tree(self, course_id: uuid.UUID) -> dict:
        """1단계(진단 무관): 슬러그 + 커리큘럼 트리 + external_refs. ingest 직후 호출.

        다중 PDF: primary 문서들을 seq 순서로 쌓아 하나의 트리를 만든다.
        """
        from app.features.seed.refs import collect_external_refs

        course = self.db.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
        documents = self._course_documents(course_id, role="primary")
        if not documents:
            raise HTTPException(status_code=404, detail="코스/문서를 찾을 수 없습니다.")

        concepts = list(
            self.db.scalars(select(Concept).where(Concept.course_id == course_id))
        )
        if not concepts:
            raise HTTPException(status_code=400, detail="개념이 없는 코스입니다.")

        await self._fill_keys(concepts)
        chapters, sections = self._build_tree(course_id, documents, concepts)
        refs_stats = await collect_external_refs(self.db, course_id)
        self.db.commit()

        return {
            "course_id": course_id,
            "document": {
                "profile": documents[0].profile,
                "concept_count": len(concepts),
                "document_count": len(documents),
            },
            "curriculum": {
                "chapters": len(chapters),
                "sections": len(sections),
                "gen_status": "pending",
            },
            "external_refs": refs_stats,
        }

    async def finalize_placement(
        self,
        course_id: uuid.UUID,
        purpose: str = "exam",
        floor_id: uuid.UUID | None = None,
        ceiling_id: uuid.UUID | None = None,
        diag_q_count: int | None = None,
    ) -> dict:
        """2단계(진단 완료 후): enrollment 확정 + mastery 시드 JSON.

        배치고사가 정밀 확정한 floor/ceiling을 넘기면 그대로 쓰고, 없으면
        mastery 신호에서 유도한다(구 진단 경로 하위호환).
        """
        course = self.db.get(Course, course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")
        documents = self._course_documents(course_id, role="primary")
        if not documents:
            raise HTTPException(status_code=404, detail="코스/문서를 찾을 수 없습니다.")
        concepts = list(
            self.db.scalars(select(Concept).where(Concept.course_id == course_id))
        )
        if not concepts:
            raise HTTPException(status_code=400, detail="개념이 없는 코스입니다.")

        mastery, derived_floor, derived_ceiling = self._mastery_seed(
            course_id, documents, concepts
        )
        floor_id = floor_id if floor_id is not None else derived_floor
        ceiling_id = ceiling_id if ceiling_id is not None else derived_ceiling
        self._finalize_enrollment(course_id, floor_id, ceiling_id, purpose, diag_q_count)
        self.db.commit()

        return {
            "course_id": course_id,
            "placement": {
                "floor_concept": floor_id,
                "ceiling_concept": ceiling_id,
                "purpose": purpose,
            },
            "mastery": mastery,
        }

    async def build(self, course_id: uuid.UUID, purpose: str = "exam") -> dict:
        """(하위호환) 1+2단계 한 번에 — 기존 /seed/{id}/build 엔드포인트용."""
        tree = await self.build_tree(course_id)
        placement = await self.finalize_placement(course_id, purpose)
        return {**tree, **placement}

    # ── ① key 슬러그 ────────────────────────────────────────────
    async def _fill_keys(self, concepts: list[Concept]) -> None:
        pending = [c for c in concepts if not c.key]
        if not pending:
            return
        seen: set[str] = {c.key for c in concepts if c.key}
        resolved: dict[uuid.UUID, str] = {}
        for i in range(0, len(pending), _SLUG_BATCH):
            batch = pending[i : i + _SLUG_BATCH]
            try:
                raw = await solar_client.generate_json(
                    # UUID 포팅: 프롬프트 id는 배치 로컬 번호 → 인덱스로 되매핑
                    _slug_prompt([(j, c.name) for j, c in enumerate(batch)]),
                    system=_SLUG_SYSTEM,
                )
                for row in raw.get("slugs") or []:
                    if (
                        isinstance(row, dict)
                        and isinstance(row.get("id"), int)
                        and 0 <= row["id"] < len(batch)
                    ):
                        slug = str(row.get("slug", "")).strip().lower()
                        if _SLUG_RE.match(slug):
                            resolved[batch[row["id"]].id] = slug[:100]
            except Exception as exc:  # noqa: BLE001 — 폴백 슬러그로 진행
                _log.warning("슬러그 배치 실패, 폴백 사용: %s", exc)
        for c in pending:
            slug = resolved.get(c.id) or f"concept-{c.id}"
            if slug in seen:
                # key는 String(128) — UUID(36자) 접미가 넘치지 않게 앞부분을 자름
                slug = f"{slug[:90]}-{c.id}"
            seen.add(slug)
            c.key = slug
        self.db.flush()
        _log.info("슬러그 생성: %d개 (LLM %d, 폴백 %d)",
                  len(pending), len(resolved), len(pending) - len(resolved))

    # ── ③ chapters/sections ────────────────────────────────────
    def _build_tree(
        self, course_id: uuid.UUID, documents: list[Document], concepts: list[Concept]
    ) -> tuple[list[Chapter], list[Section]]:
        """다중 PDF: primary 문서들을 seq 순서로 이어 하나의 트리로.

        각 문서의 parts를 챕터로 만들되 order_index를 문서 경계마다 누적 오프셋해
        [PDF1의 장들 → PDF2의 장들 → …] 순으로 쌓는다. 개념은 출처 청크가 속한
        문서의 챕터로 배정한다(문서 간 순서 = 사용자가 정한 업로드 순서).
        """
        # 재실행 대비: 기존 트리는 지우고 다시 만든다 (gen_status pending 전제)
        for old in self.db.scalars(select(Chapter).where(Chapter.course_id == course_id)):
            self.db.delete(old)
        self.db.flush()

        doc_ids = [d.id for d in documents]
        doc_seq = {d.id: i for i, d in enumerate(documents)}
        # 청크 메타(모든 문서): chunk_id -> (document_id, part_index, chunk_index)
        chunk_doc: dict[uuid.UUID, uuid.UUID] = {}
        chunk_part: dict[uuid.UUID, int] = {}
        chunk_order: dict[uuid.UUID, int] = {}
        for row in self.db.scalars(
            select(DocChunk).where(DocChunk.document_id.in_(doc_ids))
        ):
            chunk_doc[row.id] = row.document_id
            chunk_part[row.id] = row.part_index or 0
            chunk_order[row.id] = row.chunk_index

        # 챕터: 문서 순서대로, 문서마다 order_index 오프셋 누적
        chapters: list[Chapter] = []
        doc_chapters: dict[uuid.UUID, tuple[list[Chapter], bool]] = {}
        order_cursor = 0
        for d in documents:
            scan = (d.refined_elements or {}).get("scan") or {}
            part_titles = [p["title"] for p in scan.get("parts") or []]
            titles = part_titles or [d.filename]
            chs: list[Chapter] = []
            for title in titles:
                order_cursor += 10
                ch = Chapter(course_id=course_id, order_index=order_cursor, title=title[:200])
                self.db.add(ch)
                chapters.append(ch)
                chs.append(ch)
            doc_chapters[d.id] = (chs, bool(part_titles))
        self.db.flush()

        def concept_doc(c: Concept) -> uuid.UUID | None:
            return chunk_doc.get(c.source_chunk_id)

        def doc_order(c: Concept) -> tuple:
            did = concept_doc(c)
            return (
                doc_seq.get(did, 999),
                chunk_part.get(c.source_chunk_id, 0),
                chunk_order.get(c.source_chunk_id, -1),
                str(c.id),
            )

        reps = sorted(
            (c for c in concepts if c.depth_level == 0 and c.source == "book"),
            key=doc_order,
        )
        sections: list[Section] = []
        per_chapter_count: dict[uuid.UUID, int] = {}
        fallback = (chapters, False)
        for concept in reps:
            did = concept_doc(concept)
            chs, has_parts = doc_chapters.get(did, fallback) if did else fallback
            if not chs:
                chs = chapters
                has_parts = False
            part = chunk_part.get(concept.source_chunk_id, 0)
            # part 0(첫 경계 이전)은 문서 1장으로, 범위 밖은 문서 마지막 장으로
            idx = min(max(part, 1), len(chs)) - 1 if has_parts else 0
            chapter = chs[idx]
            order = (per_chapter_count.get(chapter.id, 0) + 1) * 10
            per_chapter_count[chapter.id] = per_chapter_count.get(chapter.id, 0) + 1
            section = Section(
                chapter_id=chapter.id,
                concept_id=concept.id,
                order_index=order,
                title=concept.name[:200],
            )
            self.db.add(section)
            sections.append(section)
        self.db.flush()
        return chapters, sections

    # ── ④ mastery/enrollment ───────────────────────────────────
    def _mastery_seed(
        self, course_id: uuid.UUID, documents: list[Document], concepts: list[Concept]
    ) -> tuple[list[dict], uuid.UUID | None, uuid.UUID | None]:
        # 진단 신호가 가장 많은 세션을 채택 (dev에는 미응답 세션이 쌓일 수 있음)
        sessions = list(
            self.db.scalars(
                select(DiagnosticSession)
                .where(DiagnosticSession.course_id == course_id)
                .order_by(DiagnosticSession.created_at.desc())
            )
        )
        strengths: dict[uuid.UUID, ConceptMastery] = {}
        best_signal = -1
        for session in sessions:
            rows = list(
                self.db.scalars(
                    select(ConceptMastery).where(ConceptMastery.session_id == session.id)
                )
            )
            signal = sum(
                1 for m in rows if m.resolved or m.strength != settings.BKT_P_INIT
            )
            if signal > best_signal:
                best_signal = signal
                strengths = {m.concept_id: m for m in rows}

        # floor/ceiling은 문서순 좌표 — 다중 PDF는 (문서 seq, part, chunk_index)로
        # 전 코스 순서를 잡는다 (_build_tree와 동일 규약).
        doc_seq = {d.id: i for i, d in enumerate(documents)}
        chunk_doc: dict[uuid.UUID, uuid.UUID] = {}
        chunk_part: dict[uuid.UUID, int] = {}
        chunk_order: dict[uuid.UUID, int] = {}
        for row in self.db.scalars(
            select(DocChunk).where(DocChunk.document_id.in_([d.id for d in documents]))
        ):
            chunk_doc[row.id] = row.document_id
            chunk_part[row.id] = row.part_index or 0
            chunk_order[row.id] = row.chunk_index

        mastery: list[dict] = []
        floor_id: uuid.UUID | None = None
        ceiling_id: uuid.UUID | None = None
        for c in sorted(
            concepts,
            key=lambda x: (
                doc_seq.get(chunk_doc.get(x.source_chunk_id), 999),
                chunk_part.get(x.source_chunk_id, 0),
                chunk_order.get(x.source_chunk_id, -1),
                x.id,
            ),
        ):
            m = strengths.get(c.id)
            if m is None:
                status, strength = "locked", 0.0
            elif m.resolved and m.strength >= settings.BKT_RESOLVE_HIGH:
                status, strength = "mastered", round(min(m.strength, 0.85), 3)
            elif m.resolved or m.strength != settings.BKT_P_INIT:
                status, strength = "todo", round(max(min(m.strength, 0.5), 0.0), 3)
            else:
                status, strength = "locked", 0.0
            mastery.append(
                {"concept_id": c.id, "key": c.key, "status": status, "strength": strength}
            )
            if c.depth_level == 0:
                if status == "todo" and floor_id is None:
                    floor_id = c.id
                ceiling_id = c.id  # 문서 순서 마지막 대표 = 목표(천장)
        return mastery, floor_id, ceiling_id

    def _finalize_enrollment(
        self,
        course_id: uuid.UUID,
        floor_id: uuid.UUID | None,
        ceiling_id: uuid.UUID | None,
        purpose: str,
        diag_q_count: int | None = None,
    ) -> None:
        user = AuthRepository(self.db).get_default_user()
        enrollment = self.db.get(Enrollment, (user.id, course_id))
        if enrollment is None:
            enrollment = Enrollment(user_id=user.id, course_id=course_id)
            self.db.add(enrollment)
        # 정본 이름 규약: floor_concept/ceiling_concept (*_concept_id 아님)
        enrollment.floor_concept = floor_id
        enrollment.ceiling_concept = ceiling_id
        enrollment.floor_found = floor_id is not None
        enrollment.purpose = purpose
        enrollment.diag_status = "completed"
        if diag_q_count is not None:
            enrollment.diag_q_count = diag_q_count
        self.db.flush()
