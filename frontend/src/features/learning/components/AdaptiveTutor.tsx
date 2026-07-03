/**
 * 적응형 살아있는 커리큘럼 테스트 컴포넌트.
 *
 * 프론트 카탈로그 계약(① 설명 → ② 문제) 그대로:
 *  - type "concept"     → 설명만 읽고 [이해했어요] → 다음 블록 요청 (추적 X)
 *  - type "explainBack" → 역질문에 답해야 진행 (추적 O, onAnswer)
 *
 * 백엔드가 정답/오답 → 다음 챕터 / 보충 / 선행 챕터 삽입을 결정한다.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getLearnerModel,
  getNextBlock,
  submitBlockAnswer,
} from "@/features/learning/api/learningApi";
import type {
  BlockAnswerResponse,
  ConceptBlockData,
  ExplainBackBlockData,
} from "@/features/learning/types";

interface Props {
  profileId: string;
}

const ACTION_LABEL: Record<string, string> = {
  advance: "다음 챕터로",
  thin_pass: "얇게 통과",
  supplement: "보충 학습",
  prerequisite: "선행 챕터 삽입",
};
const ACTION_COLOR: Record<string, string> = {
  advance: "bg-green-100 text-green-800",
  thin_pass: "bg-blue-100 text-blue-800",
  supplement: "bg-orange-100 text-orange-800",
  prerequisite: "bg-purple-100 text-purple-800",
};

export default function AdaptiveTutor({ profileId }: Props) {
  const qc = useQueryClient();
  const [userInput, setUserInput] = useState("");
  const [result, setResult] = useState<BlockAnswerResponse | null>(null);

  const { data: block, isFetching, refetch } = useQuery({
    queryKey: ["nextBlock", profileId],
    queryFn: () => getNextBlock(profileId),
    staleTime: Infinity,
    retry: false,
  });

  const { data: learnerModel } = useQuery({
    queryKey: ["learnerModel", profileId],
    queryFn: () => getLearnerModel(profileId),
  });

  const answerMutation = useMutation({
    mutationFn: () =>
      submitBlockAnswer({
        profileId,
        blockId: block!.id,
        conceptId: block!.conceptId,
        userInput,
        correct: null, // explainBack은 서술형 → 백엔드 LLM 채점
      }),
    onSuccess: (res) => {
      setResult(res);
      setUserInput("");
      qc.invalidateQueries({ queryKey: ["learnerModel", profileId] });
    },
  });

  const goNext = () => {
    setResult(null);
    refetch();
  };

  const score = block
    ? learnerModel?.conceptMastery?.[block.conceptId]?.score
    : undefined;

  const isConcept = block?.type === "concept";
  const isExplain = block?.type === "explainBack";

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800">적응형 튜터</h2>
        {learnerModel && (
          <span className="text-xs text-gray-500">챕터 #{learnerModel.currentUnitOrder}</span>
        )}
      </div>

      {isFetching && <div className="animate-pulse text-sm text-gray-400">로딩 중…</div>}

      {block && !isFetching && (
        <>
          {/* 블록 헤더 */}
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-gray-800 px-2.5 py-0.5 text-xs font-mono text-white">
              {block.type}
            </span>
            <span className="text-xs text-gray-400">
              {block.source === "book" ? "📖 원문" : "🤖 AI"} · {block.meta.difficulty}
            </span>
          </div>

          {/* ① 설명 블록 */}
          {isConcept && (
            <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">
                {(block.data as unknown as ConceptBlockData).title}
              </h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                {(block.data as unknown as ConceptBlockData).body}
              </p>
              <button
                className="mt-4 w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
                onClick={goNext}
              >
                이해했어요 →
              </button>
            </div>
          )}

          {/* ② 문제 블록 (explainBack) */}
          {isExplain && (
            <div className="space-y-3 rounded-xl border border-indigo-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold text-indigo-500">✍️ 설명해보기</p>
              <p className="text-sm font-medium text-gray-800">
                {(block.data as unknown as ExplainBackBlockData).prompt}
              </p>

              {score !== undefined && (
                <div className="flex items-center gap-2">
                  <div className="h-2 flex-1 rounded-full bg-gray-200">
                    <div
                      className="h-2 rounded-full bg-indigo-500 transition-all"
                      style={{ width: `${Math.round(score * 100)}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-600">{Math.round(score * 100)}%</span>
                </div>
              )}

              {!result && (
                <div className="flex gap-2">
                  <input
                    className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    placeholder="기억나는 대로 설명해 보세요…"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) =>
                      e.key === "Enter" &&
                      !answerMutation.isPending &&
                      userInput.trim() &&
                      answerMutation.mutate()
                    }
                  />
                  <button
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                    onClick={() => answerMutation.mutate()}
                    disabled={!userInput.trim() || answerMutation.isPending}
                  >
                    {answerMutation.isPending ? "채점 중…" : "제출"}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* 채점 결과 + 커리큘럼 변화 */}
          {result && (
            <div className="space-y-3">
              <div
                className={`rounded-lg px-4 py-3 text-sm ${
                  result.correct ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                }`}
              >
                <p className="font-semibold">
                  {result.correct ? "✅ 정답" : "❌ 오답"} · 숙련도{" "}
                  {Math.round(result.masteryScore * 100)}%
                </p>
                <p className="mt-1">{result.feedback}</p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    ACTION_COLOR[result.nextAction] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {ACTION_LABEL[result.nextAction] ?? result.nextAction}
                </span>
                {result.weaknessRegistered && (
                  <span className="rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs text-yellow-800">
                    약점 등록됨
                  </span>
                )}
              </div>

              {result.curriculumChanged && result.insertedUnitTitle && (
                <div className="rounded-lg border border-purple-200 bg-purple-50 px-4 py-3 text-sm text-purple-800">
                  🌱 커리큘럼이 바뀌었습니다 — 선행 챕터{" "}
                  <strong>「{result.insertedUnitTitle}」</strong>가 추가되었습니다.
                </div>
              )}

              <button
                className="w-full rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
                onClick={goNext}
              >
                계속 →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
