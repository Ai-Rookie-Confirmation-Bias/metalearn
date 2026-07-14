// GET/PUT /api/sections/:id/note — 나의 요약 노트(절 단위 자기설명 메모).
// 없으면 빈 노트가 온다(404 아님). 저장은 upsert.
import { apiClient } from "@/shared/api/client";

export type SectionNote = {
  sectionId: string;
  content: string;
  updatedAt: string | null;
};

export async function getSectionNote(sectionId: string): Promise<SectionNote> {
  const { data } = await apiClient.get<SectionNote>(`/api/sections/${sectionId}/note`);
  return data;
}

export async function saveSectionNote(
  sectionId: string,
  content: string,
): Promise<SectionNote> {
  const { data } = await apiClient.put<SectionNote>(
    `/api/sections/${sectionId}/note`,
    { content },
  );
  return data;
}
