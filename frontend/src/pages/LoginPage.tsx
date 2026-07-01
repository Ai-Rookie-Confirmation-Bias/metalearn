// 인증 화면 placeholder. 실제 로그인/가입 폼은 별도 작업.
export function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-secondary px-4">
      <div className="w-full max-w-[420px] bg-white rounded-2xl border border-border-primary shadow-lg p-12 text-center">
        <h1 className="text-[1.75rem] font-bold text-primary mb-2 tracking-tight">로그인 · 가입</h1>
        <p className="text-[0.95rem] text-text-secondary">준비 중이에요 — 인증 화면은 곧 추가됩니다.</p>
      </div>
    </div>
  );
}
