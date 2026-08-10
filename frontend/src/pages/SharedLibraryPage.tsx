// 기본 제공 자료 — **내 책장이 아니다.**
//
// 미리 파싱해 둔 CS 기초 자료를 둘러보는 자리. 책장과 갈라 놓은 이유:
//
//   ① 올린 적 없는 책이 "나의 책장"에 섞이면 그게 내 것인지 아닌지 흐려진다
//   ② 진단을 요구하지 않는다 — 진단은 내 목표·성향을 묻는 자리라, 구경하러
//      연 자료에까지 물을 일이 아니다
//   ③ 진도를 안 센다. 여기서 읽은 것이 내 준비도에 섞이면 "내가 얼마나
//      했나"가 남의 책 분량에 희석된다
//
// 문제집 버튼도 없다. 문항은 `course_id + document_id`로 저장되는데 이 자료들은
// 코스가 아니라 붙일 자리가 없다 — 없는 걸 있는 것처럼 두지 않는다.
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { BooksIcon } from "@phosphor-icons/react";

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

function SharedCard({ doc, cover }: { doc: DocumentOut; cover: Cover }) {
  const CoverIcon = cover.icon;

  return (
    <div className="flex min-h-[300px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm transition-all hover:-translate-y-1 hover:border-text-tertiary hover:shadow-lg">
      <div
        className={`relative flex h-[130px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`}
      >
        <CoverIcon className="text-[3.25rem] opacity-90" />
        <span className="absolute right-4 top-4 rounded-full bg-white/20 px-3 py-1 text-xs font-bold backdrop-blur-sm">
          화면 {doc.sectionsTotal}개
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 text-[1.05rem] font-bold leading-snug text-text-primary">
          {doc.title}
        </h4>
        <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">
          목차 {doc.chapters.length}개 · 진단 없이 바로 열어볼 수 있어요
        </p>

        <Link
          to={`/curriculum/${encodeURIComponent(doc.docId)}`}
          className="mt-auto inline-flex w-full items-center justify-center rounded-xl border border-border-primary px-5 py-3 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent"
        >
          학습 자료 보기
        </Link>
      </div>
    </div>
  );
}

export function SharedLibraryPage() {
  const { data: docIds, isLoading, isError } = useDocuments();

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  // 목록 API는 내 자료와 기본 제공을 함께 준다(`shared` 플래그로 갈린다).
  // 여기서는 기본 제공만 남긴다 — 책장이 그 반대를 한다.
  const shared = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d) && Boolean(d!.shared));

  const coverById = assignCovers(shared.map((d) => d.docId));

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          기본 제공 자료
        </h2>
        <p className="text-text-secondary">
          미리 분석해 둔 CS 기초 자료예요. 진단 없이 바로 열어볼 수 있고, 진도는
          따로 세지 않습니다.
        </p>
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
            아직 기본 제공 자료가 없어요
          </h4>
          <p className="mt-1.5 text-[0.9rem] text-text-secondary">
            자료를 적재하면 여기에 보입니다.
          </p>
        </div>
      )}

      {!isLoading && !isError && shared.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-8">
          {shared.map((doc) => (
            <SharedCard
              key={doc.docId}
              doc={doc}
              cover={coverById.get(doc.docId) ?? COVERS[0]}
            />
          ))}
        </div>
      )}
    </div>
  );
}
