// 임시(테스트용) 추가 기능 레이아웃. 팀원이 만든 프론트(`/`)와 분리된 `/lab` 영역.
// 정식 통합 시 이 레이아웃을 제거하고 라우트를 평탄화하면 된다.
import { Link, NavLink, Outlet } from "react-router-dom";

const TABS = [
  { to: "/lab/materials", label: "1. 자료 섭취" },
  { to: "/lab/diagnostic", label: "2. 정밀 진단" },
  { to: "/lab/curriculum", label: "3. JIT 커리큘럼" },
];

export function ExperimentalLayout() {
  return (
    <div
      style={{
        border: "3px dashed #f59e0b",
        borderRadius: 12,
        padding: 16,
        background: "#fffbeb",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <div>
          <strong style={{ color: "#92400e" }}>
            🚧 임시 추가 기능 (테스트용 · 팀원 프론트와 분리)
          </strong>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "#92400e" }}>
            이 영역은 이번 세션에서 추가한 실험 기능입니다. 정식 아님.
          </p>
        </div>
        <Link
          to="/"
          style={{
            padding: "8px 12px",
            borderRadius: 8,
            background: "#1f2937",
            color: "#fff",
            textDecoration: "none",
            fontSize: 13,
            whiteSpace: "nowrap",
          }}
        >
          ← 팀원 프론트(홈)로
        </Link>
      </div>

      <nav style={{ display: "flex", gap: 10, margin: "14px 0" }}>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            style={({ isActive }) => ({
              padding: "6px 10px",
              borderRadius: 8,
              textDecoration: "none",
              fontSize: 14,
              background: isActive ? "#f59e0b" : "#fff",
              color: isActive ? "#1f2937" : "#92400e",
              border: "1px solid #f59e0b",
            })}
          >
            {t.label}
          </NavLink>
        ))}
      </nav>

      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          padding: 16,
          border: "1px solid #fde68a",
        }}
      >
        <Outlet />
      </div>
    </div>
  );
}

export function LabHome() {
  return (
    <div>
      <h2 style={{ marginTop: 0 }}>추가 기능 플로우</h2>
      <p style={{ color: "#666" }}>
        위 탭을 <strong>1 → 2 → 3</strong> 순서로 진행하면 자료 ID·세션 ID가 자동으로
        이어집니다.
      </p>
      <ol style={{ color: "#444", lineHeight: 1.8 }}>
        <li>자료 섭취: PDF 업로드 → 개념/선수지식 그래프 추출</li>
        <li>정밀 진단: BKT로 개념별 숙련도 확정</li>
        <li>JIT 커리큘럼: 점수에 맞춘 인출형 학습 자료 생성</li>
      </ol>
    </div>
  );
}
