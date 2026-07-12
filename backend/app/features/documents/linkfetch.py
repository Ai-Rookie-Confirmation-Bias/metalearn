"""보조 링크 자료 수집 — URL fetch + HTML→평문 추출.

수업 생성 위저드 STEP 2의 링크 보조자료를 RAG 근거로 편입하기 위한 최소 경로:
  fetch(httpx) → HTML이면 본문 텍스트만 추출 → 호출측이 청킹·임베딩(ingest).
PDF 파이프라인(Document Parse)과 달리 외부 의존 없이 stdlib HTMLParser만 쓴다.
JS 렌더링이 필요한 SPA는 본문이 빈약할 수 있다 — v1 한계로 명시.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

_TIMEOUT = 20.0
_MAX_BYTES = 5 * 1024 * 1024  # 응답 본문 상한 5MB — 폭주 방지
# 일부 사이트는 UA 없는 요청을 차단한다.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MetaLearnBot/1.0; +study-aid)"}

# 텍스트로 안 치는 컨테이너 — 스크립트·스타일과 내비게이션류 보일러플레이트.
_SKIP_TAGS = {"script", "style", "noscript", "svg", "head", "nav", "footer", "aside"}
# 블록 경계 태그 — 닫힐 때 줄바꿈을 넣어 문단 구조를 보존한다.
_BLOCK_TAGS = {
    "p", "div", "section", "article", "li", "tr", "br",
    "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        # 헤딩은 마크다운 헤딩으로 보존 — sectioning.split_sections가 절 경계로 쓴다.
        if self._skip_depth == 0 and tag in ("h1", "h2", "h3", "h4"):
            level = int(tag[1])
            self._parts.append("\n" + "#" * level + " ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if self._skip_depth == 0 and tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skip_depth == 0 and data.strip():
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        # 공백 정리: 줄 내 다중 공백 축약, 3연속 이상 개행 축약
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def html_to_text(html: str) -> tuple[str, str]:
    """HTML → (본문 평문, 제목). 헤딩은 마크다운 #으로 보존."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text(), parser.title


async def fetch_link_text(url: str) -> tuple[str, str]:
    """URL을 가져와 (본문 텍스트, 제목)을 반환. 실패는 예외로 — 호출측이 기록.

    HTML이면 본문 추출, text/*면 그대로. 그 외 타입(PDF 등)은 v1 미지원.
    """
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, headers=_HEADERS
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        if len(resp.content) > _MAX_BYTES:
            raise ValueError(f"링크 응답이 너무 큽니다(>{_MAX_BYTES // 1024 // 1024}MB)")
        ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()

    if ctype in ("text/html", "application/xhtml+xml", ""):
        text, title = html_to_text(resp.text)
    elif ctype.startswith("text/"):
        text, title = resp.text, ""
    else:
        raise ValueError(f"지원하지 않는 링크 콘텐츠 타입: {ctype}")

    if len(text.strip()) < 80:
        raise ValueError("링크에서 충분한 본문을 추출하지 못했습니다(JS 렌더링 페이지일 수 있음).")
    return text, title
