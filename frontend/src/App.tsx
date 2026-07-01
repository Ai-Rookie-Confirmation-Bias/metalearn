import { useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { clsx } from "clsx";
import { HexagonIcon } from "@phosphor-icons/react";

export type LayoutContext = { setHeaderHidden: (hidden: boolean) => void };

// 앱 셸: 공통 글로벌 헤더 + 페이지 슬롯.
// 페이지가 필요 시 헤더를 위로 숨겼다(slide up) 다시 내릴 수 있음(예: 네이비 섹션).
export default function App() {
  // 인증/온보딩 페이지에선 헤더 로그인 링크 숨김 (이미 그 흐름 안이라 중복)
  const { pathname } = useLocation();
  const hideHeaderAuth = pathname === "/login" || pathname === "/welcome";
  const [headerHidden, setHeaderHidden] = useState(false);

  return (
    <>
      <header
        className={clsx(
          "fixed left-0 top-0 z-[100] w-full py-8 pointer-events-none transition-transform duration-300 ease-out",
          headerHidden && "-translate-y-full",
        )}
      >
        <div className="mx-auto flex w-full max-w-[1200px] items-center justify-between px-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-2xl font-extrabold tracking-tight text-primary pointer-events-auto [text-shadow:0_2px_4px_rgba(255,255,255,0.8)]"
          >
            <HexagonIcon weight="fill" className="text-[2rem] text-accent" />
            <span>MetaLearn</span>
          </Link>
          {!hideHeaderAuth && (
            <Link
              to="/login"
              className="pointer-events-auto rounded-xl border border-border-primary bg-white px-5 py-2 text-[0.9rem] font-semibold text-text-primary shadow-sm hover:bg-bg-secondary transition-colors"
            >
              로그인
            </Link>
          )}
        </div>
      </header>
      <Outlet context={{ setHeaderHidden } satisfies LayoutContext} />
    </>
  );
}
