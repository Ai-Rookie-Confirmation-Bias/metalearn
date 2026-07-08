import { useEffect, useState } from "react";
import { GearIcon } from "@phosphor-icons/react";
import { apiClient } from "@/shared/api/client";
import { apiErrorMessage } from "@/shared/api/errors";

interface AxisOut {
  score: number;
  confidence: number;
  n: number;
}

interface ProfileOut {
  axes: Record<string, AxisOut>;
  label: string;
  traits: string[];
}

const AXES: { key: string; label: string; low: string; high: string }[] = [
  { key: "representation", label: "설명 방식", low: "정의·원리", high: "비유·예시" },
  { key: "rigor", label: "진행 방식", low: "실전·암기", high: "근본 이해" },
  { key: "context", label: "맥락 선호", low: "본론 직행", high: "배경·동기" },
];

export function SettingsPage() {
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const { data } = await apiClient.get<ProfileOut>("/api/profile/me");
        setProfile(data);
        setDraft(
          Object.fromEntries(
            AXES.map(({ key }) => [key, data.axes[key]?.score ?? 0.5]),
          ),
        );
      } catch {
        setProfile(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const { data } = await apiClient.patch<ProfileOut>("/api/profile/me", { axes: draft });
      setProfile(data);
      setMsg("저장했어요. 앞으로 생성되는 설명에 반영돼요.");
    } catch (e) {
      setMsg(apiErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-[640px] px-6 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">설정</h2>
        <p className="text-text-secondary">학습 성향과 환경을 관리하세요.</p>
      </div>

      {loading ? (
        <p className="text-text-tertiary">불러오는 중…</p>
      ) : !profile ? (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-border-primary bg-white py-16 text-center">
          <GearIcon className="mb-4 text-[3rem] text-text-tertiary" />
          <p className="font-semibold text-text-secondary">아직 학습 성향 프로필이 없어요</p>
          <p className="mt-1 text-[0.9rem] text-text-tertiary">
            교재 온보딩을 완료하면 여기서 확인·수정할 수 있어요.
          </p>
        </div>
      ) : (
        <div className="space-y-8 rounded-2xl border border-border-primary bg-white p-8">
          <div>
            <p className="text-sm font-semibold text-accent">나의 학습 성향</p>
            <h3 className="mt-1 text-xl font-bold text-text-primary">{profile.label}</h3>
            <ul className="mt-3 space-y-1 text-[0.9rem] text-text-secondary">
              {profile.traits.map((t) => (
                <li key={t}>· {t}</li>
              ))}
            </ul>
          </div>

          <div className="space-y-6 border-t border-border-primary pt-6">
            <p className="text-[0.9rem] text-text-secondary">
              측정 결과가 맞지 않으면 직접 조정할 수 있어요. 내용 분량은 줄어들지 않고
              <strong className="font-semibold text-text-primary"> 설명 방식만</strong> 바뀝니다.
            </p>
            {AXES.map(({ key, label, low, high }) => (
              <div key={key}>
                <div className="mb-2 flex justify-between text-[0.85rem] font-semibold text-text-primary">
                  <span>{label}</span>
                  <span className="text-text-tertiary">{Math.round((draft[key] ?? 0.5) * 100)}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  value={Math.round((draft[key] ?? 0.5) * 100)}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, [key]: Number(e.target.value) / 100 }))
                  }
                  className="w-full accent-accent"
                />
                <div className="mt-1 flex justify-between text-[0.75rem] text-text-tertiary">
                  <span>{low}</span>
                  <span>{high}</span>
                </div>
              </div>
            ))}
          </div>

          {msg && <p className="text-[0.9rem] text-text-secondary">{msg}</p>}

          <button
            type="button"
            disabled={saving}
            onClick={() => void save()}
            className="w-full rounded-xl bg-primary py-3 text-[0.95rem] font-semibold text-white hover:bg-primary-hover disabled:opacity-50"
          >
            {saving ? "저장 중…" : "성향 저장"}
          </button>
        </div>
      )}
    </div>
  );
}
