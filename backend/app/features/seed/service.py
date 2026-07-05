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

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.auth.repository import AuthRepository
from app.features.diagnostic.models import ConceptMastery, DiagnosticSession, Enrollment
from app.features.documents.models import Chapter, Concept, DocChunk, Document, Section

_log = logging.getLogger("uvicorn.error")

_SLUG_BATCH = 80
_SLUG_SYSTEM = (
    "너는 개념 이름을 영문 슬러그로 변환하는 도구다. "
    "출력은 지정한 JSON 스키마만 따른다."
)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _slug_prompt(items: list[tuple[int, str]]) -> str:
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

    async def build(self, course_id: int, purpose: str = "exam") -> dict:
        from app.features.documents.models import Course

        course = self.db.get(Course, course_id)
        document = self.db.get(Document, course.document_id) if course else None
        if document is None:
            raise HTTPException(status_code=404, detail="코스/문서를 찾을 수 없습니다.")

        concepts = list(
            self.db.scalars(select(Concept).where(Concept.course_id == course_id))
        )
        if not concepts:
            raise HTTPException(status_code=400, detail="개념이 없는 코스입니다.")

        await self._fill_keys(concepts)
        chapters, sections = self._build_tree(course_id, document, concepts)
        mastery, floor_id, ceiling_id = self._mastery_seed(course_id, concepts)
        self._finalize_enrollment(course_id, floor_id, ceiling_id, purpose)
        self.db.commit()

        return {
            "course_id": course_id,
            "document": {
                "profile": document.profile,
                "concept_count": len(concepts),
            },
            "curriculum": {
                "chapters": len(chapters),
                "sections": len(sections),
                "gen_status": "pending",
            },
            "placement": {
                "floor_concept_id": floor_id,
                "ceiling_concept_id": ceiling_id,
                "purpose": purpose,
            },
            "mastery": mastery,
        }

    # ── ① key 슬러그 ────────────────────────────────────────────
    async def _fill_keys(self, concepts: list[Concept]) -> None:
        pending = [c for c in concepts if not c.key]
        if not pending:
            return
        seen: set[str] = {c.key for c in concepts if c.key}
        resolved: dict[int, str] = {}
        for i in range(0, len(pending), _SLUG_BATCH):
            batch = pending[i : i + _SLUG_BATCH]
            try:
                raw = await solar_client.generate_json(
                    _slug_prompt([(c.id, c.name) for c in batch]),
                    system=_SLUG_SYSTEM,
                )
                for row in raw.get("slugs") or []:
                    if isinstance(row, dict) and isinstance(row.get("id"), int):
                        slug = str(row.get("slug", "")).strip().lower()
                        if _SLUG_RE.match(slug):
                            resolved[row["id"]] = slug[:100]
            except Exception as exc:  # noqa: BLE001 — 폴백 슬러그로 진행
                _log.warning("슬러그 배치 실패, 폴백 사용: %s", exc)
        for c in pending:
            slug = resolved.get(c.id) or f"concept-{c.id}"
            if slug in seen:
                slug = f"{slug}-{c.id}"
            seen.add(slug)
            c.key = slug
        self.db.flush()
        _log.info("슬러그 생성: %d개 (LLM %d, 폴백 %d)",
                  len(pending), len(resolved), len(pending) - len(resolved))

    # ── ③ chapters/sections ────────────────────────────────────
    def _build_tree(
        self, course_id: int, document: Document, concepts: list[Concept]
    ) -> tuple[list[Chapter], list[Section]]:
        # 재실행 대비: 기존 트리는 지우고 다시 만든다 (gen_status pending 전제)
        for old in self.db.scalars(select(Chapter).where(Chapter.course_id == course_id)):
            self.db.delete(old)
        self.db.flush()

        scan = (document.refined_elements or {}).get("scan") or {}
        part_titles = [p["title"] for p in scan.get("parts") or []]

        chapters: list[Chapter] = []
        titles = part_titles or [document.filename]
        for i, title in enumerate(titles):
            chapter = Chapter(
                course_id=course_id, order_index=(i + 1) * 10, title=title[:200]
            )
            self.db.add(chapter)
            chapters.append(chapter)
        self.db.flush()

        # 대표 개념(depth 0, 교재 출처)을 출처 청크의 파트로 배정
        chunk_part: dict[int, int] = {
            row.id: row.part_index or 0
            for row in self.db.scalars(
                select(DocChunk).where(DocChunk.document_id == document.id)
            )
        }
        reps = sorted(
            (c for c in concepts if c.depth_level == 0 and c.source == "document"),
            key=lambda c: (chunk_part.get(c.source_chunk_id or -1, 0), c.id),
        )
        sections: list[Section] = []
        per_chapter_count: dict[int, int] = {}
        for concept in reps:
            part = chunk_part.get(concept.source_chunk_id or -1, 0)
            # part 0(첫 경계 이전)은 1장으로, 범위 밖은 마지막 장으로
            idx = min(max(part, 1), len(chapters)) - 1 if part_titles else 0
            chapter = chapters[idx]
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
        self, course_id: int, concepts: list[Concept]
    ) -> tuple[list[dict], int | None, int | None]:
        # 진단 신호가 가장 많은 세션을 채택 (dev에는 미응답 세션이 쌓일 수 있음)
        sessions = list(
            self.db.scalars(
                select(DiagnosticSession)
                .where(DiagnosticSession.course_id == course_id)
                .order_by(DiagnosticSession.id.desc())
            )
        )
        strengths: dict[int, ConceptMastery] = {}
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

        mastery: list[dict] = []
        floor_id: int | None = None
        ceiling_id: int | None = None
        for c in sorted(concepts, key=lambda x: x.id):
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
        self, course_id: int, floor_id: int | None, ceiling_id: int | None, purpose: str
    ) -> None:
        user = AuthRepository(self.db).get_default_user()
        enrollment = self.db.get(Enrollment, (user.id, course_id))
        if enrollment is None:
            enrollment = Enrollment(user_id=user.id, course_id=course_id)
            self.db.add(enrollment)
        enrollment.floor_concept_id = floor_id
        enrollment.ceiling_concept_id = ceiling_id
        enrollment.floor_found = floor_id is not None
        enrollment.purpose = purpose
        enrollment.diag_status = "completed"
        self.db.flush()
