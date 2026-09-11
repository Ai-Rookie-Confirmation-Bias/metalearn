"""단계별 수동 실행 — 파이프라인을 한 칸씩 돌려보고 결과를 확인하는 용도.

운영 경로(service.ParsingService.run)와 **같은 pipeline 함수를 부른다.**
여기서 로직을 다시 구현하면 디버그로 확인한 것과 실제 동작이 갈라진다.

중간 상태 보관:
  - 업로드 파일   → UPLOAD_DIR에 저장 (1단계에서 읽음)
  - 요소 배열     → documents.refined_elements["elements"]
  - 추출 결과     → documents.refined_elements["debug"]["extractions"]
  - 나머지        → 이미 각자 테이블에 있다 (조각·목차·개념·그림)

호출 사이에 프로세스가 재시작돼도 살아남아야 해서 전부 DB에 둔다.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.features.parsing.adapters import document_parse
from app.features.parsing.models import (
    Concept,
    ConceptEdge,
    DocFigure,
    DocSegment,
    DocStatus,
    DocTopic,
    SegmentSentence,
)
from app.features.parsing.pipeline import (
    concepts as concepts_step,
    dedup as dedup_step,
    density as density_step,
    embed as embed_step,
    figures as figures_step,
    normalize as normalize_step,
    persist as persist_step,
    quality as quality_step,
    refine as refine_step,
    segment as segment_step,
    sentences as sentences_step,
    topics as topics_step,
)
from app.features.parsing.repository import ParsingRepository
from app.features.parsing.schemas import ExtractionResult, Segment

_log = logging.getLogger("uvicorn.error")


@dataclass
class StepResult:
    """한 단계의 실행 결과. 프론트가 이걸 그대로 그린다."""

    step: str
    label: str
    elapsed_ms: int = 0
    solar_calls: int = 0
    summary: dict[str, Any] = field(default_factory=dict)
    # 무엇이 어떻게 바뀌었는지 눈으로 볼 표본
    preview: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None


# 단계 정의 — 프론트 목록과 실행 순서의 단일 출처.
STEPS: list[dict[str, Any]] = [
    {"id": "parse", "label": "1. Document Parse", "kind": "호출", "solar": 1,
     "desc": "PDF → 요소 배열. 판정 없음, 순수 호출. 결과는 아래 원문 패널에서 그대로 본다."},
    {"id": "figures", "label": "2. 그림 분리", "kind": "로직", "solar": 0,
     "desc": "base64 크롭을 떼어내고 주변 원문·비전 필요 여부만 준비. 설명은 안 만든다."},
    {"id": "normalize", "label": "2.5. 정규화 (제어문자·장식)", "kind": "로직", "solar": 0,
     "desc": "U+0007 → 공백(1:1 치환). 반복 배지·러닝 타이틀은 페이지 커버리지로 걷어낸다. category는 안 본다."},
    {"id": "refine_rules", "label": "3. 정제 1층 (규칙)", "kind": "로직", "solar": 0,
     "desc": "머리말·목차페이지·저작권을 removed 마킹. 물리 삭제 없음."},
    {"id": "refine_scan", "label": "4. 정제 2층 (LLM)", "kind": "호출", "solar": 1,
     "desc": "본문 시작 지점만 묻는다. 가드레일 2개로 수상하면 기각."},
    {"id": "segment", "label": "5. 조각 만들기", "kind": "로직", "solar": 0,
     "desc": "제목·문자예산으로 끊는다. 요소는 절대 안 쪼갬 → 표·수식 원자성."},
    {"id": "sentences", "label": "5-b. 문장 앵커", "kind": "로직", "solar": 0,
     "desc": "문장별 offset 부여. 북마크·드래그·근거 표시용."},
    {"id": "embed_segments", "label": "6. 조각 임베딩", "kind": "호출", "solar": 0,
     "desc": "passage 모델, 16개씩 배치."},
    {"id": "locate_figures", "label": "2-b. 그림 위치 복원", "kind": "로직", "solar": 0,
     "desc": "그림을 조각과 본문 내 offset에 매단다."},
    {"id": "topics", "label": "7. 목차 분류 ⭐", "kind": "호출", "solar": 1,
     "desc": "조각을 전부 목차에 배정 + 조각수 검산. 원문은 안 건드린다."},
    {"id": "extract", "label": "8. 개념 추출", "kind": "호출", "solar": 0,
     "desc": "조각마다 1회. 전체 비용의 80%."},
    {"id": "persist", "label": "9+11. 개념 임베딩 · 저장", "kind": "호출", "solar": 0,
     "desc": "query 모델 배치 임베딩 후 2-pass 저장. 개념↔조각은 다대다."},
    {"id": "dedup", "label": "10. 중복 정리", "kind": "호출", "solar": 0,
     "desc": "0.92 자동 병합 + 0.85~0.92 LLM 판정. 원문 출처는 전부 이관."},
    {"id": "density", "label": "12. 밀도 판정", "kind": "로직", "solar": 0,
     "desc": "본문 가능 / 뼈대만. 교과서에서 내용을 당겨올지 결정하는 스위치."},
]

_STEP_INDEX = {s["id"]: i for i, s in enumerate(STEPS)}

# 단계가 만들어내는 산출물. 재실행하면 자기 산출물과 **그 뒤 전부**를 지운다.
# 안 지우면 두 번째 실행이 유니크 제약에 걸리고(실측: uq_topic_seq 위반),
# 지우더라도 뒷단계 결과를 남겨두면 없어진 조각을 가리키는 개념이 생긴다.
_STEP_OUTPUTS: dict[str, tuple[str, ...]] = {
    "parse": ("elements",),
    "figures": ("figures",),
    "normalize": (),      # JSONB 덮어쓰기 — 지울 게 없다
    "refine_rules": (),   # JSONB 덮어쓰기 — 지울 게 없다
    "refine_scan": (),
    "segment": ("segments",),   # CASCADE로 문장·개념링크까지 따라 지워진다
    "sentences": ("sentences",),
    "embed_segments": (),       # 기존 행 갱신
    "locate_figures": (),       # 기존 행 갱신
    "topics": ("topics",),
    "extract": ("extractions",),
    "persist": ("concepts",),
    "dedup": (),                # 개념을 병합할 뿐 새로 만들지 않는다
    "density": (),              # 문서 컬럼 갱신
}


def _quality_note(report: quality_step.ParseQuality) -> str:
    """진단 수치를 사람이 읽을 한 줄로. 문제가 있으면 원인까지 짚는다."""
    if report.is_clean:
        return "표면 품질 정상."

    parts = [f"⚠ {report.verdict}."]
    if report.control_chars:
        parts.append(
            "제어문자는 화면에도 마크다운에도 안 그려져서 눈으로는 못 찾는다 — "
            "'공백이 사라진 것처럼' 보이지만 실제로는 공백 자리에 다른 문자가 "
            "들어온 것이다. 정규식 \\s에 안 걸리므로 문장 분리·임베딩·LLM 입력이 "
            "함께 망가진다. 아래 원문 패널은 이걸 ␇로 그려준다."
        )
    elif report.space_ratio < quality_step.MIN_SPACE_RATIO:
        parts.append(
            "PDF 텍스트 레이어에 스페이스 글리프가 없을 때 나오는 증상이다 — "
            "ocr=auto는 레이어가 있으면 그대로 가져온다(ocr=force는 렌더 이미지를 "
            "실제로 OCR한다)."
        )
    parts.append("아래 원문 패널에서 실제로 어떻게 나왔는지 확인할 것.")
    return " ".join(parts)


class DebugService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ParsingRepository(db)

    # ── 업로드 ────────────────────────────────────────────────────

    def upload(self, *, file_bytes: bytes, filename: str) -> uuid.UUID:
        """파일을 저장하고 문서를 pending으로 만든다. 파싱은 안 돌린다.

        같은 파일이 이미 있으면 산출물을 전부 지우고 처음부터 다시 할 수 있게
        되돌린다 — 디버그 도구이므로 재실행이 기본 동작이다.
        """
        fingerprint = hashlib.sha256(file_bytes).hexdigest()
        directory = Path(settings.UPLOAD_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{fingerprint}{Path(filename).suffix or '.pdf'}"
        path.write_bytes(file_bytes)

        document = self.repo.find_by_fingerprint(fingerprint)
        if document is None:
            source_format, _ = document_parse.detect_format(filename)
            document = self.repo.create_document(
                fingerprint=fingerprint,
                filename=filename,
                source_format=source_format,
                storage_path=str(path),
            )
        else:
            self.repo.clear_parsed(document.id)
            document.storage_path = str(path)

        document.status = DocStatus.PENDING.value
        document.error = None
        document.raw_markdown = None
        document.refined_elements = None
        document.density_grade = None
        document.avg_segment_chars = None
        document.chars_per_page = None
        document.concept_coverage = None
        self.db.commit()
        return document.id

    # ── 상태 조회 ─────────────────────────────────────────────────

    def state(self, document_id: uuid.UUID) -> dict[str, Any]:
        """어느 단계까지 끝났는지 + 현재 산출물 개수."""
        document = self._document(document_id)
        payload = document.refined_elements or {}
        debug = payload.get("debug") or {}
        topics, segments, concepts, edges = self.repo.load_tree(document_id)
        figures = self.repo.list_figures(document_id)

        return {
            "document_id": str(document.id),
            "filename": document.filename,
            "status": document.status,
            "error": document.error,
            "done": debug.get("done") or [],
            "counts": {
                "elements": len(payload.get("elements") or []),
                "figures": len(figures),
                "figures_located": sum(1 for f in figures if f.segment_id),
                "segments": len(segments),
                "sentences": sum(self.repo.count_sentences(document_id).values()),
                "topics": len(topics),
                "concepts": len(concepts),
                "edges": len(edges),
            },
            "density_grade": document.density_grade,
        }

    # ── 원문 조회 ─────────────────────────────────────────────────

    def raw(self, document_id: uuid.UUID) -> dict[str, Any]:
        """1단계 산출물 원본. **자르지 않고** 그대로 돌려준다.

        단계 결과의 표본 몇 개로는 "파서가 어떻게 뱉었는지"를 알 수 없다.
        조각·개념 품질 문제가 여기서 시작되는 일이 많아서, 요소 전체를
        원문 그대로 볼 수 있어야 한다.

        base64는 빼고 보낸다 — 요소 하나가 수 MB인데 화면에 쓸모도 없다.
        이미지는 2단계 이후 /figures/{id}로 따로 받는다.
        """
        document = self._document(document_id)
        payload = document.refined_elements or {}
        elements = payload.get("elements") or []
        report = quality_step.measure(elements)

        return {
            "document_id": str(document.id),
            "filename": document.filename,
            "markdown": document.raw_markdown or "",
            "quality": {
                "elements": report.elements,
                "pages": report.pages,
                "chars": report.chars,
                "avg_chars": report.avg_chars,
                "space_ratio": report.space_ratio,
                # 제어문자 3종은 화면이 ␇ 배지와 경고를 그리는 근거다.
                # 빠뜨리면 원문 뷰어가 손상을 '없음'으로 표시한다.
                "control_ratio": report.control_ratio,
                "control_chars": report.control_chars,
                "control_names": report.control_names,
                "glued_ratio": report.glued_ratio,
                "unterminated_ratio": report.unterminated_ratio,
                "verdict": report.verdict,
                "samples": report.samples,
            },
            "elements": [
                {
                    "idx": i,
                    "id": el.get("id"),
                    "category": el.get("category"),
                    "page": el.get("page"),
                    # 3단계 이후에 보면 어떤 요소가 왜 빠졌는지도 같이 보인다.
                    "removed": el.get("removed"),
                    "has_image": bool(el.get("base64_encoding")),
                    "text": segment_step.element_text(el),
                }
                for i, el in enumerate(elements)
            ],
        }

    # ── 단계 실행 ─────────────────────────────────────────────────

    async def run_step(self, document_id: uuid.UUID, step: str) -> StepResult:
        if step not in _STEP_INDEX:
            raise ValueError(f"알 수 없는 단계: {step}")

        # 재실행이면 이 단계부터의 산출물을 걷어낸다.
        self._reset_from(document_id, step)

        runner = getattr(self, f"_step_{step}")
        started = time.perf_counter()
        result: StepResult = await runner(document_id)
        result.elapsed_ms = int((time.perf_counter() - started) * 1000)

        self._mark_done(document_id, step)
        self.db.commit()
        _log.info("[debug] %s — %dms %s", step, result.elapsed_ms, result.summary)
        return result

    def _reset_from(self, document_id: uuid.UUID, step: str) -> None:
        """이 단계와 그 뒤 단계의 산출물을 지우고 done 표시를 되돌린다.

        뒷단계까지 지우는 이유: 조각을 다시 만들면 기존 목차·개념은 사라진
        조각을 가리키게 된다. 앞 단계를 고쳐 돌릴 때마다 뒤가 자동으로
        무효화되는 편이 디버깅에 안전하다.
        """
        document = self._document(document_id)
        index = _STEP_INDEX[step]
        outputs = {
            name
            for later in STEPS[index:]
            for name in _STEP_OUTPUTS.get(later["id"], ())
        }
        if not outputs:
            self._trim_done(document, index)
            return

        if "segments" in outputs:
            # doc_segments가 지워지면 문장·개념링크·그림연결이 CASCADE로 따라간다.
            self.db.query(DocSegment).filter(
                DocSegment.document_id == document_id
            ).delete(synchronize_session=False)
        elif "sentences" in outputs:
            self.db.query(SegmentSentence).filter(
                SegmentSentence.segment_id.in_(
                    select(DocSegment.id).where(DocSegment.document_id == document_id)
                )
            ).delete(synchronize_session=False)

        if "concepts" in outputs:
            for model in (ConceptEdge, Concept):
                self.db.query(model).filter(
                    model.document_id == document_id
                ).delete(synchronize_session=False)
        if "topics" in outputs:
            self.db.query(DocTopic).filter(
                DocTopic.document_id == document_id
            ).delete(synchronize_session=False)
        if "figures" in outputs:
            self.db.query(DocFigure).filter(
                DocFigure.document_id == document_id
            ).delete(synchronize_session=False)

        payload = dict(document.refined_elements or {})
        if "elements" in outputs:
            payload.pop("elements", None)
            # 3단계가 요소에서 뽑은 구조 근거도 같이 버린다. 하나라도 남으면
            # 7단계가 지워진 요소 기준의 근거로 배정해 재실행 결과를 믿을 수
            # 없게 된다 (body_sections는 요소 인덱스를 그대로 들고 있다).
            payload.pop("toc", None)
            payload.pop("page_sections", None)
            payload.pop("body_sections", None)
            document.raw_markdown = None
        if "extractions" in outputs:
            debug = dict(payload.get("debug") or {})
            debug.pop("extractions", None)
            debug.pop("failed", None)
            payload["debug"] = debug
        document.refined_elements = payload

        self._trim_done(document, index)
        self.db.flush()

    @staticmethod
    def _trim_done(document, index: int) -> None:
        keep = {s["id"] for s in STEPS[:index]}
        payload = dict(document.refined_elements or {})
        debug = dict(payload.get("debug") or {})
        debug["done"] = [s for s in (debug.get("done") or []) if s in keep]
        payload["debug"] = debug
        document.refined_elements = payload

    # ── 각 단계 ───────────────────────────────────────────────────

    async def _step_parse(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        if not document.storage_path:
            raise ValueError("업로드된 파일이 없습니다.")

        markdown, elements = await document_parse.parse(
            Path(document.storage_path).read_bytes(), document.filename
        )
        document.raw_markdown = markdown
        document.status = DocStatus.PARSING.value
        self._save_elements(document, elements)

        categories: dict[str, int] = {}
        for el in elements:
            key = str(el.get("category"))
            categories[key] = categories.get(key, 0) + 1

        report = quality_step.measure(elements)

        # 표본은 여기 담지 않는다 — 자른 미리보기로는 "어떻게 나왔는지"를
        # 알 수 없어서 원문 전용 패널(/raw)이 전체를 그대로 보여준다.
        return StepResult(
            step="parse", label="1. Document Parse", solar_calls=1,
            summary={
                "요소": len(elements),
                "페이지": report.pages,
                "마크다운": f"{len(markdown):,}자",
                "요소당 평균": f"{report.avg_chars:,}자",
                "카테고리": categories,
                **report.to_summary(),
            },
            note=(
                _quality_note(report)
                + " category는 챕터 경계 판정에 쓰지 않는다 — 같은 성격의 제목이 "
                "header와 heading1로 갈리는 게 실측됐다. 경계는 7단계가 정한다."
            ),
        )

    async def _step_figures(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)

        drafts = figures_step.extract(elements)
        self._save_elements(document, elements)  # base64가 빠진 상태로 다시 저장
        rows = self.repo.add_figures(document_id=document_id, figures=drafts)

        vision = [d for d in drafts if d.needs_vision]
        return StepResult(
            step="figures", label="2. 그림 분리", solar_calls=0,
            summary={
                "그림": len(drafts),
                "비전 필요": len(vision),
                "캡션 검출": sum(1 for d in drafts if d.caption),
                "저장 용량": f"{sum(len(d.data) for d in drafts) / 1024:.0f} KB",
            },
            preview=[
                {
                    "page": d.page,
                    "element": d.element_id,
                    "category": d.category,
                    "needs_vision": d.needs_vision,
                    "caption": d.caption,
                    "context_len": len(d.context_text or ""),
                    "context": (d.context_text or "")[:140],
                    "figure_id": str(row.id),
                }
                for d, row in list(zip(drafts, rows))[:12]
            ],
            note=(
                "설명은 여기서 만들지 않는다. context_text와 needs_vision만 "
                "준비하고, 실제 비전 호출은 플래그가 붙은 소수만 나중에."
            ),
        )

    async def _step_normalize(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)

        normalized, report = normalize_step.normalize(elements)
        cleaned, clean = normalize_step.clean(normalized)
        self._save_elements(document, cleaned)
        final = quality_step.measure(
            [el for el in cleaned if not el.get("removed")]
        )

        before, after = report.before, report.after
        reasons = " · ".join(f"{k} {v:,}" for k, v in clean.removed.items())
        return StepResult(
            step="normalize", label="2.5. 정규화 (제어문자·장식)", solar_calls=0,
            summary={
                "치환": (
                    f"{report.replaced:,}개 "
                    + ", ".join(f"{k} ×{n:,}" for k, n in report.counts.items())
                    if report.replaced
                    else "없음 (이미 정상)"
                ),
                "제어문자": f"{before.control_chars:,}개 → {after.control_chars:,}개",
                "공백 비율": f"{before.space_ratio}% → {after.space_ratio}%",
                "장식 그룹": f"{len(clean.groups)}종 ({reasons or '없음'})",
                "장식 제거": (
                    f"{sum(clean.removed.values()):,}개 마킹 · "
                    f"{clean.partial:,}개 부분 제거"
                ),
                "요소": f"{clean.elements_in:,} → {clean.elements_out:,}",
                "요소당 평균": f"{before.avg_chars:,}자 → {final.avg_chars:,}자",
                "판정": f"{before.verdict} → {final.verdict}",
                "검산": (
                    f"제어문자 0 · 길이 보존 · 회계 일치"
                    if report.is_clean and not clean.unaccounted
                    else f"⚠ 제어문자 {after.control_chars:,} · 회계 {clean.unaccounted:+,}"
                ),
            },
            preview=[
                *(
                    {
                        "kind": "replace", "idx": s["idx"], "category": s["category"],
                        "page": s["page"], "note": f"{s['replaced']}개 치환",
                        "before": s["before"], "after": s["after"],
                    }
                    for s in report.samples
                ),
                *(
                    {
                        "kind": "decoration", "reason": g.reason, "hits": g.hits,
                        "pages": g.pages, "coverage": round(g.coverage * 100),
                        "text": g.key,
                    }
                    for g in clean.groups
                ),
                *(
                    {
                        "kind": "strip", "category": s["category"], "page": s["page"],
                        "note": "장식 줄 제거",
                        "before": s["before"], "after": s["after"],
                    }
                    for s in clean.samples
                ),
            ],
            note=(
                "치환은 1:1이라 요소당 평균이 정의상 안 변한다 — 평균을 올리는 "
                "건 장식 제거 쪽이다. 장식 판정은 category를 안 보고 페이지 "
                "커버리지로 한다(3권 실측에서 장식이 header/footer로 잡힌 비율이 "
                "100% / 68% / 2%로 요동쳤다). 제거는 마킹이라 되돌릴 수 있고, "
                "본문과 섞인 요소는 줄 단위로만 도려낸다 — 부분 문자열로 지우면 "
                "목차 줄이 훼손된다(실측)."
            ),
        )

    async def _step_refine_rules(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)

        refined = refine_step.apply_rules(elements)
        document.status = DocStatus.REFINING.value
        self._save_elements(document, refined)

        # 목차 페이지는 본문에서 빼되 버리지 않는다 — 7단계의 정답지.
        toc = refine_step.extract_toc(refined)
        page_sections = refine_step.extract_page_sections(refined)
        body_sections = refine_step.extract_body_sections(refined)
        self._save_structure(document, toc, page_sections, body_sections)

        removed = [(i, el) for i, el in enumerate(refined) if el.get("removed")]
        reasons: dict[str, int] = {}
        for _, el in removed:
            reasons[el["removed"]] = reasons.get(el["removed"], 0) + 1

        return StepResult(
            step="refine_rules", label="3. 정제 1층 (규칙)", solar_calls=0,
            summary={
                "전체": len(refined),
                "제거 마킹": len(removed),
                "사유별": reasons,
                "자료의 목차": len(toc) or "없음",
                "러닝 헤더 단원": len(set(page_sections.values())) or "없음",
                "본문 단원 표기": (
                    [f"{e['no']}. {e['title']}" for e in body_sections] or "없음"
                ),
            },
            preview=(
                [
                    {"page": p, "section": t}
                    for p, t in sorted(page_sections.items())
                ]
                or [
                    {"no": e["no"], "title": e["title"], "start_page": e["page"]}
                    for e in toc
                ]
                or [
                    {
                        "idx": i,
                        "removed": el["removed"],
                        "category": el.get("category"),
                        "text": segment_step.element_text(el)[:120],
                    }
                    for i, el in removed[:15]
                ]
            ),
            note=(
                "물리 삭제가 아니라 마킹이다. 목차를 찾았으면 그 항목이 "
                "7단계의 정답지가 된다 — LLM이 지어내는 것보다 항상 낫다."
            ),
        )

    async def _step_refine_scan(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)

        before = sum(1 for el in elements if el.get("removed") == "front_matter")
        marked = await refine_step.apply_scan(elements)
        self._save_elements(document, elements)

        front = [
            (i, el) for i, el in enumerate(elements)
            if el.get("removed") == "front_matter"
        ]
        return StepResult(
            step="refine_scan", label="4. 정제 2층 (LLM)", solar_calls=1,
            summary={
                "새로 마킹": marked,
                "서문 구간": len(front),
                "판정": "적용됨" if marked or before else "기각 또는 서문 없음",
            },
            preview=[
                {
                    "idx": i,
                    "category": el.get("category"),
                    "text": segment_step.element_text(el)[:120],
                }
                for i, el in front[:10]
            ],
            note=(
                "가드레일 2개: 앞 25% 초과면 기각, 제거 구간에 표·수식이 있으면 "
                "기각. 실측 사고(준비 학습이 서문으로 오판돼 개념 80→49)를 막는다."
            ),
        )

    async def _step_segment(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)

        budget = segment_step.plan_budget(
            elements,
            settings.EXTRACTION_SECTION_CHAR_BUDGET,
            settings.SEGMENT_TARGET_COUNT,
            settings.SEGMENT_MIN_BUDGET,
        )
        segments = segment_step.build(
            elements, budget, settings.SEGMENT_MIN_CHARS
        )
        if not segments:
            raise ValueError("조각이 하나도 만들어지지 않았습니다.")

        document.status = DocStatus.SEGMENTING.value
        self.repo.add_segments(document_id=document_id, segments=segments)

        sizes = [s.char_count for s in segments]
        return StepResult(
            step="segment", label="5. 조각 만들기", solar_calls=0,
            summary={
                "조각": len(segments),
                "평균": f"{sum(sizes) // len(sizes):,}자",
                "최대": f"{max(sizes):,}자",
                "예산": (
                    f"{budget:,}자"
                    + ("" if budget == settings.EXTRACTION_SECTION_CHAR_BUDGET
                       else f" (기본 {settings.EXTRACTION_SECTION_CHAR_BUDGET:,}에서 축소 — 얇은 자료)")
                ),
                "예산 초과": sum(1 for s in sizes if s > budget),
            },
            preview=[
                {
                    "seq": s.seq,
                    "chars": s.char_count,
                    "heading": s.heading,
                    "pages": f"{s.page_from}-{s.page_to}",
                    "elements": f"{s.element_from}-{s.element_to}",
                    "text": s.content[:200],
                }
                for s in segments[:12]
            ],
            note=(
                "예산 초과가 남을 수 있다 — 단일 요소(큰 표)가 예산보다 크면 "
                "쪼개지 않고 통째로 둔다. 표가 중간에서 잘리는 것보다 낫다."
            ),
        )

    async def _step_sentences(self, document_id: uuid.UUID) -> StepResult:
        segments = self._segments(document_id)
        rows = {s.seq: s for s in self.repo.load_tree(document_id)[1]}

        by_seq = sentences_step.split_all(segments)
        saved = self.repo.add_sentences(sentences_by_seq=by_seq, segment_rows=rows)

        first = next((v for v in by_seq.values() if v), [])
        return StepResult(
            step="sentences", label="5-b. 문장 앵커", solar_calls=0,
            summary={
                "문장": saved,
                "조각당 평균": round(saved / max(len(by_seq), 1), 1),
            },
            preview=[
                {"seq": s.seq, "range": f"{s.char_start}~{s.char_end}", "text": s.text[:160]}
                for s in first[:15]
            ],
            note="원문을 복사하지 않고 offset으로 가리키기만 한다. 표·수식은 안 쪼갠다.",
        )

    async def _step_embed_segments(self, document_id: uuid.UUID) -> StepResult:
        segments = self._segments(document_id)
        rows = {s.seq: s for s in self.repo.load_tree(document_id)[1]}

        vectors = await embed_step.embed_segments(segments)
        for segment, vector in zip(segments, vectors):
            if segment.seq in rows:
                rows[segment.seq].embedding = vector

        calls = -(-len(segments) // settings.SEGMENT_EMBED_BATCH)
        return StepResult(
            step="embed_segments", label="6. 조각 임베딩", solar_calls=calls,
            summary={
                "벡터": len(vectors),
                "차원": len(vectors[0]) if vectors else 0,
                "모델": settings.SOLAR_EMBED_PASSAGE_MODEL,
                "호출": calls,
            },
            note="비대칭 임베딩 — 조각은 passage, 개념은 query 모델을 쓴다.",
        )

    async def _step_locate_figures(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        elements = self._elements(document)
        segments = self._segments(document_id)
        segment_rows = {s.seq: s for s in self.repo.load_tree(document_id)[1]}
        figure_rows = {f.element_id: f for f in self.repo.list_figures(document_id)}

        # locate()는 FigureDraft를 받지만 element_id만 쓴다.
        drafts = [
            figures_step.FigureDraft(
                page=f.page, element_id=f.element_id, category=f.category,
                mime=f.mime, data=b"",
            )
            for f in figure_rows.values()
        ]
        located = figures_step.locate(drafts, segments, elements)

        for element_id, (seq, offset) in located.items():
            row = figure_rows.get(element_id)
            if row is not None and seq in segment_rows:
                row.segment_id = segment_rows[seq].id
                row.char_offset = offset

        preview = []
        for element_id, (seq, offset) in list(located.items())[:10]:
            content = segment_rows[seq].content if seq in segment_rows else ""
            preview.append({
                "element": element_id,
                "segment": seq,
                "offset": offset,
                "before": content[max(0, offset - 60):offset],
                "after": content[offset:offset + 60],
            })

        return StepResult(
            step="locate_figures", label="2-b. 그림 위치 복원", solar_calls=0,
            summary={"그림": len(drafts), "위치 확정": len(located)},
            preview=preview,
            note=(
                "offset이 본문 어디를 가리키는지 before/after로 확인할 것. "
                "그림 요소도 본문에 자기 자리(이미지 마크다운)를 차지한다."
            ),
        )

    async def _step_topics(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        segments = self._segments(document_id)
        segment_rows = {s.seq: s for s in self.repo.load_tree(document_id)[1]}

        document.status = DocStatus.TOPICS.value
        payload = document.refined_elements or {}
        toc = payload.get("toc") or []
        page_sections = payload.get("page_sections") or {}
        body_sections = payload.get("body_sections") or []
        assignment = await topics_step.classify(
            segments, settings.TOPIC_MAX_COUNT,
            toc=toc, page_sections=page_sections, body_sections=body_sections,
        )

        topic_rows = self.repo.add_topics(
            document_id=document_id,
            titles=[(t.seq, t.title) for t in assignment.topics],
        )
        for draft in assignment.topics:
            members = []
            for seq in draft.segment_seqs:
                row = segment_rows.get(seq)
                if row is None:
                    continue
                self.repo.assign_topic(row, topic_rows[draft.seq])
                members.append(row)
            self.repo.set_topic_pages(topic_rows[draft.seq], members)

        # 러닝 헤더나 자료의 목차로 배정했으면 LLM을 안 부른 것(0회).
        # LLM 경로는 2패스라 짓기 1 + 배정 1 = 2회다.
        # 디버그 도구가 틀린 호출 수를 보여주면 존재 이유가 없다.
        used_llm = not (body_sections or page_sections or toc)
        return StepResult(
            step="topics", label="7. 목차 분류 ⭐",
            solar_calls=2 if used_llm else 0,
            summary={
                "출처": (
                    "본문 단원 표기" if body_sections
                    else "러닝 헤더" if page_sections
                    else "자료의 목차" if toc else "LLM 생성 (2패스)"
                ),
                "목차": len(assignment.topics),
                "상한": settings.TOPIC_MAX_COUNT,
                "조각 총수": assignment.total_segments,
                "배정 합계": assignment.assigned_count,
                "검산": "통과" if assignment.is_complete else "실패",
                "연속성": (
                    "정상"
                    if all(
                        t.segment_seqs
                        == list(range(t.segment_seqs[0], t.segment_seqs[-1] + 1))
                        for t in assignment.topics
                    )
                    else "끊긴 구간 있음"
                ),
            },
            preview=[
                {
                    "seq": t.seq,
                    "title": t.title,
                    "count": len(t.segment_seqs),
                    "segments": t.segment_seqs,
                }
                for t in assignment.topics
            ],
            note=(
                "검산이 핵심 — 조각 수와 목차별 합계가 같아야 원문 누락이 없다. "
                "1차에서 빠지면 2차 배정을 한 번 더 부른다(로그 확인)."
            ),
        )

    async def _step_extract(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        segments = self._segments(document_id)
        topic_rows, segment_rows, _, _ = self.repo.load_tree(document_id)
        titles = {t.id: t.title for t in topic_rows}
        by_segment = {
            s.seq: titles.get(s.topic_id, "") for s in segment_rows
        }

        document.status = DocStatus.EXTRACTING.value
        # 근거 문장 번호는 5-b가 만든 것과 같은 분리 결과여야 한다.
        # 여기서 다시 나누면 저장된 앵커와 번호가 어긋난다.
        extractions, failed = await concepts_step.extract_all(
            segments, by_segment, sentences_step.split_all(segments)
        )

        self._save_debug(
            document,
            extractions={
                str(seq): result.model_dump() for seq, result in extractions.items()
            },
            failed=failed,
        )

        counts = {seq: len(r.concepts) for seq, r in extractions.items()}
        sample_seq = max(counts, key=counts.get) if counts else None
        roots = [c for r in extractions.values() for c in r.concepts]
        with_evidence = sum(1 for c in roots if c.evidence)
        return StepResult(
            step="extract", label="8. 개념 추출", solar_calls=len(segments),
            summary={
                "호출": len(segments),
                "추출 개념(루트)": sum(counts.values()),
                "조각당 평균": round(sum(counts.values()) / max(len(counts), 1), 1),
                "근거 문장 있음": (
                    f"{with_evidence}/{len(roots)} "
                    f"({round(with_evidence * 100 / max(len(roots), 1))}%)"
                ),
                "실패 조각": failed,
            },
            preview=[
                {
                    "name": c.name,
                    "description": c.description[:100],
                    "key": c.key,
                    "prerequisites": [p.name for p in c.prerequisites],
                }
                for c in (extractions[sample_seq].concepts[:15] if sample_seq is not None else [])
            ],
            note=(
                f"조각 #{sample_seq}의 개념을 보여준다. 이 단계가 전체 비용의 80%. "
                "선수개념은 아직 저장 전이라 여기 이름만 보인다."
            ),
        )

    async def _step_persist(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        debug = (document.refined_elements or {}).get("debug") or {}
        raw = debug.get("extractions") or {}
        if not raw:
            raise ValueError("8단계(개념 추출)를 먼저 실행하세요.")

        extractions = {
            int(seq): ExtractionResult.model_validate(payload)
            for seq, payload in raw.items()
        }
        topic_rows, segment_rows, _, _ = self.repo.load_tree(document_id)
        rows_by_seq = {s.seq: s for s in segment_rows}
        topic_by_id = {t.id: t for t in topic_rows}
        topic_of_segment = {
            s.seq: topic_by_id[s.topic_id]
            for s in segment_rows
            if s.topic_id in topic_by_id
        }

        texts = persist_step.concept_texts(extractions)
        cache = await embed_step.embed_texts(texts)
        result = persist_step.persist(
            self.repo,
            document_id=document_id,
            extractions=extractions,
            segment_rows=rows_by_seq,
            topic_of_segment=topic_of_segment,
            embeddings=cache,
        )

        _, _, concept_rows, _ = self.repo.load_tree(document_id)
        multi = [
            c for c in concept_rows if len(c.segment_links) > 1
        ]
        multi.sort(key=lambda c: -len(c.segment_links))
        seq_of = {s.id: s.seq for s in segment_rows}

        return StepResult(
            step="persist", label="9+11. 개념 임베딩 · 저장",
            solar_calls=-(-len(texts) // settings.EMBED_BATCH_SIZE),
            summary={
                "개념": result.concept_count,
                "선후관계": result.edge_count,
                "원문 링크": result.link_count,
                "개념 없는 조각": result.empty_segments,
                "2개 이상 조각에 걸친 개념": len(multi),
            },
            preview=[
                {
                    "name": c.name,
                    "source": c.source,
                    "segments": sorted(
                        seq_of[l.segment_id] for l in c.segment_links
                        if l.segment_id in seq_of
                    ),
                }
                for c in multi[:15]
            ],
            note=(
                "⭐ 여기 목록이 다대다의 증거다. 기존 구조라면 각 개념의 원문이 "
                "첫 번째 하나만 남고 나머지는 사라졌다."
            ),
        )

    async def _step_dedup(self, document_id: uuid.UUID) -> StepResult:
        before = len(self.repo.load_tree(document_id)[2])
        result = await dedup_step.run(self.repo, document_id)
        after = len(self.repo.load_tree(document_id)[2])

        return StepResult(
            step="dedup", label="10. 중복 정리",
            solar_calls=result.llm_calls,
            summary={
                "후보쌍": result.candidate_pairs,
                "자동 병합(≥0.92)": result.auto_merged,
                "LLM 판정 병합": result.judged_merged,
                "살려낸 원문 링크": result.links_preserved,
                "개념": f"{before} → {after}",
            },
            note=(
                "살려낸 원문 링크 = 기존 merge_concepts였다면 삭제됐을 출처. "
                "후보쌍이 적으면 실질 중복 제거는 이름 정규화(①)가 이미 한 것."
            ),
        )

    async def _step_density(self, document_id: uuid.UUID) -> StepResult:
        document = self._document(document_id)
        debug = (document.refined_elements or {}).get("debug") or {}
        segments = self._segments(document_id)
        _, _, concept_rows, _ = self.repo.load_tree(document_id)

        linked = {
            l.segment_id for c in concept_rows for l in c.segment_links
        }
        rows = {s.seq: s for s in self.repo.load_tree(document_id)[1]}
        empty = [seq for seq, row in rows.items() if row.id not in linked]

        report = density_step.measure(
            segments,
            empty_segments=empty,
            failed_segments=debug.get("failed") or [],
        )
        document.density_grade = report.grade
        document.avg_segment_chars = report.avg_chars
        document.chars_per_page = report.chars_per_page
        document.concept_coverage = report.coverage
        document.status = DocStatus.READY.value

        return StepResult(
            step="density", label="12. 밀도 판정", solar_calls=0,
            summary={
                "등급": "본문 가능" if report.is_body else "뼈대만",
                "페이지당": f"{report.chars_per_page:,}자 ({report.page_count}페이지)",
                "조각당 평균": f"{report.avg_chars:,}자 (참고 — 판정에 안 씀)",
                "커버리지": f"{report.coverage}%",
                "기준": f"페이지당 {density_step.BODY_MIN_CHARS_PER_PAGE:,}자 이상 · "
                        f"커버리지 {density_step.BODY_MIN_COVERAGE}% 이상",
                "판정 근거": report.reason,
                "개념 없는 조각": report.empty_segments,
            },
            note=(
                "'뼈대만'이면 다른 자료에서 설명을 당겨와야 한다. "
                "조각당 평균은 조각 예산의 함수라 판정에 쓰지 않는다 — 실측 3권에서 "
                "3,212/3,351/3,557로 붙어 나와 슬라이드까지 '본문 가능'이 됐다. "
                "페이지당은 299/1,266/3,396으로 갈린다."
            ),
        )

    # ── 내부 ──────────────────────────────────────────────────────

    def _document(self, document_id: uuid.UUID):
        document = self.repo.get_document(document_id)
        if document is None:
            raise ValueError(f"문서를 찾을 수 없습니다: {document_id}")
        return document

    @staticmethod
    def _elements(document) -> list[dict[str, Any]]:
        elements = (document.refined_elements or {}).get("elements")
        if not elements:
            raise ValueError("1단계(Document Parse)를 먼저 실행하세요.")
        return elements

    def _segments(self, document_id: uuid.UUID) -> list[Segment]:
        """DB의 조각 행을 파이프라인이 쓰는 Segment로 되돌린다."""
        rows = self.repo.load_tree(document_id)[1]
        if not rows:
            raise ValueError("5단계(조각 만들기)를 먼저 실행하세요.")
        return [
            Segment(
                seq=r.seq, content=r.content, heading=r.heading,
                element_from=r.element_from, element_to=r.element_to,
                page_from=r.page_from, page_to=r.page_to,
            )
            for r in rows
        ]

    @staticmethod
    def _save_elements(document, elements: list[dict[str, Any]]) -> None:
        payload = dict(document.refined_elements or {})
        payload["elements"] = elements
        document.refined_elements = payload

    @staticmethod
    def _save_structure(
        document,
        toc: list[dict[str, Any]],
        page_sections: dict[int, str],
        body_sections: list[dict[str, Any]],
    ) -> None:
        payload = dict(document.refined_elements or {})
        payload["toc"] = toc
        payload["page_sections"] = {str(k): v for k, v in page_sections.items()}
        payload["body_sections"] = body_sections
        document.refined_elements = payload

    @staticmethod
    def _save_debug(document, **values: Any) -> None:
        payload = dict(document.refined_elements or {})
        debug = dict(payload.get("debug") or {})
        debug.update(values)
        payload["debug"] = debug
        document.refined_elements = payload

    def _mark_done(self, document_id: uuid.UUID, step: str) -> None:
        document = self._document(document_id)
        payload = dict(document.refined_elements or {})
        debug = dict(payload.get("debug") or {})
        done = list(debug.get("done") or [])
        if step not in done:
            done.append(step)
        debug["done"] = done
        payload["debug"] = debug
        document.refined_elements = payload
