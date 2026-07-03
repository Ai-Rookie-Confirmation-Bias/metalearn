/**
 * 수업 생성(Create Course) 위저드.
 *
 * ⚠️ 파킹 상태: 이 파일은 폐기된 "가입 전 온보딩" 프로토타입의 다단계 위저드
 *    껍데기(카드·스텝전환·slideIn·footer)를 재활용하기 위해 보존한 것이다.
 *    아래 스텝 내용(접점/목표/가치/시작)은 온보딩 시절의 placeholder이며,
 *    실제 수업 생성 스텝(자료 선택 → 범위/목표 → 생성)으로 교체 예정.
 *    참고 원본: UXUI_ANT/create_course.html
 */
import { useEffect, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  MagnifyingGlassIcon,
  ShareNetworkIcon,
  UsersThreeIcon,
  CompassIcon,
  CertificateIcon,
  BriefcaseIcon,
  BookOpenIcon,
  GraduationCapIcon,
  BrainIcon,
  MagicWandIcon,
  PenNibIcon,
  ArrowsClockwiseIcon,
  RocketLaunchIcon,
  type Icon,
} from "@phosphor-icons/react";

// [placeholder] STEP 1 접점
const SOURCES: { icon: Icon; label: string }[] = [
  { icon: MagnifyingGlassIcon, label: "검색하다가" },
  { icon: ShareNetworkIcon, label: "SNS에서" },
  { icon: UsersThreeIcon, label: "지인 추천" },
  { icon: CompassIcon, label: "그냥 둘러보다" },
];

// [placeholder] STEP 2 목표
const GOALS: { icon: Icon; label: string; phrase: string }[] = [
  { icon: CertificateIcon, label: "시험 · 자격증 합격", phrase: "시험 합격" },
  { icon: BriefcaseIcon, label: "실무 · 커리어 역량", phrase: "실무 역량" },
  { icon: BookOpenIcon, label: "새로운 분야 교양", phrase: "새로운 분야" },
  { icon: GraduationCapIcon, label: "학교 성적 향상", phrase: "성적 향상" },
];

// [placeholder] STEP 3 가치 루프
const LOOP: { icon: Icon; title: string; desc: string }[] = [
  { icon: BrainIcon, title: "진단", desc: "내가 어디서 막히는지 객관적으로 찾아요." },
  { icon: MagicWandIcon, title: "맞춤 생성", desc: "내 수준에 맞는 콘텐츠를 그때그때 만들어요." },
  { icon: PenNibIcon, title: "직접 인출", desc: "떠먹여주지 않고 직접 꺼내고 설명하게 해요." },
  { icon: ArrowsClockwiseIcon, title: "자동 복습", desc: "잊을 때쯤 다시 꺼내 오래 기억하게 해요." },
];

const cardBase = "border-2 rounded-xl bg-white cursor-pointer transition-all";
const cardState = (selected: boolean) =>
  selected
    ? "border-primary bg-black/[0.03]"
    : "border-border-primary hover:border-text-tertiary hover:bg-bg-secondary";

const NEXT_LABEL = ["다음 단계로 →", "다음 단계로 →", "이해했어요", "시작하기 🎉"];

// 마운트될 때마다 오른쪽에서 슬라이드-인 (전역 @keyframes 대신 순수 Tailwind transition).
// 부모에서 key={step}로 재마운트 → 매 스텝 애니메이션 재생.
function StepFade({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <div
      className={clsx(
        "transition-all duration-300 ease-out",
        shown ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8",
      )}
    >
      {children}
    </div>
  );
}

export function CreateCoursePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0); // 0..3
  const [source, setSource] = useState<number | null>(null);
  const [goal, setGoal] = useState<number | null>(null);

  const canNext = step === 0 ? source !== null : step === 1 ? goal !== null : true;
  const goalPhrase = goal !== null ? GOALS[goal].phrase : "목표";

  const back = () => (step === 0 ? navigate("/") : setStep((s) => s - 1));
  const next = () => {
    if (!canNext) return;
    if (step === 3) {
      navigate("/login");
      return;
    }
    setStep((s) => s + 1);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-secondary px-4">
      <div className="w-full max-w-[600px] bg-white rounded-2xl border border-border-primary shadow-lg p-12 max-[480px]:p-6 relative overflow-hidden">
        {/* key={step}로 매 스텝 재마운트 → 각 스텝이 슬라이드-인 */}
        <StepFade key={step}>
          <div className="text-sm font-semibold text-accent mb-4">STEP {step + 1} / 4</div>

          {step === 0 && (
            <>
              <h2 className="text-[1.75rem] font-bold text-primary mb-2 tracking-tight">
                어떤 경로로 메타런에 오셨어요?
              </h2>
              <p className="text-[0.95rem] text-text-secondary mb-10">가볍게 하나만 골라주세요.</p>
              <div className="grid grid-cols-2 max-[480px]:grid-cols-1 gap-4 mb-12">
                {SOURCES.map((o, i) => (
                  <button
                    key={o.label}
                    onClick={() => setSource(i)}
                    className={clsx(
                      cardBase,
                      cardState(source === i),
                      "flex flex-col items-center text-center px-4 py-6",
                    )}
                  >
                    <o.icon className="text-[2.5rem] text-primary mb-4" />
                    <span className="font-semibold text-base text-text-primary">{o.label}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h2 className="text-[1.75rem] font-bold text-primary mb-2 tracking-tight">
                무엇을 이루고 싶으세요?
              </h2>
              <p className="text-[0.95rem] text-text-secondary mb-10">
                목표에 맞춰 학습을 안내해드릴게요.
              </p>
              <div className="flex flex-col gap-3 mb-12">
                {GOALS.map((o, i) => (
                  <button
                    key={o.label}
                    onClick={() => setGoal(i)}
                    className={clsx(
                      cardBase,
                      cardState(goal === i),
                      "flex flex-row items-center gap-4 text-left px-6 py-4",
                    )}
                  >
                    <o.icon className="text-[1.75rem] text-primary shrink-0" />
                    <span className="font-semibold text-base text-text-primary">{o.label}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="text-[1.75rem] font-bold text-primary mb-2 tracking-tight">
                메타런은 <span className="text-accent">{goalPhrase}</span>을 이렇게 도와줘요
              </h2>
              <p className="text-[0.95rem] text-text-secondary mb-10">
                떠먹여주는 게 아니라, 스스로 꺼내게 만드는 학습 루프예요.
              </p>
              <div className="flex flex-col gap-3 mb-12">
                {LOOP.map((o) => (
                  <div key={o.title} className="flex items-center gap-4 px-6 py-4 rounded-xl bg-bg-secondary">
                    <o.icon className="text-[1.75rem] text-primary shrink-0" />
                    <div>
                      <div className="font-semibold text-base text-text-primary">{o.title}</div>
                      <div className="text-[0.85rem] text-text-secondary mt-1">{o.desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="text-[1.75rem] font-bold text-primary mb-2 tracking-tight">
                이제 시작할 준비가 됐어요!
              </h2>
              <p className="text-[0.95rem] text-text-secondary mb-10">
                메타런과 함께 <span className="text-accent">{goalPhrase}</span>에 한 걸음씩 다가가 봐요.
              </p>
              <div className="flex flex-col items-center justify-center py-10 mb-12">
                <RocketLaunchIcon className="text-[5rem] text-accent" weight="fill" />
              </div>
            </>
          )}
        </StepFade>

        {/* footer (스텝 전환에도 고정) */}
        <div className="flex justify-between items-center border-t border-border-primary pt-6">
          <button
            onClick={back}
            className="flex items-center gap-2 text-[13.3333px] leading-[normal] text-text-secondary font-medium hover:text-primary transition-colors"
          >
            <ArrowLeftIcon /> {step === 0 ? "홈으로" : "이전"}
          </button>
          <button
            onClick={next}
            disabled={!canNext}
            className={clsx(
              "bg-primary text-white text-[13.3333px] leading-[normal] px-5 py-[0.6rem] rounded-xl font-semibold shadow-sm inline-flex items-center gap-2 transition-all",
              canNext
                ? "hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
                : "opacity-50 cursor-not-allowed",
            )}
          >
            {NEXT_LABEL[step]}
          </button>
        </div>
      </div>
    </div>
  );
}
