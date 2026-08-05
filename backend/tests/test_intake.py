from app.features.quiz.intake import validate_document
from app.features.quiz.schemas import QuizGenConfig


def test_fixture_passes_validation(parsed_doc):
    report = validate_document(parsed_doc, QuizGenConfig())
    assert report.ok, report.errors


def test_unsupported_parser_version_hard_fails(parsed_doc):
    doc = parsed_doc.model_copy(update={"parser_version": "9.9"})
    report = validate_document(doc, QuizGenConfig())
    assert not report.ok
    assert "파서 버전" in report.errors[0]


def test_out_of_range_anchor_is_error(parsed_doc):
    doc = parsed_doc.model_copy(deep=True)
    doc.chunks[0].sentences[0].end = len(doc.chunks[0].raw_text) + 100
    report = validate_document(doc, QuizGenConfig())
    assert any("원문" in e and "밖" in e for e in report.errors)


def test_toc_referencing_missing_chunk_is_error(parsed_doc):
    doc = parsed_doc.model_copy(deep=True)
    doc.tocs[0].chunk_indexes.append(999)
    report = validate_document(doc, QuizGenConfig())
    assert any("존재하지 않는 조각" in e for e in report.errors)


def test_unassigned_chunk_is_warning(parsed_doc):
    doc = parsed_doc.model_copy(deep=True)
    doc.tocs[1].chunk_indexes.remove(7)
    report = validate_document(doc, QuizGenConfig())
    assert report.ok
    assert any("미배정" in w for w in report.warnings)
