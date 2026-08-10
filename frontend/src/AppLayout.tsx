import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  HexagonIcon,
  BooksIcon,
  BookOpenIcon,
  ChartLineUpIcon,
  GearIcon,
  LightningIcon,
  MagnifyingGlassIcon,
  BellIcon,
  SignOutIcon,
  type Icon,
} from "@phosphor-icons/react";

import { fetchMe, logout } from "@/features/auth/api";
import { isLoggedIn } from "@/shared/api/client";

// 로그인 후 공통 셸: 좌측 사이드바(고정) + 상단 검색바 + 본문 슬롯.
// 사이드바는 안 사라지고 <Outlet/> 본문만 라우트에 따라 교체됨.

// ⚠️ **문제집은 여기 없다.** 문제은행은 자료에 딸린 것이라 책장 카드에서 연다
//    (`/quiz?course=<id>`). 사이드바에도 두면 진입점이 둘로 갈려서, 거기로 들어온
//    사람은 책장에서 이미 고른 자료를 과목 선택 화면에서 **또 고르게 된다.**
//    `/quiz` 라우트 자체는 살아 있다 — 카드의 딥링크와 "다른 과목"이 쓴다.
const NAV: { to: string; label: string; icon: Icon }[] = [
  { to: "/library", label: "나의 책장", icon: BooksIcon },
  // 미리 분석해 둔 CS 기초 자료. 내 책장과 **가른다** — 올린 적 없는 책이
  // "나의 책장"에 섞이면 그게 내 것인지 아닌지 흐려지고, 그 자료들은 진단도
  // 진도도 없어서 카드가 말할 수 있는 것 자체가 다르다.
  { to: "/shared", label: "기본 제공 자료", icon: BookOpenIcon },
  { to: "/analysis", label: "메타인지 분석", icon: ChartLineUpIcon },
  { to: "/settings", label: "설정", icon: GearIcon },
];

const avatarUrl = (name: string) =>
  `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=2563eb&color=fff`;

// 헤더 우측 계정 영역.
//
// 로그인 여부가 화면 어디에도 안 보이면 시연에서 확인할 방법이 없다 —
// 자료가 안 보일 때 그게 "로그인이 풀렸다"인지 "업로드가 실패했다"인지
// 가릴 수 없기 때문이다. 미로그인이면 dev 유저로 도는 중이라고 밝힌다.
function AccountMenu() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  const loggedIn = isLoggedIn();
  const { data: me } = useQuery({ queryKey: ["auth", "me"], queryFn: fetchMe });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const label = loggedIn ? (me?.name ?? me?.email ?? "…") : "학습자";

  const signOut = () => {
    logout();
    // 토큰이 사라지면 이제부터 dev 유저다. 캐시를 비우지 않으면 이전 계정의
    // 책장이 그대로 남아 로그아웃이 안 된 것처럼 보인다.
    qc.clear();
    navigate("/login");
  };

  return (
    <div ref={boxRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex cursor-pointer items-center gap-3"
      >
        <img src={avatarUrl(label)} alt="프로필" className="h-9 w-9 rounded-full" />
        <span className="text-[0.95rem] font-semibold text-text-primary">{label}님</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-[240px] overflow-hidden rounded-xl border border-border-primary bg-white shadow-lg">
          <div className="border-b border-border-primary px-4 py-3">
            <p className="truncate text-[0.9rem] font-semibold text-text-primary">
              {loggedIn ? (me?.email ?? "…") : "로그인하지 않았어요"}
            </p>
            <p className="mt-0.5 text-[0.8rem] text-text-tertiary">
              {loggedIn
                ? `${me?.provider ?? ""} 계정으로 로그인됨`
                : "체험 계정으로 보는 중이에요"}
            </p>
          </div>
          {loggedIn ? (
            <button
              type="button"
              onClick={signOut}
              className="flex w-full items-center gap-2 px-4 py-3 text-left text-[0.9rem] font-medium text-text-secondary transition-colors hover:bg-bg-secondary hover:text-primary"
            >
              <SignOutIcon className="text-[1.1rem]" />
              로그아웃
            </button>
          ) : (
            <button
              type="button"
              onClick={() => navigate("/login")}
              className="w-full px-4 py-3 text-left text-[0.9rem] font-semibold text-accent transition-colors hover:bg-bg-secondary"
            >
              로그인하기
            </button>
          )}
        </div>
      )}
    </div>
  );
}

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
            <AccountMenu />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
