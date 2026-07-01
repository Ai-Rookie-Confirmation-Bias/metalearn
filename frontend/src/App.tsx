import { Outlet, Link, useLocation } from "react-router-dom";
import { HexagonIcon } from "@phosphor-icons/react";

// 앱 셸: 모든 페이지 공통 글로벌 헤더(로고) + 페이지 콘텐츠 슬롯
export default function App() {
  // 인증 페이지에선 헤더 로그인 링크 숨김 (이미 그 페이지라 중복)
  const isAuthPage = useLocation().pathname === "/login";

  return (
    <>
      <header className="fixed left-0 top-0 z-[100] w-full py-8 pointer-events-none">
        <div className="mx-auto flex w-full max-w-[1200px] items-center justify-between px-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-2xl font-extrabold tracking-tight text-primary pointer-events-auto [text-shadow:0_2px_4px_rgba(255,255,255,0.8)]"
          >
            <HexagonIcon weight="fill" className="text-[2rem] text-accent" />
            <span>MetaLearn</span>
          </Link>
          {!isAuthPage && (
            <Link
              to="/login"
              className="pointer-events-auto rounded-xl border border-border-primary bg-white px-5 py-2 text-[0.9rem] font-semibold text-text-primary shadow-sm hover:bg-bg-secondary transition-colors"
            >
              로그인
            </Link>
          )}
        </div>
      </header>
      <Outlet />
    </>
  );
}
