// 좌측 커리큘럼 목차 — 어디쯤 왔는지가 늘 보이게.
//
// 자료 → 목차 → 화면을 전체 페이지로 넘나들면 **지금 어디인지**가 매번 사라진다.
// 목차를 옆에 고정해 두면 이동이 한 번에 끝나고, 순서가 눈에 남는다.
//
// 표시는 전부 데이터에서 나온다. 화면이 판정하는 건 "펼쳤나" 하나뿐이다.
//   상태 아이콘  section.status (백엔드의 숙련도 판정)
//   🔁 복습      section.needsReview (망각곡선. 맞힌 적 있는데 잊혀가는 것)
//   🔒 잠김      chapter.formativeReady — **평가에만 걸린다**
//
// ⚠️ integration 목업은 **안 배운 강의**를 잠갔다(`cursor-not-allowed`). 그쪽이
//    이탈을 겪은 자리다. 학습 화면은 순서와 무관하게 언제나 열려 있다.
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowUUpLeftIcon,
  ArrowsClockwiseIcon,
  CaretDownIcon,
  CaretUpIcon,
  CheckCircleIcon,
  CircleIcon,
  LockSimpleIcon,
  NotePencilIcon,
  PlayCircleIcon,
} from "@phosphor-icons/react";

import type { SectionOut } from "@/features/curriculum/api/curriculum";
import { useChapter, useDocument } from "@/features/curriculum/queries/useCurriculum";

const base = (docId: string) => `/curriculum/${encodeURIComponent(docId)}`;

/** 화면 하나의 상태 아이콘. 색과 모양은 백엔드 판정을 그대로 옮긴 것이다. */
function SectionIcon({ s }: { s: SectionOut }) {
  // 보충 화면은 상태보다 **출처**가 먼저다 — 왜 여기 있는지가 안 보이면
  // 교재에 원래 있던 화면이라고 오해한다.
  if (s.inserted && s.attempts === 0)
    return <ArrowUUpLeftIcon weight="bold" className="shrink-0 text-lg text-violet-600" />;
  if (s.needsReview)
    return <ArrowsClockwiseIcon weight="bold" className="shrink-0 text-lg text-amber-600" />;
  if (s.status === "solid")
    return <CheckCircleIcon weight="fill" className="shrink-0 text-lg text-[#10b981]" />;
  if (s.attempts > 0)
    return <PlayCircleIcon weight="fill" className="shrink-0 text-lg text-accent" />;
  return <CircleIcon className="shrink-0 text-lg text-text-tertiary" />;
}

/** 펼친 목차 하나의 내용. 화면 목록은 펼칠 때 받아온다(목차마다 요청이 따로다). */
function ChapterBody({
  docId,
  index,
  currentSectionId,
  onFormative,
}: {
  docId: string;
  index: number;
  currentSectionId: string;
  onFormative: boolean;
}) {
  const { data, isLoading } = useChapter(docId, index);

  if (isLoading)
    return <p className="px-6 py-3 text-[0.8rem] text-text-tertiary">불러오는 중…</p>;
  if (!data) return null;

  return (
    <div className="py-1">
      {data.sections.map((s) => {
        const active = s.sectionId === currentSectionId;
        return (
          <Link
            key={s.sectionId}
            to={`${base(docId)}/sections/${s.sectionId}`}
            className={clsx(
              "flex items-center gap-2.5 px-6 py-2 transition-colors hover:bg-bg-secondary",
              active && "bg-accent/5",
              // 보충 화면은 살짝 들여 쓴다 — 원래 목차의 한 줄이 아니라
              // **앞 화면을 위해 끼운 것**이라는 게 눈으로 읽혀야 한다.
              s.inserted && "border-l-2 border-violet-300 bg-violet-50/40 pl-[22px]",
            )}
          >
            <SectionIcon s={s} />
            <span
              className={clsx(
                "flex-1 truncate text-[0.85rem]",
                active ? "font-semibold text-accent" : "text-text-secondary",
              )}
            >
              {s.title}
            </span>
          </Link>
        );
      })}

      {/* 목차의 마지막은 언제나 단원 평가. 잠겨 있어도 자리는 지킨다 —
          끝이 보여야 진도가 의미를 갖는다. */}
      <Link
        to={`${base(docId)}/chapters/${index}/formative`}
        className={clsx(
          "flex items-center gap-2.5 border-t border-dashed border-border-primary px-6 py-2.5 transition-colors hover:bg-bg-secondary",
          onFormative && "bg-accent/5",
          !data.formativeReady && "opacity-70",
        )}
      >
        {data.formativeReady ? (
          <NotePencilIcon weight="fill" className="shrink-0 text-lg text-accent" />
        ) : (
          <LockSimpleIcon className="shrink-0 text-lg text-text-tertiary" />
        )}
        <span
          className={clsx(
            "flex-1 truncate text-[0.85rem]",
            onFormative ? "font-semibold text-accent" : "text-text-secondary",
          )}
        >
          단원 평가
        </span>
      </Link>
    </div>
  );
}

export function OutlinePanel({ docId }: { docId: string }) {
  const { pathname } = useLocation();
  const { data } = useDocument(docId);

  // 지금 보고 있는 곳. 경로에서 읽는다 — 레이아웃은 자식 라우트 파라미터를 못 본다.
  const secMatch = pathname.match(/\/sections\/([^/]+)/);
  const chMatch = pathname.match(/\/chapters\/(\d+)/);
  const currentSectionId = secMatch ? decodeURIComponent(secMatch[1]) : "";
  const currentChapter = chMatch ? Number(chMatch[1]) : null;
  const onFormative = pathname.endsWith("/formative");
  const onReview = pathname.endsWith("/review");

  // 지금 있는 목차는 기본으로 펼친다. 절에 들어와 있으면 그 절이 속한 목차를
  // 알아야 하는데, 목록만으로는 모른다 — 그래서 목차 화면에서 온 것만 편다.
  const [open, setOpen] = useState<Set<number>>(
    () => new Set(currentChapter !== null ? [currentChapter] : [0]),
  );

  if (!data) return null;

  const toggle = (i: number) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  return (
    <aside className="hidden w-[268px] flex-shrink-0 flex-col border-r border-border-primary bg-white lg:flex">
      <div className="border-b border-border-primary px-5 py-4">
        <Link
          to={base(docId)}
          className="block truncate font-bold text-text-primary hover:text-accent"
          title={data.title}
        >
          📚 {data.title}
        </Link>
        <div className="mt-2 flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-border-primary">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${Math.round(data.readiness * 100)}%` }}
            />
          </div>
          <span className="text-[0.75rem] font-semibold text-text-secondary">
            준비도 {Math.round(data.readiness * 100)}%
          </span>
        </div>
        {/* 🔁 복습이 밀려 있으면 여기서 먼저 말한다. 목차를 다 펼쳐 봐야
            알 수 있으면 복습은 영영 안 하게 된다. */}
        {/* 숫자만 띄우면 아무도 안 누른다 — 갈 데가 있어야 복습이 일어난다.
            다만 **막지는 않는다**(integration은 전면 모달로 세웠다). */}
        <Link
          to={`${base(docId)}/review`}
          className={clsx(
            "mt-1.5 block text-[0.75rem] font-medium hover:underline",
            onReview && "font-bold",
            data.sectionsDue > 0 ? "text-amber-700" : "text-text-tertiary",
          )}
        >
          {data.sectionsDue > 0 ? `🔁 복습할 화면 ${data.sectionsDue}개 →` : "🔁 복습"}
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto">
        {data.chapters.map((ch) => {
          const isOpen = open.has(ch.index);
          const done = ch.sectionsTotal > 0 && ch.sectionsDone >= ch.sectionsTotal;
          return (
            <div key={ch.index} className="border-b border-border-primary">
              <button
                type="button"
                onClick={() => toggle(ch.index)}
                className={clsx(
                  "flex w-full items-center justify-between gap-2 px-5 py-3 text-left transition-colors",
                  isOpen ? "bg-white" : "bg-bg-secondary/60 hover:bg-bg-secondary",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    {/* ✚ 진단이 끼운 단원 — 교재에 없던 내용. 목차는 학습 내내
                        옆에 떠 있으므로, 여기서 구분이 안 되면 학습자는 이걸
                        교재 목차로 읽는다. */}
                    {ch.inserted && (
                      <span
                        title="진단에서 모른다고 하신 내용 — 교재에는 없습니다"
                        className="shrink-0 text-[0.75rem] font-bold text-accent"
                      >
                        ✚
                      </span>
                    )}
                    <span
                      className={clsx(
                        "truncate text-[0.875rem] font-bold",
                        currentChapter === ch.index ? "text-accent" : "text-text-primary",
                      )}
                    >
                      {ch.title}
                    </span>
                    {done && (
                      <CheckCircleIcon
                        weight="fill"
                        className="shrink-0 text-sm text-[#10b981]"
                      />
                    )}
                  </span>
                  <span className="mt-0.5 block text-[0.7rem] text-text-tertiary">
                    화면 {ch.sectionsDone}/{ch.sectionsTotal}
                    {ch.sectionsDue > 0 && <> · 🔁 {ch.sectionsDue}</>}
                    {ch.inserted && <> · 교재 밖</>}
                  </span>
                </span>
                {isOpen ? (
                  <CaretUpIcon className="shrink-0 text-text-tertiary" />
                ) : (
                  <CaretDownIcon className="shrink-0 text-text-tertiary" />
                )}
              </button>

              {isOpen && (
                <ChapterBody
                  docId={docId}
                  index={ch.index}
                  currentSectionId={currentSectionId}
                  onFormative={onFormative && currentChapter === ch.index}
                />
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
