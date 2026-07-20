"""[3.Service] Ingestion: users → documents → courses → concepts.

ISSUE-008 설계 ("넓이는 미리, 깊이는 JIT"):
- 업로드 시점: 마크다운 헤딩 기준 섹션별 추출로 타겟 개념을 빠짐없이 확보.
  타겟은 source='book' + 출처 섹션(source_anchor), LLM이 보충한
  선수개념은 source='ai_prereq'로 출처를 구분한다(정본 규약, MERGE_AGREEMENT).
- 커리큘럼 시점(2단계, 미구현): source_anchor로 섹션 원문을 찾아
  하위 깊이를 JIT 확장.

병합 2단계: Integer→UUID 포팅(정본 모델 사용). 청크 임베딩은 passage 모델
(ISSUE-015 비대칭 임베딩), 개념 임베딩은 query 모델 유지.
"""
import asyncio
import base64
import logging
import re
import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.auth.repository import AuthRepository
from app.features.diagnostic.repository import DiagnosticRepository
from app.features.documents import refinement, sectioning
from app.features.documents.repository import DocumentRepository
from app.features.seed.models import Concept
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

_log = logging.getLogger("uvicorn.error")

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _sanitize_slug(raw: str | None) -> str | None:
    """추출 동시 산출 슬러그 검사 — 형식 위반은 버리고 seed 폴백에 맡긴다."""
    if not raw:
        return None
    slug = raw.strip().lower()
    return slug[:100] if _SLUG_RE.match(slug) else None

# 청크 임베딩(RAG 검색용) 입력 절단·배치 크기 — 임베딩 모델 토큰 한계 대비.
_CHUNK_EMBED_MAX_CHARS = 2000
_CHUNK_EMBED_BATCH = 16


def _extraction_prompt(anchor: str, section_text: str) -> str:
    return (
        "다음은 학습 자료의 한 섹션이다.\n"
        f"섹션 위치: {anchor}\n\n"
        "이 섹션이 다루는 타겟 개념을 하나도 빠짐없이 전부 추출하라.\n"
        "규칙:\n"
        "1. 이 섹션에서 설명·정의·소개하는 모든 개념/용어가 타겟이다. "
        "대표 개념 몇 개로 요약·압축하지 말 것. 사소해 보여도 본문이 다루면 포함할 것.\n"
        "2. prerequisites 에는 해당 개념을 이해하기 위해 '직접' 선행돼야 하는 개념만. "
        "이 자료에 없는 외부 배경지식이라도 이해에 필요하면 포함하라.\n"
        f"3. 트리 중첩 깊이는 최대 {settings.MAX_CONCEPT_DEPTH}단계까지만 (N-2 제한). "
        f"초과 깊이는 자동 삭제되므로 반드시 {settings.MAX_CONCEPT_DEPTH}단계 이내로 유지할 것.\n"
        "4. name 은 간결한 명사구, description 은 한국어 한 문장.\n"
        "5. 같은 개념은 한 번만 정의하고 중복 생성하지 말 것.\n"
        "6. 원문은 PDF 파싱 과정에서 문장 속 수식의 위첨자·특수기호가 "
        "평문화되어 있을 수 있다(예: 'x2+x'는 x^2+x, 'ex'는 e^x, "
        "'x3-3x2'는 x^3-3x^2). 수학 맥락으로 원래 수식을 복원해 "
        "name/description에 표준 표기(x^2, e^x 꼴)로 적을 것.\n"
        "7. section 필드에 이 섹션 전체를 관통하는 대표 개념 하나를 제시하라. "
        "헤딩 원문 복사가 아니라 학습 주제로서의 개념명으로 지을 것 "
        '(예: "■ 트리 순회 방법 - 3가지" 섹션이면 "트리 순회").\n'
        "8. 모든 개념(선수 포함)과 section에 key 필드로 영문 슬러그를 함께 산출하라 — "
        '소문자 영단어를 하이픈으로 연결한 의미 번역(음차 금지, 예: "이진 탐색 트리"→'
        '"binary-search-tree").\n\n'
        'JSON 형식: {"section":{"name":str,"description":str,"key":str},'
        '"concepts":[{"name":str,"description":str,"key":str,'
        '"prerequisites":[{ ...동일 구조... }]}]}\n'
        "주의: prerequisites 는 문자열 배열이 아니라 반드시 동일 구조의 "
        "객체 배열이어야 한다.\n\n"
        "=== 섹션 원문 ===\n"
        f"{section_text}"
    )


_DEDUP_SYSTEM = (
    "너는 지식 그래프의 중복 개념 판정기다. "
    "출력은 반드시 지정한 JSON 스키마만 따른다."
)


def _dedup_prompt(pairs: list) -> str:
    lines = [
        "아래 개념 쌍들이 '완전히 같은 개념의 다른 표기'인지 판정하라.\n",
        "같음(병합)으로 판정: 띄어쓰기·기호 차이, 약어와 전체 명칭"
        "(예: DRM = 디지털 저작권 관리(DRM)), 완전 동의어 표기.\n",
        "다름으로 판정: 포함·상하위 관계(예: '테스트 드라이버' vs '드라이버'), "
        "인접·대비 개념(예: 전위 순회 vs 후위 순회, /24 vs /31 서브넷), "
        "속성·범위가 다른 세부 변형. 애매하면 다름으로.\n",
        '출력 JSON: {"same": [같은 쌍의 번호, ...]}\n\n',
    ]
    for i, (a, b, _sim) in enumerate(pairs):
        lines.append(
            f"[{i}] A: {a.name} — {a.description[:80]}\n"
            f"    B: {b.name} — {b.description[:80]}\n"
        )
    return "".join(lines)


def _dedup_rank(concept) -> tuple:
    """병합 시 남길 노드 우선순위: 교재 출처 > 얕은 depth > id(결정적 타이브레이크).

    UUID 포팅 주: Integer PK 시절의 '먼저 생성' 순서는 UUID에선 없다 —
    id 비교는 결정성 보장용 타이브레이크로만 쓴다(대부분 source/depth에서 갈림).
    """
    return (0 if concept.source == "book" else 1, concept.depth_level, concept.id)


def _normalize_name(name: str) -> str:
    """중복 판정용 이름 정규화: 괄호 보조 표기·대괄호 기호·공백 제거 + 소문자.

    공백까지 전부 제거하는 이유(ISSUE-011 실측): "일계도함수/일계 도함수",
    "로그함수/로그 함수" 같은 표면 변형이 임베딩 유사도로는 0.75~0.81이라
    문턱(0.92)에 안 걸린다 — 표면 중복은 정규화가 잡아야 한다.
    """
    base = re.sub(r"\s*\([^)]*\)", " ", name)
    base = base.replace("[", " ").replace("]", " ")
    return re.sub(r"\s+", "", base).lower()


def _extract_figures(elements: list[dict]) -> list[dict]:
    """DP elements에서 figure/chart 크롭(base64)을 뽑아 저장용 dict로.

    **부수효과**: 각 element의 base64_encoding 키를 제거한다(pop) — 이미지는
    doc_figures가 정본이고, elements는 refined_elements(JSONB)로 저장되므로
    수 MB짜리 base64를 남기면 안 된다. mime은 매직 바이트로 판별.
    """
    out: list[dict] = []
    for e in elements:
        if not isinstance(e, dict):
            continue
        b64 = e.pop("base64_encoding", None)
        if not b64 or e.get("category") not in ("figure", "chart"):
            continue
        try:
            blob = base64.b64decode(b64)
        except Exception:  # noqa: BLE001 — 깨진 이미지는 버림
            continue
        if len(blob) < 200:  # 아이콘·불릿 수준의 초소형은 노이즈
            continue
        mime = "image/jpeg" if blob[:3] == b"\xff\xd8\xff" else "image/png"
        out.append(
            {
                "page": int(e.get("page") or 0),
                "element_id": int(e.get("id") or 0),
                "category": e.get("category"),
                "mime": mime,
                "data": blob,
            }
        )
    return out


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DocumentRepository(db)
        self.auth_repo = AuthRepository(db)
        self.diag_repo = DiagnosticRepository(db)

    def create_stub(self, *, filename: str, title: str | None) -> tuple[uuid.UUID, uuid.UUID]:
        """업로드 즉시 응답용 스텁(단일 PDF) — document + course + enrollment.

        비동기 ingest(ISSUE-010②): 파이프라인은 run_pipeline이 백그라운드에서
        실행하고, 프론트는 course 상세의 status를 폴링한다.
        """
        user = self.auth_repo.get_default_user()
        document = self.repo.create_document(user_id=user.id, filename=filename)
        course = self.repo.create_course(
            document_id=document.id, user_id=user.id, title=title or filename
        )
        # 다중 PDF 통합: 단일도 코스에 귀속(seq=0/primary)해 이후 로직 일관.
        document.course_id = course.id
        document.seq = 0
        document.role = "primary"
        self.diag_repo.ensure_enrollment(user_id=user.id, course_id=course.id)
        self.db.commit()
        return document.id, course.id

    def create_batch_stub(
        self, *, files: list[dict], title: str | None
    ) -> tuple[uuid.UUID, uuid.UUID, list[dict]]:
        """다중 PDF 스텁 — 코스 1개 + 문서 N개(순서/역할). files는 순서대로:
        [{"filename": str, "role": "primary"|"supplementary"}]. primary가 먼저 오도록
        호출측이 정렬. 반환: (anchor_document_id, course_id, [{document_id, role} …]).
        """
        user = self.auth_repo.get_default_user()
        # 앵커(코스 진행표시용) = 첫 primary. 코스 생성엔 document_id가 필요하므로 먼저.
        anchor_meta = files[0]
        anchor = self.repo.create_document(user_id=user.id, filename=anchor_meta["filename"])
        course = self.repo.create_course(
            document_id=anchor.id, user_id=user.id, title=title or anchor_meta["filename"]
        )
        anchor.course_id = course.id
        anchor.seq = 0
        anchor.role = anchor_meta.get("role", "primary")
        specs = [{"document_id": anchor.id, "role": anchor.role}]
        for i, meta in enumerate(files[1:], start=1):
            doc = self.repo.create_document(
                user_id=user.id,
                filename=meta["filename"],
                course_id=course.id,
                seq=i,
                role=meta.get("role", "primary"),
            )
            # 링크 보조자료: 원본 위치 = URL (파일 스토리지 없음)
            if meta.get("url"):
                doc.storage_url = meta["url"]
            specs.append({"document_id": doc.id, "role": doc.role})
        self.diag_repo.ensure_enrollment(user_id=user.id, course_id=course.id)
        self.db.commit()
        return anchor.id, course.id, specs

    async def _ingest_document(
        self,
        *,
        document,
        course_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        extract_graph: bool,
    ) -> None:
        """문서 1개: 파싱→정제→청킹→(추출→그래프). dedup·트리는 코스 단위(호출측).

        extract_graph=False(supplementary)면 청크·임베딩만 남겨 RAG 근거로 쓴다.
        """
        def stage(name: str) -> None:
            document.status = name
            self.db.commit()

        stage("parsing")
        parsed, elements = await solar_client.parse_document(file_bytes, filename)
        if not parsed.strip():
            raise ValueError("Document Parse 결과가 비어 있습니다.")
        document.raw_text = parsed
        self.db.commit()

        # Layer 2: DP가 크롭해 준 그림(base64)을 영속화하고 elements에서는
        # 스트립한다(refined_elements JSONB 비대화 방지 — 이미지는 doc_figures가 정본).
        figures = _extract_figures(elements)
        if figures:
            n = self.repo.add_figures(document_id=document.id, figures=figures)
            self.db.commit()
            _log.info("교재 그림 저장: %d개 (%s)", n, filename)

        stage("refining")
        refined, profile = await refinement.refine(elements)
        document.refined_elements = refined
        document.profile = profile
        self.db.commit()

        stage("chunking")
        chunks = sectioning.chunk_elements(
            refined["elements"], settings.EXTRACTION_SECTION_CHAR_BUDGET
        )
        if not chunks:
            chunks = sectioning.chunk_sections(
                sectioning.split_sections(parsed),
                settings.EXTRACTION_SECTION_CHAR_BUDGET,
            )
        chunk_rows = self.repo.add_chunks(
            document_id=document.id,
            chunks=chunks,
            embeddings=await self._embed_chunks(chunks),
        )
        self.db.commit()

        if extract_graph:
            stage("extracting")
            extractions = await self._extract_all(chunks)
            await self._persist_graph(
                course_id, extractions, chunk_ids=[row.id for row in chunk_rows]
            )

    async def _ingest_link(self, *, document, url: str) -> None:
        """링크 보조자료 1건: fetch→텍스트→청킹→임베딩. 항상 RAG 근거 전용.

        PDF 경로(Document Parse·정제·그래프 추출)를 타지 않는다 — 링크는
        supplementary 고정이라 청크·임베딩만 있으면 _course_doc_ids가 집어간다.
        실패해도 코스 전체를 죽이지 않는다(호출측에서 개별 failed 마킹).
        """
        from app.features.documents.linkfetch import fetch_link_text

        document.status = "parsing"
        self.db.commit()
        text, title = await fetch_link_text(url)
        document.raw_text = text
        if title:
            # 표시용 이름을 URL 대신 페이지 제목으로 (원본 위치는 storage_url에)
            document.filename = title[:512]
        self.db.commit()

        document.status = "chunking"
        self.db.commit()
        chunks = sectioning.chunk_sections(
            sectioning.split_sections(text),
            settings.EXTRACTION_SECTION_CHAR_BUDGET,
        )
        if not chunks:
            raise ValueError("링크 본문에서 청크를 만들지 못했습니다.")
        self.repo.add_chunks(
            document_id=document.id,
            chunks=chunks,
            embeddings=await self._embed_chunks(chunks),
        )
        self.db.commit()

    async def run_pipeline(
        self, *, document_id: uuid.UUID, course_id: uuid.UUID, file_bytes: bytes, filename: str
    ) -> None:
        """(단일 PDF) 파싱→추출→dedup→씨앗 트리. status로 단계 노출."""
        from app.features.materials.models import Document
        from app.features.seed.service import SeedService

        document = self.db.get(Document, document_id)
        if document is None:
            return
        try:
            await self._ingest_document(
                document=document, course_id=course_id,
                file_bytes=file_bytes, filename=filename, extract_graph=True,
            )
            await self._dedup_pass(course_id)
            document.status = "building_seed"
            self.db.commit()
            await SeedService(self.db).build_tree(course_id)
            document.status = "ready"
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            document.status = "failed"
            document.error = str(exc)[:2000]
            self.db.commit()
            _log.exception("섭취 실패(document=%s)", document_id)
            raise

    async def run_batch_pipeline(
        self, *, anchor_document_id: uuid.UUID, course_id: uuid.UUID, docs: list[dict]
    ) -> None:
        """(다중 PDF) 문서들을 순서대로 ingest → 코스 단위 dedup + 트리 1회.

        docs: [{"document_id", "file_bytes", "filename", "role"} …] (seq 순서).
        앵커(첫 primary) 문서의 status를 코스 진행표시로 쓴다(프론트 폴링).
        """
        from app.features.materials.models import Document
        from app.features.seed.service import SeedService

        anchor = self.db.get(Document, anchor_document_id)
        if anchor is None:
            return
        try:
            # 문서 간 병렬 ingest (C9): 각 문서를 독립 DB 세션에서 동시에 처리해
            # Solar 슬롯을 채운다(순차일 땐 소형 PDF들이 8슬롯 중 3~4만 사용).
            # sync Session은 태스크 간 공유 불가라 문서마다 세션 분리가 필수.
            # 동시 API 상한은 Solar 클라 전역 세마포어(8)가 잡는다(429 방지).
            results = await asyncio.gather(
                *(
                    self._ingest_one_isolated(spec, course_id, anchor_document_id)
                    for spec in docs
                ),
                return_exceptions=True,
            )
            # primary PDF 실패만 배치 실패로 전파(supplementary·링크 실패는 흡수).
            for r in results:
                if isinstance(r, BaseException):
                    raise r

            # 독립 세션들이 커밋한 변경을 배치 세션이 보게 refresh 후 dedup·트리(순차).
            self.db.expire_all()
            anchor = self.db.get(Document, anchor_document_id)
            await self._dedup_pass(course_id)
            anchor.status = "building_seed"
            self.db.commit()
            await SeedService(self.db).build_tree(course_id)
            anchor.status = "ready"
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            anchor = self.db.get(Document, anchor_document_id)
            if anchor is not None:
                anchor.status = "failed"
                anchor.error = str(exc)[:2000]
                self.db.commit()
            _log.exception("배치 섭취 실패(course=%s)", course_id)
            raise

    async def _ingest_one_isolated(
        self, spec: dict, course_id: uuid.UUID, anchor_id: uuid.UUID
    ) -> None:
        """문서 1건을 독립 DB 세션에서 ingest — 문서 간 병렬화의 단위(C9).

        anchor 문서는 여기서 status를 바꾸지 않는다(배치 세션이 트리 후 ready로).
        primary PDF 실패만 예외를 올려 배치 실패로 전파하고, supplementary·링크
        실패는 해당 문서만 failed로 마킹하고 삼킨다(근거 하나 빠질 뿐).
        """
        from app.features.materials.models import Document

        db = SessionLocal()
        try:
            svc = DocumentService(db)
            document = db.get(Document, spec["document_id"])
            if document is None:
                return
            try:
                if spec.get("url"):
                    await svc._ingest_link(document=document, url=spec["url"])
                else:
                    await svc._ingest_document(
                        document=document, course_id=course_id,
                        file_bytes=spec["file_bytes"], filename=spec["filename"],
                        extract_graph=(spec.get("role") == "primary"),
                    )
                if document.id != anchor_id:
                    document.status = "ready"
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                document.status = "failed"
                document.error = str(exc)[:2000]
                db.commit()
                label = spec.get("filename") or spec.get("url") or spec["document_id"]
                _log.warning("문서 섭취 실패: %s — %s", label, exc)
                if spec.get("role") == "primary" and not spec.get("url"):
                    raise  # primary PDF 실패 → 배치 전체 실패
        finally:
            db.close()

    async def ingest(self, *, file_bytes: bytes, filename: str, title: str | None) -> CourseDetail:
        """(동기 경로 — 스크립트/하위호환) 스텁 생성 + 파이프라인 완주 후 상세 반환."""
        document_id, course_id = self.create_stub(filename=filename, title=title)
        try:
            await self.run_pipeline(
                document_id=document_id,
                course_id=course_id,
                file_bytes=file_bytes,
                filename=filename,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502, detail=f"섭취 실패(document={document_id}): {exc}"
            ) from exc
        return self.get_course_detail(course_id)

    async def _extract_all(
        self, chunks: list[sectioning.Chunk]
    ) -> list[tuple[str, ExtractionResult]]:
        """섹션 청크별 병렬 추출 (제한 동시성, 청크당 1회 재시도)."""
        sem = asyncio.Semaphore(settings.EXTRACTION_MAX_CONCURRENCY)
        done = 0

        async def one(chunk: sectioning.Chunk) -> tuple[str, ExtractionResult]:
            nonlocal done
            async with sem:
                try:
                    result = await self._extract_concepts(chunk)
                except Exception:  # noqa: BLE001 — 일시 오류 대비 1회 재시도
                    _log.warning("추출 실패, 재시도: %s", chunk.anchor)
                    result = await self._extract_concepts(chunk)
                done += 1
                _log.info(
                    "추출 %d/%d 완료: %s (%d개 타겟)",
                    done, len(chunks), chunk.anchor, len(result.concepts),
                )
                return chunk.anchor, result

        _log.info("섹션 추출 시작: 청크 %d개", len(chunks))
        return list(await asyncio.gather(*(one(c) for c in chunks)))

    async def _extract_concepts(self, chunk: sectioning.Chunk) -> ExtractionResult:
        raw = await solar_client.generate_json(
            _extraction_prompt(chunk.anchor, chunk.text), system=_EXTRACTION_SYSTEM
        )
        try:
            return ExtractionResult.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(
                f"추출 JSON이 스키마 검증을 통과하지 못했습니다"
                f" (섹션: {chunk.anchor}): {exc}"
            ) from exc

    async def _dedup_pass(self, course_id: uuid.UUID) -> None:
        """일괄 중복 청소 (ISSUE-011): 유사도는 후보 수집만, 판정은 LLM이.

        실측 근거: 진짜 중복이 0.85~0.92 구간에 별개 개념과 섞여 분포해
        단일 문턱으로는 분리 불가 → 후보쌍을 LLM에 배치로 물어 확정 병합.
        ingest 직후에만 실행 (진단/학습 데이터가 생기기 전 — merge가 노드를
        삭제하므로).
        """
        pairs = self.repo.find_similar_pairs(
            course_id=course_id,
            min_sim=settings.DEDUP_CANDIDATE_SIM_THRESHOLD,
            limit=settings.DEDUP_MAX_PAIRS,
        )
        if not pairs:
            return
        same_ids: list[tuple[uuid.UUID, uuid.UUID]] = []
        for i in range(0, len(pairs), settings.DEDUP_JUDGE_BATCH_SIZE):
            batch = pairs[i : i + settings.DEDUP_JUDGE_BATCH_SIZE]
            try:
                raw = await solar_client.generate_json(
                    _dedup_prompt(batch), system=_DEDUP_SYSTEM
                )
            except Exception as exc:  # noqa: BLE001 — 청소 실패는 비치명
                _log.warning("중복 판정 실패, 배치 건너뜀: %s", exc)
                continue
            for idx in raw.get("same") or []:
                if isinstance(idx, int) and 0 <= idx < len(batch):
                    a, b, _sim = batch[idx]
                    same_ids.append((a.id, b.id))

        # 체인 병합(A~B, B~C) 대비: 삭제된 id를 최종 생존 id로 따라간다.
        redirect: dict[uuid.UUID, uuid.UUID] = {}

        def final_id(cid: uuid.UUID) -> uuid.UUID:
            while cid in redirect:
                cid = redirect[cid]
            return cid

        merged = 0
        for a_id, b_id in same_ids:
            ka, kb = final_id(a_id), final_id(b_id)
            if ka == kb:
                continue
            a, b = self.repo.get_concept(ka), self.repo.get_concept(kb)
            if a is None or b is None:
                continue
            keep, drop = (a, b) if _dedup_rank(a) <= _dedup_rank(b) else (b, a)
            if drop.depth_level < keep.depth_level:
                keep.depth_level = drop.depth_level
            _log.info("중복 병합: %r ← %r", keep.name, drop.name)
            self.repo.merge_concepts(keep=keep, drop=drop)
            redirect[drop.id] = keep.id
            merged += 1
        _log.info("중복 청소: 후보 %d쌍 → LLM 동일 판정 %d → 병합 %d건",
                  len(pairs), len(same_ids), merged)

    async def _embed_all(
        self, extractions: list[tuple[str, ExtractionResult]]
    ) -> dict[str, list[float]]:
        """개념 텍스트 배치 임베딩 (ISSUE-010: 개념당 1호출 → 64개씩 묶음).

        _persist_graph의 resolve와 동일한 순회 순서로 정규화 이름당 첫
        텍스트만 수집한다 — 기존 순차 embed와 같은 텍스트가 임베딩되도록.
        캐시에 없는 텍스트는 resolve가 단건 호출로 폴백하므로 정합성 무손실.
        """
        texts: list[str] = []
        seen: set[str] = set()

        def collect(name: str, description: str) -> None:
            norm = _normalize_name(name)
            if norm not in seen:
                seen.add(norm)
                texts.append(f"{name}\n{description}")

        def walk(node: ConceptNode) -> None:
            collect(node.name, node.description)
            for child in node.prerequisites:
                walk(child)

        for _, extraction in extractions:
            if extraction.section is not None:
                collect(extraction.section.name, extraction.section.description)
            for root in extraction.concepts:
                collect(root.name, root.description)
        for _, extraction in extractions:
            for root in extraction.concepts:
                walk(root)

        cache: dict[str, list[float]] = {}
        for i in range(0, len(texts), settings.EMBED_BATCH_SIZE):
            batch = texts[i : i + settings.EMBED_BATCH_SIZE]
            cache.update(zip(batch, await solar_client.embed_batch(batch)))
            _log.info("임베딩 배치 %d/%d", len(cache), len(texts))
        return cache

    async def _embed_chunks(
        self, chunks: list[sectioning.Chunk]
    ) -> list[list[float]]:
        """청크 본문 임베딩 (doc_chunks의 RAG 검색 벡터). 입력은 절단."""
        texts = [c.text[:_CHUNK_EMBED_MAX_CHARS] for c in chunks]
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _CHUNK_EMBED_BATCH):
            # ISSUE-015 비대칭 임베딩: 청크=passage 모델 (개념=query 모델 유지)
            vectors.extend(
                await solar_client.embed_batch(
                    texts[i : i + _CHUNK_EMBED_BATCH], purpose="passage"
                )
            )
        return vectors

    async def _persist_graph(
        self,
        course_id: uuid.UUID,
        extractions: list[tuple[str, ExtractionResult]],
        chunk_ids: list[uuid.UUID] | None = None,
    ) -> None:
        """추출 결과를 2단계로 저장한다.

        1단계: 모든 섹션의 타겟(root)을 먼저 등록 — 교재 출처(book+anchor) 확정.
        2단계: 선수관계 연결. 선수 노드는 기존 개념과 이름/임베딩으로 중복 판정해
               병합하고, 새로 만들 때만 source='ai_prereq'(LLM 보충 지식)으로 남긴다.

        조건부 섹션 계층 (ISSUE-009): 청크 타겟이 SECTION_NODE_MIN_FANOUT 이상이면
        섹션 대표 개념을 depth 0으로 세우고 타겟들을 depth 1 + kind='contains'로
        내린다. 미달 청크(논문 등)는 섹션 노드 없이 타겟이 그대로 depth 0.
        """
        by_norm: dict[str, uuid.UUID] = {}  # 정규화 이름 → concept_id
        edges: set[tuple[uuid.UUID, uuid.UUID]] = set()
        # 코스 내 슬러그 유니크 가드. 다중 PDF: 이전 문서가 이미 만든 슬러그를
        # DB에서 미리 로드해 문서 간 충돌(예: 두 PDF의 'protocol')을 막는다.
        # 충돌 슬러그는 None으로 두고 dedup/seed 폴백에 맡긴다(NULL은 유니크 예외).
        used_keys: set[str] = set(
            self.db.scalars(
                select(Concept.key).where(
                    Concept.course_id == course_id, Concept.key.isnot(None)
                )
            )
        )
        embed_cache = await self._embed_all(extractions)
        ids = chunk_ids or [None] * len(extractions)

        async def resolve(
            node: ConceptNode,
            depth_level: int,
            source: str,
            anchor: str | None,
            chunk_id: uuid.UUID | None,
        ) -> uuid.UUID:
            norm = _normalize_name(node.name)
            cid = by_norm.get(norm)
            if cid is not None:
                self._merge_concept(cid, node, depth_level, source, anchor, chunk_id)
                return cid

            key = f"{node.name}\n{node.description}"
            embedding = embed_cache.get(key) or await solar_client.embed(key)
            near = self.repo.find_nearest_concept(course_id=course_id, embedding=embedding)
            if near is not None and near[1] >= settings.CONCEPT_DEDUP_SIM_THRESHOLD:
                cid = near[0].id
                self._merge_concept(cid, node, depth_level, source, anchor, chunk_id)
            else:
                # 슬러그 동시 산출: 코스 내 중복이면 None으로 두고 seed가 채운다
                # (UniqueConstraint(course_id, key) 위반 방지).
                slug = _sanitize_slug(node.key)
                if slug and slug in used_keys:
                    slug = None
                if slug:
                    used_keys.add(slug)
                concept = self.repo.add_concept(
                    course_id=course_id,
                    name=node.name,
                    description=node.description,
                    depth_level=depth_level,
                    embedding=embedding,
                    source=source,
                    source_anchor=anchor,
                    source_chunk_id=chunk_id,
                    key=slug,
                )
                cid = concept.id
            by_norm[norm] = cid
            if len(by_norm) % 100 == 0:
                _log.info("개념 저장 진행: %d개 (임베딩 포함)", len(by_norm))
            return cid

        async def upsert(
            node: ConceptNode,
            depth_level: int,
            source: str,
            anchor: str | None,
            chunk_id: uuid.UUID | None,
        ) -> uuid.UUID:
            cid = await resolve(node, depth_level, source, anchor, chunk_id)
            for child in node.prerequisites:
                child_id = await upsert(child, depth_level + 1, "ai_prereq", None, None)
                edge = (cid, child_id)
                if edge not in edges and cid != child_id:
                    self.repo.add_edge(from_concept_id=cid, to_concept_id=child_id)
                    edges.add(edge)
            return cid

        def sectioned(extraction: ExtractionResult) -> bool:
            return (
                extraction.section is not None
                and len(extraction.concepts) >= settings.SECTION_NODE_MIN_FANOUT
            )

        # 1단계: 섹션 노드 + 타겟 전부 먼저 (교재 출처 확정 — 선수로도 등장하는
        # 개념이 ai_prereq 출처로 먼저 생기는 것을 방지)
        for (anchor, extraction), chunk_id in zip(extractions, ids):
            root_depth = 0
            if sectioned(extraction):
                root_depth = 1
                assert extraction.section is not None
                await resolve(
                    ConceptNode(
                        name=extraction.section.name,
                        description=extraction.section.description,
                        key=extraction.section.key,
                    ),
                    0,
                    "book",
                    anchor,
                    chunk_id,
                )
            for root in extraction.concepts:
                await resolve(root, root_depth, "book", anchor, chunk_id)

        # 2단계: 선수 연결 + 섹션 contains 연결
        for (anchor, extraction), chunk_id in zip(extractions, ids):
            root_depth = 0
            section_id: uuid.UUID | None = None
            if sectioned(extraction):
                root_depth = 1
                assert extraction.section is not None
                section_id = by_norm[_normalize_name(extraction.section.name)]
            for root in extraction.concepts:
                cid = await upsert(root, root_depth, "book", anchor, chunk_id)
                if section_id is not None and section_id != cid:
                    edge = (section_id, cid)
                    if edge not in edges:
                        self.repo.add_edge(
                            from_concept_id=section_id,
                            to_concept_id=cid,
                            kind="contains",
                        )
                        edges.add(edge)

    def _merge_concept(
        self,
        concept_id: uuid.UUID,
        node: ConceptNode,
        depth_level: int,
        source: str,
        anchor: str | None,
        chunk_id: uuid.UUID | None = None,
    ) -> None:
        """중복 판정된 기존 개념에 병합. 교재(book) 출처가 ai_prereq보다 우선."""
        concept = self.repo.get_concept(concept_id)
        if concept is None:
            return
        if source == "book" and concept.source == "ai_prereq":
            concept.source = "book"
            concept.source_anchor = anchor
            concept.source_chunk_id = chunk_id
            concept.description = node.description  # 교재 설명이 권위
        if depth_level < concept.depth_level:
            concept.depth_level = depth_level
        self.db.flush()

    def get_course_detail(self, course_id: uuid.UUID) -> CourseDetail:
        course = self.repo.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="코스를 찾을 수 없습니다.")

        concepts = [
            ConceptOut(
                id=c.id,
                name=c.name,
                description=c.description,
                depth_level=c.depth_level,
                source=c.source,
                source_anchor=c.source_anchor,
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
