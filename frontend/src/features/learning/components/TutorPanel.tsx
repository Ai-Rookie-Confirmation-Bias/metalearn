// [3단계] 순수 UI 렌더링. queries만 호출.
import { useState } from "react";

import { Button } from "@/shared/ui/Button";
import { useGenerate } from "@/features/learning/queries/useGenerate";
import { useLearningStore } from "@/features/learning/store";

export function TutorPanel() {
  const [topic, setTopic] = useState("");
  const { mutate, data, isPending } = useGenerate();
  const activeTab = useLearningStore((s) => s.activeTab);

  return (
    <div>
      <p>현재 탭: {activeTab}</p>
      <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="주제" />
      <Button onClick={() => mutate(topic)} disabled={isPending}>
        {isPending ? "생성 중..." : "생성"}
      </Button>
      {data && <pre style={{ whiteSpace: "pre-wrap" }}>{data}</pre>}
    </div>
  );
}
