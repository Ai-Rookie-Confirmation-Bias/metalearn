import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";
import { ArrowRightIcon, CaretRightIcon } from "@phosphor-icons/react";

// 랜딩 히어로 전용 데모 컴포넌트. (UXUI_ANT/app.js의 DOM 조작을 React state로 환원)
const OPTIONS = [
  { letter: "A", text: "이해하지 못한 공식을 무작정 10번 반복해서 외웠다.", correct: false },
  { letter: "B", text: "모의고사를 푼 뒤, 틀린 문제의 원인을 파악하고 보완 계획을 세웠다.", correct: true },
  { letter: "C", text: "친구보다 점수가 높게 나와서 기분이 좋아졌다.", correct: false },
];

const tabBtn = (active: boolean) =>
  clsx(
    "text-sm font-semibold px-3 py-1.5 rounded-lg transition-all",
    active
      ? "text-primary bg-white shadow-sm border border-border-primary"
      : "text-text-tertiary",
  );

export function InteractiveDemo() {
  const [tab, setTab] = useState<0 | 1>(0);
  const [picked, setPicked] = useState<number | null>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const panel0 = useRef<HTMLDivElement>(null);
  const panel1 = useRef<HTMLDivElement>(null);

  // 활성 패널 높이에 맞춰 뷰포트 높이를 부드럽게 (app.js의 scrollHeight 로직)
  useEffect(() => {
    const active = (tab === 0 ? panel0 : panel1).current;
    if (viewportRef.current && active) {
      viewportRef.current.style.height = `${active.scrollHeight}px`;
    }
  }, [tab, picked]);

  const reset = () => {
    setPicked(null);
    setTab(0);
  };

  const answered = picked !== null;

  return (
    <div className="w-full max-w-[500px] bg-white border border-border-primary rounded-2xl shadow-[0_20px_40px_-10px_rgba(0,0,0,0.08)] overflow-hidden z-10">
      {/* header */}
      <div className="flex justify-between items-center px-6 py-4 border-b border-border-primary bg-bg-secondary">
        <span className="font-semibold text-[0.95rem] text-text-secondary">기본 체험해보기</span>
        <div className="flex items-center gap-2">
          <button onClick={() => setTab(0)} className={tabBtn(tab === 0)}>
            1. 개념
          </button>
          <CaretRightIcon className="text-text-tertiary" />
          <button onClick={() => setTab(1)} className={tabBtn(tab === 1)}>
            2. 퀴즈
          </button>
        </div>
      </div>

      {/* viewport */}
      <div
        ref={viewportRef}
        className="w-full overflow-hidden bg-white transition-[height] duration-500 ease-[cubic-bezier(0.25,1,0.5,1)]"
      >
        <div
          className="flex w-[200%] items-start transition-transform duration-500 ease-[cubic-bezier(0.25,1,0.5,1)]"
          style={{ transform: `translateX(-${tab * 50}%)` }}
        >
          {/* Panel 1: 개념 */}
          <div ref={panel0} className="w-1/2 p-8 shrink-0">
            <span className="inline-block px-[0.8rem] py-[0.3rem] bg-accent/10 text-accent rounded-full text-xs font-bold tracking-wider mb-4">
              개념 학습
            </span>
            <h4 className="text-xl font-bold mb-4 text-primary leading-tight">
              메타인지(Metacognition)란?
            </h4>
            <p className="text-[0.95rem] text-text-secondary leading-relaxed mb-6">
              메타인지는 <strong>'자신의 생각에 대해 생각하는 능력'</strong>입니다.
              <br />
              <br />
              단순히 지식을 아는 것을 넘어, 내가{" "}
              <em>'무엇을 알고 있고 무엇을 모르는지'</em> 객관적으로 파악함으로써 가장
              효율적인 학습 전략을 세울 수 있게 해줍니다.
            </p>
            <button
              onClick={() => setTab(1)}
              className="bg-primary text-white text-[13.3333px] leading-[normal] px-5 py-[0.6rem] rounded-xl font-semibold shadow-sm inline-flex items-center gap-2 hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md transition-all"
            >
              개념을 이해했어요 <ArrowRightIcon className="shrink-0" />
            </button>
          </div>

          {/* Panel 2: 퀴즈 */}
          <div ref={panel1} className="w-1/2 p-8 shrink-0">
            <span className="inline-block px-[0.8rem] py-[0.3rem] bg-[rgba(74,222,128,0.2)] text-[#166534] rounded-full text-xs font-bold tracking-wider mb-4">
              실전 테스트
            </span>
            <h4 className="text-xl font-bold mb-4 text-primary leading-tight">
              다음 중 메타인지가 잘 발휘된 상황은 무엇일까요?
            </h4>

            <div className="flex flex-col gap-2 mb-4">
              {OPTIONS.map((opt, i) => {
                const showCorrect = answered && opt.correct;
                const showWrong = answered && picked === i && !opt.correct;
                return (
                  <button
                    key={opt.letter}
                    onClick={() => !answered && setPicked(i)}
                    className={clsx(
                      "flex items-start gap-3 p-[0.875rem] border-2 rounded-xl bg-white text-left transition-all",
                      !answered &&
                        "border-border-primary hover:border-text-tertiary hover:bg-bg-secondary",
                      answered && "pointer-events-none opacity-60",
                      showCorrect && "border-emerald-500 bg-emerald-500/5 !opacity-100",
                      showWrong && "border-red-500 bg-red-500/5",
                      answered && !showCorrect && !showWrong && "border-border-primary",
                    )}
                  >
                    <span
                      className={clsx(
                        "inline-flex items-center justify-center w-6 h-6 rounded-md text-xs font-bold shrink-0",
                        showCorrect
                          ? "bg-emerald-500 text-white"
                          : showWrong
                            ? "bg-red-500 text-white"
                            : "bg-bg-secondary text-text-secondary",
                      )}
                    >
                      {opt.letter}
                    </span>
                    <span className="text-[0.9rem] text-text-primary leading-snug font-medium">
                      {opt.text}
                    </span>
                  </button>
                );
              })}
            </div>

            {answered && (
              <div
                className={clsx(
                  "p-4 rounded-xl animate-[fadeIn_0.3s_ease]",
                  OPTIONS[picked].correct
                    ? "bg-emerald-500/10 text-[#065f46]"
                    : "bg-red-500/10 text-[#991b1b]",
                )}
              >
                <div className="font-semibold text-[0.85rem] mb-2">
                  {OPTIONS[picked].correct
                    ? "🎉 정답입니다! 객관적인 자기 파악이 바로 메타인지의 핵심입니다."
                    : "💡 아쉽습니다. 메타인지는 '자신이 모른다는 사실을 인지'하고 보완하는 과정과 관련이 깊습니다."}
                </div>
                <button
                  onClick={reset}
                  className="text-text-secondary font-medium text-[0.95rem] hover:text-primary mt-2"
                >
                  다시 학습하기
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
