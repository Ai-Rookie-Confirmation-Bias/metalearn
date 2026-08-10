// MetaLearn 도서관 — **내 책장이 아니다.**
//
// 미리 분석해 둔 자료를 둘러보는 자리. 책장과 갈라 놓은 이유:
//
//   ① 올린 적 없는 책이 "나의 책장"에 섞이면 그게 내 것인지 아닌지 흐려진다
//   ② 진단을 요구하지 않는다 — 진단은 내 목표·성향을 묻는 자리라, 구경하러
//      연 자료에까지 물을 일이 아니다
//   ③ 진도를 안 센다. 여기서 읽은 것이 내 준비도에 섞이면 "내가 얼마나
//      했나"가 남의 책 분량에 희석된다
//
// 문제집 버튼도 없다. 문항은 `course_id + document_id`로 저장되는데 이 자료들은
// 코스가 아니라 붙일 자리가 없다 — 없는 걸 있는 것처럼 두지 않는다.
//
// 화면은 **서가**로 짠다. 카드 격자가 아니라 책이 선반에 꽂힌 모양인 이유는,
// 여기가 "내가 쌓아 온 것"이 아니라 "골라 오는 곳"이기 때문이다. 책장(`/library`)
// 과 생김새가 같으면 두 페이지의 성격 차이가 화면에서 안 보인다.
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { BooksIcon, MagnifyingGlassIcon } from "@phosphor-icons/react";

import {
  fetchDocument,
  type DocumentOut,
} from "@/features/curriculum/api/curriculum";
import {
  curriculumKeys,
  useDocuments,
} from "@/features/curriculum/queries/useCurriculum";
import {
  COVERS,
  assignCovers,
  type Cover,
} from "@/features/curriculum/components/covers";

/** 선반 널. 격자 칸을 꽉 채워서 옆 칸 널과 맞닿아야 한 줄로 이어져 보인다 —
 *  그래서 가로 간격(`gap-x`)이 0이고 책 쪽에만 안쪽 여백을 준다. */
function Plank() {
  return (
    <div className="mt-3 h-[7px] rounded-[2px] bg-gradient-to-b from-[#e2d6c2] to-[#c2ab8b] shadow-[0_2px_6px_rgba(120,95,60,0.25)]" />
  );
}

function Book({ doc, cover }: { doc: DocumentOut; cover: Cover }) {
  const CoverIcon = cover.icon;

  return (
    <div className="flex flex-col justify-end">
      <div className="px-3">
        <Link to={`/curriculum/${encodeURIComponent(doc.docId)}`} className="group block">
          {/* 표지 — 제목을 표지에 얹는다. 책은 등이 아니라 표지로 고른다. */}
          <div
            className={`relative h-[220px] overflow-hidden rounded-l-[3px] rounded-r-lg bg-gradient-to-br text-white shadow-md transition-all duration-200 group-hover:-translate-y-2 group-hover:shadow-xl ${cover.grad}`}
          >
            {/* 책등 */}
            <div className="absolute inset-y-0 left-0 w-[14px] bg-black/25" />
            <div className="absolute inset-y-0 left-[14px] w-px bg-white/25" />

            <div className="flex h-full flex-col justify-between p-4 pl-7">
              <CoverIcon className="text-[1.6rem] opacity-80" />
              <div>
                <h4 className="line-clamp-3 text-[0.95rem] font-bold leading-snug">
                  {doc.title}
                </h4>
                <p className="mt-1.5 text-[0.72rem] text-white/75">
                  목차 {doc.chapters.length} · 화면 {doc.sectionsTotal}
                </p>
              </div>
            </div>
          </div>

          <p className="mt-2.5 text-[0.8rem] text-text-tertiary transition-colors group-hover:text-accent">
            진단 없이 바로 열람
          </p>
        </Link>
      </div>
      <Plank />
    </div>
  );
}

export function SharedLibraryPage() {
  const { data: docIds, isLoading, isError } = useDocuments();
  const [query, setQuery] = useState("");

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  // 목록 API는 내 자료와 도서관 자료를 함께 준다(`shared` 플래그로 갈린다).
  // 여기서는 도서관 것만 남긴다 — 책장이 그 반대를 한다.
  const shared = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d) && Boolean(d!.shared));

  // 찾기는 **화면에서만** 한다. 자료 수가 수십 권이라 서버를 왕복할 이유가 없고,
  // 한 글자마다 요청을 보내면 목록이 깜빡인다.
  const q = query.trim().toLowerCase();
  const found = q
    ? shared.filter(
        (d) =>
          d.title.toLowerCase().includes(q) ||
          d.chapters.some((c) => c.title.toLowerCase().includes(q)),
      )
    : shared;

  const coverById = assignCovers(found.map((d) => d.docId));

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="mb-1.5 text-[0.75rem] font-bold uppercase tracking-wider text-text-tertiary">
            탐색
          </p>
          <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
            MetaLearn 도서관
          </h2>
          <p className="text-text-secondary">
            미리 분석해 둔 자료를 둘러보는 곳이에요. 진단 없이 바로 열어볼 수
            있고, 진도는 내 책장과 따로 셉니다.
          </p>
        </div>

        <div className="flex w-[320px] items-center gap-2 rounded-full border border-border-primary bg-white px-4 py-3 transition-colors focus-within:border-accent">
          <MagnifyingGlassIcon className="flex-shrink-0 text-[1.05rem] text-text-tertiary" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="책 제목이나 목차로 찾기"
            className="w-full bg-transparent text-[0.9rem] text-text-primary placeholder:text-text-tertiary focus:outline-none"
          />
        </div>
      </div>

      {isLoading && (
        <p className="py-12 text-center text-text-secondary">자료를 불러오는 중…</p>
      )}
      {isError && (
        <p className="py-12 text-center text-red-600">
          자료를 불러오지 못했습니다. 백엔드가 켜져 있는지 확인해 주세요.
        </p>
      )}

      {!isLoading && !isError && shared.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border-primary py-20 text-center">
          <BooksIcon className="mb-4 text-[2.5rem] text-text-tertiary" />
          <h4 className="text-lg font-bold text-text-primary">
            서가가 아직 비어 있어요
          </h4>
          <p className="mt-1.5 text-[0.9rem] text-text-secondary">
            자료를 적재하면 여기에 꽂힙니다.
          </p>
        </div>
      )}

      {!isLoading && !isError && shared.length > 0 && found.length === 0 && (
        <p className="py-16 text-center text-text-secondary">
          “{query}”에 맞는 책이 없어요.
        </p>
      )}

      {found.length > 0 && (
        <>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-x-0 gap-y-12">
            {found.map((doc) => (
              <Book
                key={doc.docId}
                doc={doc}
                cover={coverById.get(doc.docId) ?? COVERS[0]}
              />
            ))}
          </div>
          <p className="mt-8 text-[0.85rem] text-text-tertiary">
            서가에 {found.length}권
            {query.trim() && ` · 전체 ${shared.length}권 중`}
          </p>
        </>
      )}
    </div>
  );
}
