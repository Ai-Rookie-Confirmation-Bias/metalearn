import { GearIcon } from "@phosphor-icons/react";

// 설정 — PATCH /me(프로필) 등 자리. 목업 미정 placeholder.
export function SettingsPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">설정</h2>
        <p className="text-text-secondary">프로필과 학습 환경을 관리하세요.</p>
      </div>

      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-primary bg-white py-24 text-center">
        <GearIcon className="mb-4 text-[3rem] text-text-tertiary" />
        <p className="font-semibold text-text-secondary">준비 중</p>
        <p className="mt-1 text-[0.9rem] text-text-tertiary">설정 화면을 준비하고 있어요.</p>
      </div>
    </div>
  );
}
