import { Link, Outlet } from "react-router-dom";

export default function App() {
  return (
    <div>
      <header
        style={{
          padding: "1rem",
          borderBottom: "1px solid #eee",
          display: "flex",
          alignItems: "center",
          gap: "1.5rem",
        }}
      >
        <strong>MetaLearn</strong>
        <nav style={{ display: "flex", gap: "1rem", fontSize: "0.95rem" }}>
          <Link to="/">학습 (예시)</Link>
          <Link to="/seed">Seed 플로우</Link>
        </nav>
      </header>
      <main style={{ padding: "1rem" }}>
        <Outlet />
      </main>
    </div>
  );
}
