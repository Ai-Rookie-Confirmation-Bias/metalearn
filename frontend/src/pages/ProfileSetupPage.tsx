import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { SmileyIcon } from "@phosphor-icons/react";

// 첫 로그인 후 프로필 설정 — 닉네임(표시명)만 입력.
// ⚠️ 지금은 디자인 단계: 저장·실제 진입(가입 직후)은 OAuth 붙을 때. 제출 시 임시로 홈 이동.
export function ProfileSetupPage() {
  const navigate = useNavigate();
  const [nickname, setNickname] = useState("");
  const valid = nickname.trim().length > 0;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    // TODO: 닉네임 저장 후 앱으로 (OAuth/백엔드 연결 단계)
    navigate("/");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-white px-4">
      <form onSubmit={submit} className="w-full max-w-[380px] flex flex-col">
        <h1 className="text-2xl font-bold text-primary tracking-tight text-center">
          환영해요!
        </h1>
        <p className="text-[0.95rem] text-text-secondary mt-2 mb-8 text-center">
          메타런에서 어떻게 불러드릴까요?
        </p>

        {/* 닉네임 입력 (preflight가 인풋 스타일 리셋 → 명시) */}
        <div className="relative">
          <SmileyIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[1.25rem] text-text-tertiary" />
          <input
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            maxLength={20}
            autoFocus
            placeholder="닉네임을 입력하세요"
            className="w-full rounded-xl border border-border-primary bg-white py-3 pl-11 pr-4 text-[0.95rem] text-text-primary placeholder:text-text-tertiary shadow-sm transition-colors focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
          />
        </div>
        <p className="text-[0.8rem] text-text-tertiary mt-2 pl-1">
          언제든 바꿀 수 있어요.
        </p>

        <button
          type="submit"
          disabled={!valid}
          className={
            "mt-8 w-full rounded-xl py-3 text-[0.95rem] font-semibold text-white shadow-sm transition-all " +
            (valid
              ? "bg-primary hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
              : "bg-primary opacity-40 cursor-not-allowed")
          }
        >
          시작하기
        </button>
      </form>
    </div>
  );
}
