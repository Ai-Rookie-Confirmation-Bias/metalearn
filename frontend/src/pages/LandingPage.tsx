import { useEffect, useRef, type ReactNode } from "react";
import { Link, useOutletContext } from "react-router-dom";

import type { LayoutContext } from "@/App";
import { clsx } from "clsx";
import { BrainIcon, TargetIcon, TrendUpIcon, CaretDownIcon } from "@phosphor-icons/react";

import { InteractiveDemo } from "@/pages/landing/InteractiveDemo";

// 우측(또는 좌측) 비주얼 박스: 아이콘 + 하단 뱃지
function VisualBox({ icon, badge }: { icon: ReactNode; badge: string }) {
  return (
    <div className="w-[300px] h-[400px] border-[3px] border-border-primary rounded-2xl flex flex-col items-center justify-center shadow-[0_25px_50px_-12px_rgba(0,0,0,0.1)] relative bg-[radial-gradient(circle_at_center,#ffffff_0%,#f9fafb_100%)]">
      {icon}
      <div className="absolute -bottom-4 bg-[#facc15] text-[#854d0e] font-extrabold px-6 py-2 rounded-full shadow-md text-[0.9rem]">
        {badge}
      </div>
    </div>
  );
}

// 지그재그 기능 소개 섹션 (reverse 시 비주얼/텍스트 위치 교환)
function FeatureSection({
  title,
  desc,
  visual,
  reverse = false,
}: {
  title: ReactNode;
  desc: ReactNode;
  visual: ReactNode;
  reverse?: boolean;
}) {
  const text = (
    <div className="flex flex-col items-start max-[900px]:items-center max-[900px]:text-center">
      <h2 className="text-5xl font-extrabold tracking-[-0.04em] leading-[1.1] mb-6 text-[#4ade80]">
        {title}
      </h2>
      <p className="text-lg text-text-secondary leading-relaxed">{desc}</p>
    </div>
  );
  const vis = (
    <div
      className={clsx(
        "w-full flex relative max-[900px]:justify-center",
        reverse ? "justify-start" : "justify-end",
      )}
    >
      {visual}
    </div>
  );

  return (
    <section className="h-screen w-full snap-start snap-always flex flex-col justify-center relative">
      <div className="grid grid-cols-1 min-[900px]:grid-cols-2 gap-16 items-center max-w-[1200px] mx-auto px-8 w-full">
        {reverse ? (
          <>
            {vis}
            {text}
          </>
        ) : (
          <>
            {text}
            {vis}
          </>
        )}
      </div>
    </section>
  );
}

export function LandingPage() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const premiumRef = useRef<HTMLElement>(null);
  const { setHeaderHidden } = useOutletContext<LayoutContext>();

  // 네이비(프리미엄) 섹션이 화면에 들어오면 헤더를 위로 숨김 (검은 로고/버튼 안 보임 방지)
  useEffect(() => {
    const root = scrollRef.current;
    const target = premiumRef.current;
    if (!root || !target) return;
    const obs = new IntersectionObserver(
      ([entry]) => setHeaderHidden(entry.intersectionRatio > 0.5),
      { root, threshold: [0, 0.5, 1] },
    );
    obs.observe(target);
    return () => {
      obs.disconnect();
      setHeaderHidden(false);
    };
  }, [setHeaderHidden]);

  // 랜딩에선 창 스크롤을 잠가 모든 스크롤을 스냅 컨테이너 안에서만 일어나게
  // (원본 variables.css의 body{overflow:hidden} 역할 — 이게 없으면 크롬에서 창이 스크롤돼 스냅이 안 걸림)
  useEffect(() => {
    const prevBody = document.body.style.overflow;
    const prevHtml = document.documentElement.style.overflow;
    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevBody;
      document.documentElement.style.overflow = prevHtml;
    };
  }, []);

  // 마우스 휠만 가로채 한 섹션씩 이동 (트랙패드=작고 연속적인 델타는 CSS 스냅에 맡김).
  // Chrome 휠은 CSS 스냅이 잘 안 걸려서 JS로 보정.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let locked = false;

    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaY) < 50) return; // 트랙패드 → native 스냅
      e.preventDefault();
      if (locked) return;

      const h = el.clientHeight;
      const current = Math.round(el.scrollTop / h);
      const next = Math.max(0, Math.min(current + (e.deltaY > 0 ? 1 : -1), el.children.length - 1));
      if (next === current) return;

      locked = true;
      // 스무스 스크롤 중 mandatory 스냅이 끼어들어 출발점으로 되돌리는 크롬 버그 방지 → 잠시 스냅 끔
      el.style.scrollSnapType = "none";
      el.scrollTo({ top: next * h, behavior: "smooth" });

      const release = () => {
        el.style.scrollSnapType = ""; // Tailwind snap-mandatory 복귀
        locked = false;
        el.removeEventListener("scrollend", release);
      };
      el.addEventListener("scrollend", release);
      window.setTimeout(release, 800); // scrollend 미지원 폴백
    };

    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  return (
    <div ref={scrollRef} className="h-screen overflow-y-scroll snap-y snap-mandatory">
      {/* PAGE 1: 히어로 */}
      <section className="h-screen w-full snap-start snap-always flex flex-col justify-center relative">
        <div className="grid grid-cols-1 min-[900px]:grid-cols-2 gap-16 items-center max-w-[1200px] mx-auto px-8 w-full">
          <div className="flex flex-col items-start max-[900px]:items-center max-[900px]:text-center">
            <h1 className="text-[3.5rem] max-[900px]:text-5xl font-extrabold tracking-[-0.04em] leading-[1.1] mb-6 text-[#4ade80]">
              재밌고 효과적인
              <br />
              맞춤형 학습
            </h1>
            <p className="text-lg text-text-secondary mb-10 leading-relaxed">
              MetaLearn과 함께하는 학습은 재미있을 뿐 아니라,{" "}
              <strong>그 효과도 입증되었어요!</strong>
              <br />
              나의 학습 메타인지를 파악하고 실력을 레벨업 해보세요.
            </p>
            <div className="w-full max-w-[400px]">
              <Link
                to="/login"
                className="bg-primary text-white px-7 py-[0.8rem] text-[1.1rem] rounded-xl font-semibold shadow-sm inline-flex items-center justify-center w-full mb-3 hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md transition-all"
              >
                지금 시작하기
              </Link>
              <p className="text-[0.8rem] text-text-tertiary text-center">
                간단한 설문을 통해 맞춤형 학습 플랜을 추천받으세요.
              </p>
            </div>
          </div>

          <div className="w-full flex justify-end max-[900px]:justify-center relative">
            <InteractiveDemo />
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 text-text-tertiary animate-[bounce_2s_infinite]">
          <CaretDownIcon className="text-2xl" />
        </div>
      </section>

      {/* PAGE 2~4: 기능 소개 */}
      <FeatureSection
        title={
          <>
            완벽한
            <br />
            메타인지 분석
          </>
        }
        desc={
          <>
            내가 무엇을 알고 모르는지 정확히 진단합니다.
            <br />
            취약점을 집중 공략하여 불필요한 반복 학습 시간을 획기적으로 절약하세요.
          </>
        }
        visual={
          <VisualBox
            icon={<BrainIcon className="text-[5rem] text-[#4ade80]" />}
            badge="학습 효율 200% 증가"
          />
        }
      />

      <FeatureSection
        reverse
        title={
          <>
            목표 기반
            <br />
            학습 설계
          </>
        }
        desc={
          <>
            명확한 마일스톤을 설정하고 당신만의 최적화된 학습 경로를 생성하세요.
            <br />
            학습 진도율과 달성률을 대시보드에서 한눈에 파악할 수 있습니다.
          </>
        }
        visual={
          <VisualBox
            icon={<TargetIcon className="text-[5rem] text-[#4ade80]" />}
            badge="목표 달성률 87% 상승"
          />
        }
      />

      <FeatureSection
        title={
          <>
            꾸준한 학습
            <br />
            동기 자극
          </>
        }
        desc={
          <>
            게임화된 학습 기능, 재미있는 도전 과제, 그리고 친절한 AI 어시스턴트의 적시
            알림을 통해 매일매일 자연스럽게 학습 습관을 기를 수 있습니다.
          </>
        }
        visual={
          <VisualBox
            icon={<TrendUpIcon className="text-[5rem] text-[#4ade80]" />}
            badge="14일 연속 학습 달성"
          />
        }
      />

      {/* PAGE 5: 프리미엄 CTA */}
      <section
        ref={premiumRef}
        className="h-screen w-full snap-start snap-always flex flex-col justify-center items-center text-center relative bg-navy text-white"
      >
        <div className="flex flex-col items-center gap-10 max-w-[800px] px-8 z-[2]">
          <h2 className="text-[4.5rem] max-md:text-5xl font-black italic leading-[1.1] tracking-[-0.02em] uppercase">
            POWER UP WITH
            <br />
            <span className="bg-gradient-to-r from-[#4ade80] to-[#3b82f6] bg-clip-text text-transparent inline-block pr-[0.15em]">
              METALEARN PRO
            </span>
          </h2>
          <Link
            to="/login"
            className="bg-white text-navy px-10 py-4 rounded-xl text-[1.125rem] font-extrabold uppercase tracking-wider shadow-[0_10px_25px_rgba(255,255,255,0.2)] hover:scale-105 hover:shadow-[0_15px_35px_rgba(255,255,255,0.3)] transition-all"
          >
            1주 무료 체험하기
          </Link>
        </div>

        <footer className="absolute bottom-0 w-full p-8 text-center">
          <p className="text-white/40 text-[0.85rem]">
            © 2026 MetaLearn. All rights reserved. &nbsp;|&nbsp;{" "}
            <a href="#" className="text-white/60 hover:text-white">
              이용약관
            </a>{" "}
            &nbsp;|&nbsp;{" "}
            <a href="#" className="text-white/60 hover:text-white">
              개인정보처리방침
            </a>
          </p>
        </footer>
      </section>
    </div>
  );
}
