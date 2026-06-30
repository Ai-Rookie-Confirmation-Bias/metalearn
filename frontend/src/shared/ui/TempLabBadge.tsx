// 임시(테스트용) 추가 기능 진입 배지. 팀원 프론트 위에 떠 있는 형태로,
// 디자인을 건드리지 않으면서 눈에 잘 띄게 한다. 정식 반영 시 이 파일과
// App.tsx의 사용처만 지우면 된다.
import { Link } from "react-router-dom";

export function TempLabBadge() {
  return (
    <Link
      to="/lab"
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        zIndex: 9999,
        padding: "10px 14px",
        borderRadius: 999,
        background: "#f59e0b",
        color: "#1f2937",
        fontWeight: 700,
        fontSize: 13,
        textDecoration: "none",
        boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
        border: "2px dashed #92400e",
      }}
    >
      🚧 임시 추가 기능 (테스트)
    </Link>
  );
}
