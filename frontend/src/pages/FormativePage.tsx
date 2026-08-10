// [화면 4] 단원 평가 — 화면을 가로질러 구별할 수 있는가.
//
// 학습 화면의 인출과 목적이 다르다. 인출은 "방금 읽은 이 개념을 꺼낼 수 있나",
// 평가는 "여러 화면에서 배운 것들이 섞여 있을 때 가를 수 있나"다. 단원을 다 읽고
// 나면 개념 하나하나는 알아도 서로 헷갈리는 게 정상이고, 여기가 그걸 잡는 자리다.
//
// 🔒 **잠기는 건 여기뿐이다.** 학습은 절대 안 잠근다. 그리고 잠금은 진도로만 —
// 이해도로 잠그면 못 하는 사람일수록 확인할 기회가 사라진다.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LightningIcon, LockSimpleIcon } from "@phosphor-icons/react";

import { Mcq } from "@/features/curriculum/components/Mcq";
import { Bar, pct } from "@/features/curriculum/components/bits";
import {
  useAnswer,
  useFormative,
} from "@/features/curriculum/queries/useCurriculum";

export function FormativePage() {
  const { docId = "", index = "0" } = useParams<{
    docId: string;
    index: string;
  }>();
  const chapterIndex = Number(index);
  const { data, isLoading, isError } = useFormative(docId, chapterIndex);
  const answer = useAnswer(docId);
  const [done, setDone] = useState<Record<number, boolean>>({});

  if (isLoading)
    return (
      <div className="mx-auto max-w-2xl p-8">
        <p className="text-text-secondary">단원 평가를 만드는 중…</p>
        <p className="mt-1 text-[0.8rem] text-text-tertiary">
          단원 전체를 훑어 문항을 만듭니다. 처음 한 번만 10초 안팎 걸립니다.
        </p>
      </div>
    );
  if (isError || !data)
    return <p className="p-8 text-red-600">단원 평가를 불러오지 못했습니다.</p>;

  const back = `/curriculum/${encodeURIComponent(docId)}/chapters/${chapterIndex}`;
  const answered = Object.keys(done).length;
  const correct = Object.values(done).filter(Boolean).length;

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Link
        to={back}
        className="text-[0.8rem] text-text-tertiary hover:underline"
      >
        ← {data.chapterTitle}
      </Link>

      <header className="mt-3 mb-6">
        <p className="text-[0.7rem] font-semibold text-text-tertiary">
          단원 평가
        </p>
        <h1 className="text-2xl font-bold text-text-primary">
          {data.chapterTitle}
        </h1>
        <p className="mt-2 text-[0.8rem] text-text-secondary">
          여러 화면에서 배운 것들을 <strong>섞어서</strong> 묻습니다. 하나씩은
          알아도 같이 놓으면 헷갈리는 지점을 찾는 자리입니다.
        </p>
      </header>

      {/* 🔒 잠김 — 무엇을 하면 열리는지까지 말한다. "잠김"만 띄우면 알 수 없다. */}
      {data.locked ? (
        <div className="rounded-lg border border-border-primary bg-bg-secondary p-6 text-center">
          <LockSimpleIcon
            weight="fill"
            className="text-2xl text-text-tertiary"
          />
          <p className="mt-2 font-medium text-text-primary">{data.reason}</p>
          <div className="mx-auto mt-4 max-w-xs">
            <Bar value={data.progress} tone="accent" />
            <p className="mt-1 text-[0.75rem] text-text-tertiary">
              이 단원 진도 {pct(data.progress)}
            </p>
          </div>
          <Link
            to={back}
            className="mt-4 inline-block rounded bg-primary px-4 py-2 text-[0.8rem] font-medium text-white hover:bg-primary-hover"
          >
            학습하러 가기 →
          </Link>
        </div>
      ) : !data.generated ? (
        <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          문항을 만들지 못했습니다. 잠시 후 다시 열어주세요.
        </p>
      ) : (
        <>
          {/* 이 평가가 무엇을 확인하는지 — 백엔드가 실제로 문항에 넣은 것만 온다. */}
          {data.coveredWeak.length > 0 && (
            <p className="mb-4 rounded-lg border-l-4 border-accent bg-accent/5 px-3 py-2 text-[0.8rem] text-text-primary">
              <LightningIcon
                weight="fill"
                aria-hidden
                className="mr-1 inline align-[-2px]"
              />
              자주 틀리신 <strong>{data.coveredWeak.join(" · ")}</strong>을(를)
              이번 평가에 넣었습니다.
            </p>
          )}

          <ul className="space-y-3">
            {data.blocks.map((b, i) => (
              <Mcq
                key={i}
                block={b}
                label={`${i + 1}번 — 가르기`}
                onGraded={(ok, conceptKey) => {
                  setDone((d) => ({ ...d, [i]: ok }));
                  // 문항은 화면을 가로지르지만 숙련도는 화면 단위다. 어느 화면에
                  // 기록할지는 **백엔드가 정해서** sectionId로 실어 보낸다.
                  answer.mutate({
                    sectionId: String(b.content.sectionId ?? ""),
                    correct: ok,
                    conceptKey,
                    kind: "formative",
                  });
                }}
              />
            ))}
          </ul>

          {answered > 0 && (
            <div className="mt-6 rounded-lg border border-border-primary p-4">
              <p className="text-sm text-text-secondary">
                {answered}/{data.blocks.length} 문항 ·{" "}
                <strong className="text-text-primary">{correct}개 정답</strong>
              </p>
              {answered === data.blocks.length && (
                <p className="mt-1 text-[0.8rem] text-text-tertiary">
                  결과는 단원 이해도와 준비도에 반영됐습니다. 틀린 개념은 다음
                  화면 설명에 함께 녹습니다.
                </p>
              )}
              <Link
                to={back}
                className="mt-3 inline-block rounded bg-primary px-3 py-1.5 text-[0.8rem] font-medium text-white hover:bg-primary-hover"
              >
                단원으로 돌아가기 →
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}
