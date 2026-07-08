import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { setToken } from "@/shared/api/client";

// 제공자 → 백엔드 콜백 → 여기로 302(#token=... 또는 #error=...).
// 해시(fragment)로 토큰을 받는 이유: 쿼리스트링과 달리 서버 로그/리퍼러에
// 남지 않아 토큰 노출 위험이 작다.
const ERROR_MESSAGES: Record<string, string> = {
  denied: "로그인을 취소했어요.",
  bad_state: "보안 검증에 실패했어요. 다시 시도해 주세요.",
  missing_code: "인증 코드가 없어요. 다시 시도해 주세요.",
  exchange_failed: "제공자 인증에 실패했어요. 잠시 후 다시 시도해 주세요.",
  unknown_provider: "지원하지 않는 로그인 제공자예요.",
  unknown: "로그인 중 문제가 발생했어요.",
};

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = params.get("token");
    const provider = params.get("provider");
    const err = params.get("error");

    if (token) {
      setToken(token);
      if (provider) localStorage.setItem("ml_last_provider", provider);
      // 토큰이 담긴 해시를 히스토리에서 지우고 이동.
      navigate("/library", { replace: true });
      return;
    }
    setError(err ?? "unknown");
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-[360px] flex flex-col items-center text-center">
        {error === null ? (
          <>
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-border-primary border-t-accent" />
            <p className="mt-4 text-[0.95rem] text-text-secondary">
              로그인 중이에요…
            </p>
          </>
        ) : (
          <>
            <h1 className="text-xl font-bold text-primary">로그인 실패</h1>
            <p className="mt-2 text-[0.95rem] text-text-secondary">
              {ERROR_MESSAGES[error] ?? ERROR_MESSAGES.unknown}
            </p>
            <button
              type="button"
              onClick={() => navigate("/login", { replace: true })}
              className="mt-6 rounded-xl border border-border-primary bg-white px-5 py-2.5 text-[0.9rem] font-semibold text-text-primary shadow-sm hover:bg-bg-secondary transition-colors"
            >
              로그인 화면으로
            </button>
          </>
        )}
      </div>
    </div>
  );
}
