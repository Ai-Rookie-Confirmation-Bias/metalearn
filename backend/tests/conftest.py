import json
from pathlib import Path

import pytest

from app.features.quiz.schemas import ParsedDocument

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def parsed_doc() -> ParsedDocument:
    """팀원 파서 md 예시(정처기 실기노트)에서 추출한 실데이터 픽스처.

    조각 #0·#1(목차 0) + #7(목차 1). 조각 #0 앞부분엔 저자 인사말·광고가
    실제로 들어 있어 선별 로직의 리트머스가 된다.
    """
    data = json.loads((FIXTURES / "parsed_sample.json").read_text(encoding="utf-8"))
    return ParsedDocument.model_validate(data)
