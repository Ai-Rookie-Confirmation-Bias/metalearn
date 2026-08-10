// [화면 1] 내 자료 — **지금 뭘 해야 하나**에 답한다.
//
// ⚠️ 목차를 나열하지 않는다. 왼쪽 사이드바(`OutlinePanel`)가 학습 내내 목차를
//    띄우고 있어서, 여기서 또 늘어놓으면 같은 목록이 한 화면에 둘이 된다.
//    실제로 겹치던 것: 제목 · 준비도 · 단원 제목 · 화면 n/m · 책장에 있음 · 복습 n.
//
//    **왼쪽은 이동, 여기는 판단.** 이 페이지만 가진 것(근거 파일 · ⚡ 이유 ·
//    가장 약함 · 분량 조정)이 목록에 묻혀 있었는데, 목록을 걷어내면 그게 본문이
//    된다. "목차가 뭐가 있나"는 왼쪽이 이미 늘 답하고 있는 질문이다.
//
// 목차 자체는 교재 그대로 두고 분량과 상태만 바뀐다 — 진단이 좋든 나쁘든 시험
// 범위는 교재 전체이고, 목차가 흔들리면 어디쯤 왔는지 감각이 사라진다.
import { Link, useParams } from "react-router-dom";
import { useEffect, useRef } from "react";
import {
  ArrowRightIcon,
  ArrowsClockwiseIcon,
  CheckCircleIcon,
  PlayCircleIcon,
} from "@phosphor-icons/react";

import {
  KIND_LABEL,
  prewarm,
  type AttemptKind,
  type ChapterBrief,
  type DocumentOut,
} from "@/features/curriculum/api/curriculum";
import {
  Bar,
  ModeBadge,
  Reason,
  StatusBadge,
  pct,
} from "@/features/curriculum/components/bits";
import {
  useChapter,
  useDocument,
  useDocuments,
} from "@/features/curriculum/queries/useCurriculum";
import { DiagnosticBanner } from "@/features/diagnostic/DiagnosticBanner";

function Picker() {
  const { data, isLoading } = useDocuments();
  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (!data?.length)
    return (
      <p className="p-8 text-text-secondary">
        올린 자료가 없습니다. 백엔드 <code>tests/fixtures</code>에 파싱 결과
        md를 넣어주세요.
      </p>
    );
  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-xl font-bold text-text-primary">내 자료</h1>
      <ul className="space-y-2">
        {data.map((id) => (
          <li key={id}>
            <Link
              to={`/curriculum/${encodeURIComponent(id)}`}
              className="block rounded-lg border border-border-primary px-4 py-3 font-medium hover:bg-bg-secondary"
            >
              {id}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 이어서 할 단원 — **앞에서부터 처음으로 안 끝난 것.**
 *
 * "가장 약한 단원"을 먼저 주지 않는다. 약한 곳은 대개 앞 단원을 안 봐서 약한
 * 것이고, 순서를 건너뛰게 하면 선수 관계가 깨진다. 약한 곳은 아래 "눈여겨볼
 * 곳"에서 따로 짚는다.
 */
function nextChapter(data: DocumentOut): ChapterBrief | null {
  return (
    data.chapters.find((ch) => ch.sectionsDone < ch.sectionsTotal) ??
    data.chapters[0] ??
    null
  );
}

/** 그 단원 안에서 이어서 열 화면.
 *
 * 단원까지만 보내도 되지만, 그러면 학습자가 목차에서 한 번 더 고른다. 이 화면이
 * 하려는 일이 "지금 뭘 해야 하나"에 답하는 것이라 **끝까지 데려간다.**
 * 단원 상세를 한 번 더 부르는 값은 그만큼 한다.
 */
function NextUp({ doc, chapter }: { doc: DocumentOut; chapter: ChapterBrief }) {
  const { data } = useChapter(doc.docId, chapter.index);
  const base = `/curriculum/${encodeURIComponent(doc.docId)}`;

  // 아직 안 푼 화면 → 없으면 복습이 밀린 화면 → 그것도 없으면 첫 화면.
  const section =
    data?.sections.find((s) => s.attempts === 0) ??
    data?.sections.find((s) => s.needsReview) ??
    data?.sections[0];

  const to = section
    ? `${base}/sections/${encodeURIComponent(section.sectionId)}`
    : `${base}/chapters/${chapter.index}`;

  return (
    <section className="rounded-2xl border border-accent/30 bg-accent/[0.04] p-5">
      <p className="mb-2 text-[0.7rem] font-bold tracking-wide text-accent">
        이어서 할 것
      </p>

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[0.78rem] text-text-tertiary">{chapter.title}</p>
          <h2 className="mt-0.5 truncate text-[1.15rem] font-bold text-text-primary">
            {section?.title ?? chapter.title}
          </h2>
          <p className="mt-1 text-[0.78rem] text-text-tertiary">
            화면 {chapter.sectionsDone}/{chapter.sectionsTotal}
            {chapter.pages && <> · {chapter.pages}</>}
          </p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-1.5">
          <ModeBadge mode={chapter.mode} />
          <StatusBadge status={chapter.status} label={chapter.statusLabel} />
        </div>
      </div>

      {/* 왜 이 분량인지. 목록에 묻혀 있던 것이 여기서는 주인공이다. */}
      {chapter.reason && (
        <div className="mt-3">
          <Reason text={chapter.reason} />
        </div>
      )}

      {/* 교재 밖 단원이면 무엇으로 채웠는지 밝힌다 — 안 밝히면 교재 내용으로
          오해한다. 책장에 있으면 그 파일을, 없으면 AI가 쓴 것임을 말한다. */}
      {chapter.inserted && (
        <p className="mt-2 truncate text-[0.78rem] text-emerald-700">
          {chapter.coveredBy ? chapter.coveredBy : "교재 밖 내용 · 보강 개념"}
        </p>
      )}

      <div className="mt-4">
        <Bar value={chapter.progress} tone="accent" />
      </div>

      <Link
        to={to}
        className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-[0.9rem] font-bold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
      >
        <PlayCircleIcon weight="fill" className="text-[1.05rem]" />
        {chapter.sectionsDone > 0 ? "이어서 학습" : "학습 시작"}
        <ArrowRightIcon className="text-[0.9rem]" />
      </Link>
    </section>
  );
}

/** 눈여겨볼 곳 — **목록이 아니라 짚어 주는 것**이다.
 *
 * 전체 목차를 다시 그리지 않는다. 지금 손봐야 할 이유가 있는 단원만 올린다:
 * 가장 약한 곳, 복습이 밀린 곳. 이유가 없으면 아무것도 안 그린다.
 */
function Watchlist({ doc }: { doc: DocumentOut }) {
  const base = `/curriculum/${encodeURIComponent(doc.docId)}`;
  const rows: { ch: ChapterBrief; why: string; tone: "weak" | "due" }[] = [];

  const weakest =
    doc.weakestChapter === null ? null : doc.chapters[doc.weakestChapter];
  if (weakest) rows.push({ ch: weakest, why: "가장 약함", tone: "weak" });

  for (const ch of doc.chapters) {
    if (ch.sectionsDue > 0 && ch.index !== doc.weakestChapter) {
      rows.push({ ch, why: `복습 ${ch.sectionsDue}개`, tone: "due" });
    }
  }
  if (rows.length === 0) return null;

  return (
    <section className="mt-6">
      <h3 className="mb-2 text-[0.7rem] font-bold tracking-wide text-text-tertiary">
        눈여겨볼 곳
      </h3>
      <ul className="divide-y divide-border-primary overflow-hidden rounded-2xl border border-border-primary bg-white">
        {rows.slice(0, 4).map(({ ch, why, tone }) => (
          <li key={`${ch.index}-${tone}`}>
            <Link
              to={`${base}/chapters/${ch.index}`}
              className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-bg-secondary"
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[0.9rem] font-semibold text-text-primary">
                  {ch.title}
                </span>
                <span className="block text-[0.75rem] text-text-tertiary">
                  화면 {ch.sectionsDone}/{ch.sectionsTotal}
                </span>
              </span>
              <span
                className={
                  tone === "weak"
                    ? "shrink-0 text-[0.75rem] font-bold text-red-600"
                    : "flex shrink-0 items-center gap-1 text-[0.75rem] font-bold text-amber-700"
                }
              >
                {tone === "due" && (
                  <ArrowsClockwiseIcon className="text-[0.8rem]" />
                )}
                {why}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CurriculumPage() {
  const { docId } = useParams<{ docId: string }>();
  const { data, isLoading, isError } = useDocument(docId);

  // 개요를 보는 동안 앞 화면을 서버가 미리 만든다. 여기 온 사람은 곧 첫 화면을
  // 누르는데, 그때 처음 만들면 LLM 콜 5~7초를 그대로 기다리게 된다.
  // 자료당 한 번만 — 목차를 오갈 때마다 다시 부르면 헛일이다.
  const warmed = useRef<string | null>(null);
  useEffect(() => {
    if (!docId || warmed.current === docId) return;
    warmed.current = docId;
    prewarm(docId);
  }, [docId]);

  if (!docId) return <Picker />;
  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (isError || !data)
    return <p className="p-8 text-red-600">자료를 불러오지 못했습니다.</p>;

  const hours = Math.floor(data.estimatedMinutes / 60);
  const mins = data.estimatedMinutes % 60;

  // 준비도 = 이해도 × 진도 × 회상. 준비도만 낮고 이해도는 높으면 **잊은 것**이라
  // 처방이 "복습"이고, 둘 다 낮으면 아직 모르는 것이라 "다시 학습"이다.
  const forgotten = data.understanding - data.readiness;
  const kinds = Object.entries(data.byKind).filter(([, n]) => n > 0) as [
    AttemptKind,
    number,
  ][];
  const next = nextChapter(data);
  const done = data.remainingSections === 0;

  return (
    <div className="mx-auto max-w-3xl p-8">
      {/* 책장으로 나가는 문은 **사이드바에만** 둔다. 여기에도 두면 같은 일을
          하는 링크가 한 화면에 둘이 되고, 왼쪽에 늘 떠 있는 쪽이 더 잘 보인다. */}

      {/* 코스면 진단 안내가 뜬다. 자료 하나면 아무것도 안 그린다. */}
      <div>
        <DiagnosticBanner docId={docId ?? ""} />
      </div>

      <header className="mt-3 mb-6">
        <h1 className="text-2xl font-bold text-text-primary">{data.title}</h1>
        <div className="mt-4 flex items-baseline gap-2">
          <span className="text-3xl font-bold tabular-nums text-text-primary">
            {pct(data.readiness)}
          </span>
          <span className="text-sm text-text-secondary">준비도</span>
        </div>
        <div className="mt-2">
          <Bar value={data.readiness} />
        </div>
        <p className="mt-2 text-[0.8rem] text-text-tertiary">
          남은 화면 {data.remainingSections} / {data.sectionsTotal} · 예상{" "}
          {hours > 0 ? `${hours}시간 ` : ""}
          {mins}분
        </p>

        {/* 이 숫자가 어디서 왔는지 — 진단·학습·복습·평가가 전부 여기로 모인다.
            근거를 안 보여주면 준비도가 그냥 떨어진 숫자로 보인다. */}
        {kinds.length > 0 && (
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.75rem] text-text-tertiary">
            {kinds.map(([k, n]) => (
              <span key={k}>
                {KIND_LABEL[k]}{" "}
                <span className="tabular-nums font-medium">{n}</span>
              </span>
            ))}
          </p>
        )}

        {/* 잊어서 낮은 것과 아직 몰라서 낮은 것은 처방이 다르다. */}
        {forgotten >= 0.05 && (
          <Link
            to={`/curriculum/${encodeURIComponent(data.docId)}/review`}
            className="mt-3 flex items-start gap-1.5 rounded-lg bg-amber-50/70 px-3 py-2 text-[0.8rem] text-amber-800 transition-colors hover:bg-amber-50"
          >
            <ArrowsClockwiseIcon className="mt-0.5 shrink-0" />
            <span>
              이해한 건 {pct(data.understanding)}인데 지금 꺼낼 수 있는 건{" "}
              {pct(data.readiness)}입니다. 복습이 필요한 화면 {data.sectionsDue}
              개 →
            </span>
          </Link>
        )}
      </header>

      {done ? (
        <section className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5">
          <CheckCircleIcon
            weight="fill"
            className="shrink-0 text-[1.6rem] text-emerald-600"
          />
          <div>
            <p className="font-bold text-text-primary">한 바퀴 다 돌았어요</p>
            <p className="mt-0.5 text-[0.85rem] text-text-secondary">
              이제 잊을 때쯤 다시 꺼내는 게 남았습니다.
            </p>
          </div>
        </section>
      ) : (
        next && <NextUp doc={data} chapter={next} />
      )}

      <Watchlist doc={data} />

      {/* 목차를 여기서 다시 그리지 않는다는 것을 말해 준다 — 없어진 게 아니라
          옆에 있다. */}
      <p className="mt-6 hidden text-[0.78rem] text-text-tertiary lg:block">
        전체 목차 {data.chapters.length}개는 왼쪽에 있어요.
      </p>

      {/* ⚠️ 좁은 화면에는 **사이드바가 없다**(`OutlinePanel`은 `lg:flex`).
          거기서는 목차를 여기 두지 않으면 단원으로 갈 길이 아예 사라진다.
          중복이 아니라 **둘 중 하나만 보이는 것**이라, 사이드바가 뜨는
          너비에서는 이쪽이 사라진다. 대신 판단은 안 싣는다 — 이동만 한다. */}
      <nav className="mt-8 lg:hidden">
        <h3 className="mb-2 text-[0.7rem] font-bold tracking-wide text-text-tertiary">
          전체 목차
        </h3>
        <ul className="divide-y divide-border-primary overflow-hidden rounded-2xl border border-border-primary bg-white">
          {data.chapters.map((ch) => (
            <li key={ch.index}>
              <Link
                to={`/curriculum/${encodeURIComponent(data.docId)}/chapters/${ch.index}`}
                className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-bg-secondary"
              >
                <span className="min-w-0 flex-1 truncate text-[0.9rem] font-medium text-text-primary">
                  {ch.title}
                </span>
                <span className="shrink-0 text-[0.75rem] tabular-nums text-text-tertiary">
                  {ch.sectionsDone}/{ch.sectionsTotal}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
