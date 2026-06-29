interface Props {
  mode?: "llm" | "local" | "fallback";
  note?: string | null;
}

export function GenerationBanner({ mode, note }: Props) {
  if (!note && mode === "llm") return null;

  const isFallback = mode === "fallback" || mode === "local";
  return (
    <div
      style={{
        marginBottom: "1rem",
        padding: "0.75rem 1rem",
        borderRadius: 8,
        background: isFallback ? "#fff8e6" : "#eef6ff",
        border: `1px solid ${isFallback ? "#e6c200" : "#99c2ff"}`,
        fontSize: "0.9rem",
        color: "#333",
      }}
    >
      <strong>{isFallback ? "⚠ 규칙 기반 fallback" : "✓ Solar 사용"}</strong>
      {note && <span style={{ marginLeft: 8 }}>{note}</span>}
    </div>
  );
}
