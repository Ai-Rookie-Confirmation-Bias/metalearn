import { NavLink, Outlet } from "react-router-dom";
import { clsx } from "clsx";
import {
  HexagonIcon,
  BooksIcon,
  ChartLineUpIcon,
  GearIcon,
  LightningIcon,
  MagnifyingGlassIcon,
  BellIcon,
  ArrowsClockwiseIcon,
  type Icon,
} from "@phosphor-icons/react";

// 로그인 후 공통 셸: 좌측 사이드바(고정) + 상단 검색바 + 본문 슬롯.
// 사이드바는 안 사라지고 <Outlet/> 본문만 라우트에 따라 교체됨.

const NAV: { to: string; label: string; icon: Icon }[] = [
  { to: "/library", label: "나의 책장", icon: BooksIcon },
  { to: "/review", label: "복습", icon: ArrowsClockwiseIcon },
  { to: "/analysis", label: "메타인지 분석", icon: ChartLineUpIcon },
  { to: "/settings", label: "설정", icon: GearIcon },
];

export default function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-secondary">
      {/* 사이드바 */}
      <aside className="flex w-[280px] flex-shrink-0 flex-col border-r border-border-primary bg-white">
        <div className="p-8">
          <div className="flex items-center gap-2 text-2xl font-extrabold tracking-tight text-primary">
            <HexagonIcon weight="fill" className="text-[2rem] text-accent" />
            <span>MetaLearn</span>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-2 px-6">
          {NAV.map(({ to, label, icon: IconCmp }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 rounded-xl px-4 py-3.5 font-semibold transition-colors",
                  isActive
                    ? "bg-accent/10 text-accent"
                    : "text-text-secondary hover:bg-bg-secondary hover:text-primary",
                )
              }
            >
              <IconCmp className="text-[1.25rem]" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-6">
          <div className="rounded-2xl border border-border-primary bg-bg-secondary p-5">
            <LightningIcon weight="fill" className="mb-2 block text-[1.5rem] text-accent" />
            <h5 className="mb-1 text-[0.95rem] font-bold text-text-primary">Pro로 업그레이드</h5>
            <p className="text-[0.8rem] leading-snug text-text-secondary">
              무제한 AI 학습 분석을 경험하세요.
            </p>
          </div>
        </div>
      </aside>

      {/* 메인 영역 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 상단바 */}
        <header className="sticky top-0 z-[5] flex h-20 flex-shrink-0 items-center justify-between border-b border-border-primary bg-white px-12">
          <div className="flex w-[350px] items-center gap-2 rounded-full border border-transparent bg-bg-secondary px-4 py-3 transition-colors focus-within:border-accent">
            <MagnifyingGlassIcon className="text-[1.125rem] text-text-tertiary" />
            <input
              type="text"
              placeholder="어떤 강의나 목표를 찾고 계신가요?"
              className="w-full bg-transparent text-[0.95rem] text-text-primary placeholder:text-text-tertiary focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-6">
            <button
              type="button"
              className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-secondary text-[1.25rem] text-text-secondary transition-colors hover:bg-[#e5e7eb] hover:text-primary"
            >
              <BellIcon />
            </button>
            <div className="flex cursor-pointer items-center gap-3">
              <img
                src="https://ui-avatars.com/api/?name=User&background=2563eb&color=fff"
                alt="프로필"
                className="h-9 w-9 rounded-full"
              />
              <span className="text-[0.95rem] font-semibold text-text-primary">학습자님</span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
