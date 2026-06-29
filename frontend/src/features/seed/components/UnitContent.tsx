/**
 * 커리큘럼 단원 학습 콘텐츠 렌더러
 * Solar가 생성한 마크다운을 간단히 HTML로 변환해 표시합니다.
 */
interface Props {
  content: string;
}

function parseMarkdown(md: string): string {
  return (
    md
      // ## 헤딩
      .replace(/^## (.+)$/gm, '<h3 class="unit-h3">$1</h3>')
      // **볼드**
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      // 불릿 리스트
      .replace(/^[-*] (.+)$/gm, "<li>$1</li>")
      // li 묶음 → ul
      .replace(/(<li>.*<\/li>\n?)+/gs, (m) => `<ul class="unit-ul">${m}</ul>`)
      // ⚠️ 등 이모지 + 볼드 패턴 보존
      .replace(/^(⚠️.+)$/gm, '<p class="unit-warn">$1</p>')
      // 줄바꿈 → <p>
      .replace(/\n\n+/g, "</p><p>")
      .replace(/^(?!<[hup])(.+)$/gm, "$1")
  );
}

export function UnitContent({ content }: Props) {
  const html = parseMarkdown(content);

  return (
    <div
      className="unit-content"
      style={{
        marginTop: "0.75rem",
        padding: "1rem 1.25rem",
        background: "#f8faff",
        borderRadius: 8,
        borderLeft: "3px solid #4a90e2",
        fontSize: "0.9rem",
        lineHeight: 1.75,
        color: "#222",
      }}
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: `<p>${html}</p>` }}
    />
  );
}
