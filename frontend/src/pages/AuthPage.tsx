import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";

import { fetchProviders, startLogin, type Provider } from "@/features/auth/api";

// 구글 공식 4색 G 로고 (Phosphor는 단색이라 공식 SVG 인라인)
function GoogleG({ className = "h-[1.15rem] w-[1.15rem]" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  );
}

// "최근에 로그인했어요" 말풍선 (버튼 위쪽, 꼬리 아래로 — 모바일까지 안전)
function RecentBadge() {
  return (
    <span className="pointer-events-none absolute bottom-full right-2 z-20 mb-2 whitespace-nowrap rounded-lg bg-[#2b2b2b] px-2.5 py-1.5 text-[0.7rem] font-semibold text-white shadow-md">
      최근에 로그인했어요
      <span className="absolute right-4 top-full h-2 w-2 -translate-y-1/2 rotate-45 bg-[#2b2b2b]" />
    </span>
  );
}

// 소셜 인증 페이지 (소셜만 → 로그인=가입).
// localStorage['ml_last_provider']로 표시 분기:
//   - 없음        → 첫 방문: 가입 문구
//   - google/naver → 재방문: 로그인 문구 + 해당 버튼에 "최근 로그인" 뱃지
//   (그 플래그는 로그인 성공 후 /auth/callback에서 심는다)
export function AuthPage() {
  const lastProvider = localStorage.getItem("ml_last_provider"); // "google" | "naver" | null
  const returning = lastProvider !== null;

  // 자격증명이 없는 제공자는 눌러도 503만 돌아온다 — 서버에 물어보고 잠근다.
  // 응답이 오기 전(isPending)에는 잠그지 않는다. 첫 화면에서 버튼이 회색으로
  // 떴다가 켜지면 고장 난 것처럼 보인다.
  const { data: providers } = useQuery({
    queryKey: ["auth", "providers"],
    queryFn: fetchProviders,
    staleTime: Infinity, // .env를 고치면 백엔드를 재시작한다. 그때 새로고침된다
  });
  const enabled = (p: Provider) => providers?.[p] !== false;

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-[360px] flex flex-col">
        <h1 className="text-2xl font-bold text-primary tracking-tight text-center">
          {returning ? "다시 오셨어요" : "메타런 시작하기"}
        </h1>
        <p className="text-[0.95rem] text-text-secondary mt-2 mb-8 text-center">
          {returning
            ? "소셜 계정으로 로그인하세요."
            : "소셜 계정으로 3초 만에 가입하세요."}
        </p>

        <div className="flex flex-col gap-3">
          <button
            type="button"
            disabled={!enabled("google")}
            onClick={() => startLogin("google")}
            className={clsx(
              "relative w-full flex items-center justify-center gap-3 py-3 rounded-xl border border-border-primary bg-white text-[0.95rem] font-semibold text-text-primary shadow-sm transition-all",
              enabled("google")
                ? "hover:bg-bg-secondary hover:shadow-md"
                : "cursor-not-allowed opacity-50",
            )}
          >
            <GoogleG />
            Google로 계속하기
            {lastProvider === "google" && <RecentBadge />}
          </button>

          <button
            type="button"
            disabled={!enabled("naver")}
            onClick={() => startLogin("naver")}
            className={clsx(
              "relative w-full flex items-center justify-center gap-3 py-3 rounded-xl bg-[#03C75A] text-[0.95rem] font-semibold text-white shadow-sm transition-all",
              enabled("naver")
                ? "hover:brightness-95 hover:shadow-md"
                : "cursor-not-allowed opacity-50",
            )}
          >
            <span className="text-[1.15rem] font-black leading-none">N</span>
            네이버로 계속하기
            {lastProvider === "naver" && <RecentBadge />}
          </button>
        </div>

        {providers && !enabled("naver") && (
          <p className="text-[0.8rem] text-text-tertiary text-center mt-4">
            네이버 로그인은 아직 준비 중이에요.
          </p>
        )}

        <p className="text-[0.8rem] text-text-tertiary text-center mt-6 leading-relaxed">
          계속하면 이용약관과 개인정보처리방침에
          <br />
          동의하게 됩니다.
        </p>
      </div>
    </div>
  );
}
