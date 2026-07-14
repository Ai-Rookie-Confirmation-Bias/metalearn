import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { RobotIcon, PaperPlaneRightIcon, XIcon } from "@phosphor-icons/react";

import type { AttemptResponse } from "@/features/learning/api/submitAttempt";
import type { SupplementResponse } from "@/features/learning/api/getSupplement";
import { getSectionNote, saveSectionNote } from "@/features/learning/api/sectionNote";
import { postTutorChat, type TutorChatTurn } from "@/features/learning/api/tutorChat";

// 오답 보충 상태(LearningPage가 소유) — loading 동안 "분석 중" 버블, ready면 진단+재설명 버블.
export type SupplementState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: SupplementResponse };

// 서버 채점 신호(cause/feedback)를 튜터의 적응형 코멘트로 변환.
function tutorMessage(signal: AttemptResponse | null | undefined): string {
  if (!signal) {
    return "위의 빈칸 문제나 객관식 퀴즈가 어렵다면 언제든 질문해 주세요! 정답 대신 스스로 떠올릴 수 있는 힌트를 드릴게요.";
  }
  if (signal.feedback?.comment) return signal.feedback.comment;
  switch (signal.cause?.type) {
    case "prerequisite":
      return "지금 막힌 건 이 개념 자체보다 선수 개념이 아직 약해서예요. 선행을 먼저 다지면 여기가 쉬워져요.";
    case "content":
      return "선수 개념은 충분해요. 이 개념 자체를 조금 더 볼까요? 위 설명을 다시 읽으면 도움이 돼요.";
    case "hold":
      return "아직 판단하기엔 시도가 적어요. 한 문제 더 풀어볼까요?";
    default:
      return signal.correct
        ? "좋아요! 정확히 이해했어요. 다음으로 가볼까요?"
        : "다시 한 번 시도해봐요. 필요하면 힌트를 드릴게요.";
  }
}

// 우측 플로팅 패널 — AI 튜터(적응형 코멘트 + 오답 재설명 + 근거 접지 Q&A) / 요약 노트 탭.
// 항상 떠 있지 않고 FAB로 여닫는다(LearningPage 소유) — 인출 학습이 주인공, 튜터는 보조.
export function AiTutorPanel({
  sectionId,
  signal,
  supplement,
  onClose,
}: {
  sectionId?: string | null;
  signal?: AttemptResponse | null;
  supplement?: SupplementState;
  onClose?: () => void;
}) {
  const [tab, setTab] = useState<"ai" | "note">("ai");
  const message = tutorMessage(signal);

  // 나의 요약 노트 — 절 단위 서버 저장(자기설명 흔적). 절 변경 시 로드.
  const [note, setNote] = useState("");
  const [noteState, setNoteState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [noteSavedAt, setNoteSavedAt] = useState<string | null>(null);
  useEffect(() => {
    setNote("");
    setNoteState("idle");
    setNoteSavedAt(null);
    if (!sectionId) return;
    let alive = true;
    getSectionNote(sectionId)
      .then((n) => {
        if (alive) {
          setNote(n.content);
          setNoteSavedAt(n.updatedAt);
        }
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [sectionId]);

  const saveNote = async () => {
    if (!sectionId || noteState === "saving") return;
    setNoteState("saving");
    try {
      const n = await saveSectionNote(sectionId, note);
      setNoteState("saved");
      setNoteSavedAt(n.updatedAt);
    } catch {
      setNoteState("error");
    }
  };

  // 채팅 Q&A — 서버 무저장, 절 단위 컨텍스트라 절이 바뀌면 리셋.
  const [chat, setChat] = useState<TutorChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setChat([]);
    setDraft("");
    setSending(false);
  }, [sectionId]);

  // 새 버블(채팅·보충) 도착 시 맨 아래로
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat, sending, supplement?.status]);

  const send = async () => {
    const text = draft.trim();
    if (!text || sending || !sectionId) return;
    const history = chat;
    setChat((c) => [...c, { role: "user", text }]);
    setDraft("");
    setSending(true);
    try {
      const res = await postTutorChat({ sectionId, message: text, history });
      setChat((c) => [...c, { role: "tutor", text: res.reply }]);
    } catch {
      setChat((c) => [
        ...c,
        { role: "tutor", text: "지금은 답변을 만들지 못했어요. 잠시 후 다시 물어봐 주세요." },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <aside className="flex h-full w-full flex-col bg-white">
      {/* 탭 + 닫기 */}
      <div className="flex items-center border-b border-border-primary">
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
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            aria-label="튜터 패널 닫기"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-text-tertiary transition-colors hover:bg-bg-secondary hover:text-text-primary"
          >
            <XIcon weight="bold" />
          </button>
        )}
      </div>

      {tab === "ai" ? (
        <>
          {/* AI 프로필 */}
          <div className="flex items-center gap-3 border-b border-border-primary px-6 py-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent text-xl text-white">
              <RobotIcon weight="fill" />
            </div>
            <div>
              <h4 className="text-[0.95rem] font-bold leading-tight text-primary">MetaLearn AI 튜터</h4>
              <span className="text-xs font-semibold text-[#10b981]">온라인</span>
            </div>
          </div>

          {/* 채팅 */}
          <div ref={scrollRef} className="flex flex-1 flex-col gap-4 overflow-y-auto bg-[#fafafa] p-6">
            <div className="flex max-w-[90%] flex-col gap-1 self-start">
              <div className="rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] leading-normal text-text-primary shadow-sm">
                {message}
              </div>
            </div>

            {/* 오답 맞춤 재설명(개입 사다리 ②) — 서버가 실제 오답을 분석해 생성 */}
            {supplement?.status === "loading" && (
              <div className="flex max-w-[90%] flex-col gap-1 self-start">
                <div className="animate-pulse rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] leading-normal text-text-tertiary shadow-sm">
                  방금 답안을 분석해서 맞춤 설명을 만들고 있어요…
                </div>
              </div>
            )}
            {supplement?.status === "ready" && (
              <>
                <div className="flex max-w-[90%] flex-col gap-1 self-start">
                  <div className="whitespace-pre-wrap break-keep rounded-2xl rounded-tl-[4px] border border-accent/40 bg-accent/5 px-4 py-3.5 text-[0.9rem] leading-relaxed text-text-primary shadow-sm">
                    <span className="mb-1 block text-[0.72rem] font-bold text-accent">
                      {supplement.data.misconception ? "오개념 진단" : "놓친 지점"}
                    </span>
                    {supplement.data.diagnosis}
                  </div>
                </div>
                <div className="flex max-w-[90%] flex-col gap-1 self-start">
                  <div className="whitespace-pre-wrap break-keep rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] leading-relaxed text-text-primary shadow-sm">
                    <span className="mb-1 block font-bold">
                      {supplement.data.title}
                    </span>
                    {supplement.data.body}
                  </div>
                  <span className="px-1 text-[0.7rem] text-text-tertiary">
                    {supplement.data.fallback
                      ? "원문 발췌"
                      : "내 답안 기반 맞춤 설명"}
                  </span>
                </div>
              </>
            )}

            {/* Q&A 대화 — 근거 접지 + 정답 비유출(서버 규칙) */}
            {chat.map((t, i) =>
              t.role === "user" ? (
                <div key={i} className="flex max-w-[90%] flex-col gap-1 self-end">
                  <div className="whitespace-pre-wrap break-keep rounded-2xl rounded-tr-[4px] bg-accent px-4 py-3.5 text-[0.9rem] leading-relaxed text-white shadow-sm">
                    {t.text}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex max-w-[90%] flex-col gap-1 self-start">
                  <div className="whitespace-pre-wrap break-keep rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] leading-relaxed text-text-primary shadow-sm">
                    {t.text}
                  </div>
                </div>
              ),
            )}
            {sending && (
              <div className="flex max-w-[90%] flex-col gap-1 self-start">
                <div className="animate-pulse rounded-2xl rounded-tl-[4px] border border-border-primary bg-white px-4 py-3.5 text-[0.9rem] text-text-tertiary shadow-sm">
                  생각하는 중…
                </div>
              </div>
            )}
          </div>

          {/* 입력 */}
          <div className="flex items-center gap-2 border-t border-border-primary bg-white p-4">
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.nativeEvent.isComposing) send();
              }}
              disabled={!sectionId}
              placeholder={sectionId ? "AI에게 질문하기..." : "절을 열면 질문할 수 있어요"}
              className="flex-1 rounded-full border border-border-primary bg-bg-secondary px-5 py-3 text-[0.9rem] text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-accent focus:bg-white disabled:opacity-60"
            />
            <button
              type="button"
              onClick={send}
              disabled={sending || !draft.trim() || !sectionId}
              aria-label="질문 보내기"
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent text-white transition-transform hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
            >
              <PaperPlaneRightIcon weight="fill" />
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between border-b border-border-primary bg-bg-secondary px-6 py-4">
            <span className="text-[0.8rem] font-medium text-text-tertiary">
              {noteState === "saving"
                ? "저장 중…"
                : noteState === "error"
                  ? "저장 실패 — 다시 시도해주세요"
                  : noteSavedAt
                    ? `마지막 저장: ${new Date(noteSavedAt).toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}`
                    : "아직 저장된 노트가 없어요"}
            </span>
            <button
              type="button"
              onClick={saveNote}
              disabled={!sectionId || noteState === "saving"}
              className="rounded-md bg-accent/10 px-3 py-1.5 text-[0.8rem] font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-50"
            >
              {noteState === "saved" ? "저장됨 ✓" : "저장하기"}
            </button>
          </div>
          <textarea
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
              if (noteState === "saved" || noteState === "error") setNoteState("idle");
            }}
            placeholder="학습한 내용을 나만의 언어로 요약해 보세요!"
            className="flex-1 resize-none p-6 text-[0.95rem] leading-relaxed text-text-primary outline-none placeholder:text-text-tertiary"
          />
        </>
      )}
    </aside>
  );
}
