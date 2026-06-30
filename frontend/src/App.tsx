import { Outlet } from "react-router-dom";

import { TempLabBadge } from "@/shared/ui/TempLabBadge";

export default function App() {
  return (
    <div>
      <header style={{ padding: "1rem", borderBottom: "1px solid #eee" }}>
        <strong>MetaLearn</strong>
      </header>
      <main style={{ padding: "1rem" }}>
        <Outlet />
      </main>
      {/* 임시: 추가 기능(/lab) 진입용 플로팅 배지. 팀원 프론트는 그대로 둠. */}
      <TempLabBadge />
    </div>
  );
}
