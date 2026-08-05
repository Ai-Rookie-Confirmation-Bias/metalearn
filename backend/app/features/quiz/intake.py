"""① 수신·무결성 검증 (docs/QUIZ.md §2-①). 순수 함수 — LLM·DB 없음.

하류(근거 표시·문장 슬라이스)가 전부 앵커 offset을 믿고 동작하므로,
여기서 어긋난 데이터를 조기에 걸러 팀원에게 되돌릴 리포트를 만든다.
"""
from app.features.quiz.schemas import ParsedDocument, ParseReport, QuizGenConfig


def validate_document(doc: ParsedDocument, config: QuizGenConfig) -> ParseReport:
    report = ParseReport()

    if doc.parser_version not in config.supported_parser_versions:
        report.errors.append(
            f"지원하지 않는 파서 버전: {doc.parser_version} "
            f"(지원: {config.supported_parser_versions})"
        )
        return report  # 버전이 다르면 이후 검사는 무의미

    chunk_by_index = {c.index: c for c in doc.chunks}

    # 목차 ↔ 조각 매핑 실존 검사 (하드 실패 — 문항 귀속 불가)
    seen: set[int] = set()
    for toc in doc.tocs:
        for ci in toc.chunk_indexes:
            if ci not in chunk_by_index:
                report.errors.append(f"목차 {toc.index}가 존재하지 않는 조각 #{ci}를 참조")
            elif ci in seen:
                report.errors.append(f"조각 #{ci}가 여러 목차에 중복 배정")
            seen.add(ci)

    unassigned = set(chunk_by_index) - seen
    if unassigned:
        report.warnings.append(f"미배정 조각 {len(unassigned)}개: {sorted(unassigned)}")

    for chunk in doc.chunks:
        _validate_chunk(chunk, report)

    return report


def _validate_chunk(chunk, report: ParseReport) -> None:
    n = len(chunk.raw_text)
    prev_end = 0
    for i, a in enumerate(chunk.sentences):
        if not (0 <= a.start < a.end <= n):
            report.errors.append(
                f"조각 #{chunk.index} 문장 {i}: offset [{a.start},{a.end})가 원문({n}자) 밖"
            )
            continue
        if a.start < prev_end:
            report.warnings.append(f"조각 #{chunk.index} 문장 {i}: 앞 문장과 겹침")
        prev_end = a.end

    # 커버리지: 앵커가 원문 끝까지 닿는지 (파서의 '커버리지 100%' 주장 검증)
    if chunk.sentences and prev_end < n * 0.95:
        report.warnings.append(
            f"조각 #{chunk.index}: 앵커 커버리지 {prev_end}/{n}자 — 뒷부분 문장 누락 의심"
        )

    for f in chunk.figures:
        if not (0 <= f.offset <= n):
            report.warnings.append(f"조각 #{chunk.index} 그림(p.{f.page}): offset {f.offset}이 원문 밖")
