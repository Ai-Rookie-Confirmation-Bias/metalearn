// 브라우저 영구/대용량 저장소 (Dexie · IndexedDB) — Phase 2.
// 오프라인 학습 상태 영속화에 사용 예정. 지금은 스키마 골격만.
import Dexie, { type EntityTable } from "dexie";

interface CachedItem {
  id: number;
  content: string;
}

const db = new Dexie("metalearn") as Dexie & {
  items: EntityTable<CachedItem, "id">;
};

db.version(1).stores({
  items: "++id, content",
});

export { db };
