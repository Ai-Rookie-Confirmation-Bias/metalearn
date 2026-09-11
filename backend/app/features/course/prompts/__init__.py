"""코스 층 프롬프트. 파일 하나가 물음 하나를 맡는다.

  gray    16' 회색지대 — "이걸 모르면 이 자료를 못 읽나"
  merge   16' 과목 이름 합치기 — 같은 과목이 여러 이름으로 온다
  cards   24 ③ 카드 4장 — 같은 개념을 네 형식으로
  probe   24 ⑤ 확인 문항 — 정답은 우리가 정하고 LLM은 오답만 만든다
"""
from . import cards, gray, merge, probe  # noqa: F401
