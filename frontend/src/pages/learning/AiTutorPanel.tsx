import { useState } from "react";
import { clsx } from "clsx";
import { RobotIcon, PaperPlaneRightIcon } from "@phosphor-icons/react";

// 우측 패널 — AI 튜터(채팅) / 나의 요약 노트 탭.
// ⚠️ 채팅은 아직 UI mock(전송 안 됨). 실제 튜터 연결은 백엔드(LLM) 단계.
export function AiTutorPanel() {
  const [tab, setTab] = useState<"ai" | "note">("ai");
  const [note, setNote] = useState("");

  return (
    <aside className="flex w-[340px] flex-shrink-0 flex-col border-l border-border-primary bg-white shadow-[-4px_0_15px_rgba(0,0,0,0.02)]">
      {/* 탭 */}
      <div className="flex border-b border-border-primary">
        {(
          [
            ["ai", "AI 튜터"],
            ["note", "나의 요약 노트"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={clsx(
              "flex-1 border-b-2 py-3.5 text-center text-[0.9rem] font-semibold transition-colors",
              tab === key
                ? "border-accent text-primary"
                : "border-transparent text-text-secondary hover:bg-bg-secondary",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "ai" ? (
        <>
          {/* AI 프로필 */}
          <div className="flex items-center gap-3 border-b border-border-primary px-6 py-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-xl text-white">
              <RobotIcon weight="fill" />
            </div>
            <div>
              <h4 className="text-[0.95rem] font-bold leading-tight text-primary">MetaLearn AI 튜터</h4>
              <span className="text-xs font-semibold text-[#10b981]">온라인</span>
            </div>
          </div>

          {/* 채팅 */}
          <div className="flex flex-1 flex-col gap-4 overflow-y-auto bg-[#fafafa] p-6">
            <div className="flex max-w-[90%] flex-col gap-1 self-start">
              <div className="rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] leading-normal text-text-primary shadow-sm">
                위의 빈칸 문제나 객관식 퀴즈가 어렵다면 언제든 저에게 질문해 주세요! 힌트를 드릴게요.
              </div>
              <span className="px-1 text-[0.7rem] text-text-tertiary">방금 전</span>
            </div>
          </div>

          {/* 입력 */}
          <div className="flex items-center gap-2 border-t border-border-primary bg-white p-4">
            <input
              type="text"
              placeholder="AI에게 질문하기..."
              className="flex-1 rounded-full border border-border-primary bg-bg-secondary px-5 py-3 text-[0.9rem] text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-accent focus:bg-white"
            />
            <button
              type="button"
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent text-white transition-transform hover:scale-105"
            >
              <PaperPlaneRightIcon weight="fill" />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between border-b border-border-primary bg-bg-secondary px-6 py-4">
            <span className="text-[0.8rem] font-medium text-text-tertiary">마지막 저장: 방금</span>
            <button
              type="button"
              className="rounded-md bg-accent/10 px-3 py-1.5 text-[0.8rem] font-semibold text-accent"
            >
              저장하기
            </button>
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="학습한 내용을 나만의 언어로 요약해 보세요!"
            className="flex-1 resize-none p-6 text-[0.95rem] leading-relaxed text-text-primary outline-none placeholder:text-text-tertiary"
          />
        </>
      )}
    </aside>
  );
}
