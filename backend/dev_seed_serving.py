"""학습 서빙 E2E 확인용 dev 픽스처 시드(임시 스크립트).

유저/문서/청크/코스/개념/챕터/절을 심고 ID를 출력한다. 멱등(재실행 시 기존 삭제 후 재생성).
사용: docker compose exec -T backend uv run python dev_seed_serving.py
"""
import uuid

from app.core.database import SessionLocal
from app.features.auth.models import User
from app.features.curriculum.models import Chapter, Section
from app.features.learning.models import (
    Attempt,
    Block,
    ConceptMastery,
    Enrollment,
    LearningCursor,
    SectionProgress,
)
from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, ConceptEdge, Course, ExternalRef

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TITLE = "[DEV] 정보처리기사 서빙 검증"

db = SessionLocal()

# 멱등: 이 유저의 학습자 상태(FK 자식)부터 지우고 → 코스 삭제(개념/챕터/절/블록 CASCADE)
db.query(LearningCursor).filter(LearningCursor.user_id == DEV_USER_ID).delete(
    synchronize_session=False
)
db.query(Attempt).filter(Attempt.user_id == DEV_USER_ID).delete(
    synchronize_session=False
)
db.query(SectionProgress).filter(SectionProgress.user_id == DEV_USER_ID).delete(
    synchronize_session=False
)
db.query(ConceptMastery).filter(ConceptMastery.user_id == DEV_USER_ID).delete(
    synchronize_session=False
)
db.query(Enrollment).filter(Enrollment.user_id == DEV_USER_ID).delete(
    synchronize_session=False
)
db.commit()
for old in db.query(Course).filter(Course.title == TITLE).all():
    # blocks.concept_id FK엔 CASCADE 없음 → 코스 삭제 전 블록부터 제거
    concept_ids = [c.id for c in db.query(Concept).filter(Concept.course_id == old.id)]
    if concept_ids:
        db.query(Block).filter(Block.concept_id.in_(concept_ids)).delete(
            synchronize_session=False
        )
    db.query(Chapter).filter(Chapter.course_id == old.id).delete()
    db.delete(old)
db.commit()

user = db.get(User, DEV_USER_ID)
if user is None:
    user = User(id=DEV_USER_ID, email="dev@local", password_hash="dev")
    db.add(user)
    db.flush()

doc = Document(
    user_id=DEV_USER_ID,
    filename="dev.pdf",
    storage_url="dev://fixture",
    raw_text="정규화와 트랜잭션에 대한 데브 픽스처 문서",
    status="ready",
)
db.add(doc)
db.flush()

chunks = [
    DocChunk(
        document_id=doc.id,
        chunk_index=0,
        content="정규화는 데이터의 중복을 제거하고 이상 현상을 방지하기 위해 릴레이션을 분해하는 과정이다.",
        page_from=1,
        page_to=1,
    ),
    DocChunk(
        document_id=doc.id,
        chunk_index=1,
        content="제1정규형은 모든 속성이 원자값을 갖는 상태를 말하며, 제2정규형은 부분 함수 종속을 제거한다.",
        page_from=2,
        page_to=2,
    ),
    DocChunk(
        document_id=doc.id,
        chunk_index=2,
        content="트랜잭션은 데이터베이스의 상태를 변화시키는 논리적 작업 단위이며 ACID 성질을 가진다.",
        page_from=3,
        page_to=3,
    ),
]
db.add_all(chunks)
db.flush()

# 청크 passage 임베딩 — 상류(parsing) RAG 색인의 스탠드인. RAG 검색 테스트용, best-effort.
import asyncio  # noqa: E402

from app.core.llm.factory import get_llm_client  # noqa: E402

try:
    async def _embed_chunks() -> None:
        _llm = get_llm_client()
        for _c in chunks:
            _c.embedding = await _llm.embed(_c.content, purpose="passage")

    asyncio.run(_embed_chunks())
    db.flush()
    print("CHUNK_EMBED=ok")
except Exception as _e:  # noqa: BLE001
    print(f"CHUNK_EMBED=skip ({_e})")

course = Course(document_id=doc.id, user_id=DEV_USER_ID, title=TITLE, category="IT")
db.add(course)
db.flush()

# === parsing 규약(docs/GRAPH_ORIENTATION_CONTRACT.md) ===
# 진행축 = 커리큘럼 순서(섹션 대표개념, depth 0). 선행일수록 depth 큼. 엣지 의존→선수.
#
# 스파인(섹션, 순서): 개요(10) · 정규화(20) · 트랜잭션(30) · 인덱스(40)
#   floor=정규화(1020), ceiling=트랜잭션(1030)
#   → placement: 개요<floor→mastered / 정규화·트랜잭션→todo / 인덱스>ceiling→locked
# 선행(더 깊음, 섹션 없음): 정규화 → {DB기초(depth1), 관계대수(depth2)}  (의존→선수)
c_intro = Concept(course_id=course.id, key="db-overview", name="DB 개요",
                   description="관계형 데이터베이스 개관", source="book", depth_level=0)
c_norm = Concept(course_id=course.id, key="normalization", name="정규화",
                 description="중복 제거와 이상 방지를 위한 릴레이션 분해", source="book",
                 depth_level=0)
c_txn = Concept(course_id=course.id, key="transaction", name="트랜잭션",
                description="ACID를 만족하는 논리적 작업 단위", source="book", depth_level=0)
c_index = Concept(course_id=course.id, key="indexing", name="인덱스 튜닝",
                  description="탐색 성능을 위한 인덱스 설계(목표 너머 심화)", source="book",
                  depth_level=0)
# 정규화의 선행(더 깊음). 섹션 없음 → placement 미시딩, 국소화에선 미학습=결손(0.0).
c_dbbasic = Concept(course_id=course.id, key="db-basic", name="DB 기초",
                    description="테이블/키 등 관계형 모델의 기본", source="ai_prereq",
                    depth_level=1)
c_algebra = Concept(course_id=course.id, key="relational-algebra", name="관계대수",
                    description="셀렉션/프로젝션/조인 등 정규화의 근본 토대", source="ai_prereq",
                    depth_level=2)
db.add_all([c_intro, c_norm, c_txn, c_index, c_dbbasic, c_algebra])
db.flush()

ref = ExternalRef(
    concept_id=c_algebra.id,
    source_kind="corpus",
    title="관계대수 개론",
    url="https://example.org/relational-algebra",
    snippet="관계대수는 관계에 대한 연산의 집합으로 질의의 수학적 기반이다.",
)
db.add(ref)
db.flush()

chapter = Chapter(course_id=course.id, order_index=10, title="1장 데이터베이스", origin="book")
db.add(chapter)
db.flush()

# 스파인 섹션(진행 순서). 위치 = chapter*1000 + section order.
s_intro = Section(chapter_id=chapter.id, concept_id=c_intro.id, order_index=10, title="DB 개요")
s_norm = Section(chapter_id=chapter.id, concept_id=c_norm.id, order_index=20, title="정규화")
s_txn = Section(chapter_id=chapter.id, concept_id=c_txn.id, order_index=30, title="트랜잭션")
s_index = Section(chapter_id=chapter.id, concept_id=c_index.id, order_index=40, title="인덱스 튜닝")
db.add_all([s_intro, s_norm, s_txn, s_index])
db.flush()  # 블록이 s_norm.id를 참조하기 전 섹션 id 확정(default uuid는 flush 때 생성)

# 진단 종료 결과: 바닥=정규화(1020), 천장=트랜잭션(1030). placement 시딩 입력.
enrollment = Enrollment(
    user_id=DEV_USER_ID,
    course_id=course.id,
    floor_concept=c_norm.id,
    ceiling_concept=c_txn.id,
    floor_found=True,
    diag_status="completed",
    purpose="exam",
)
db.add(enrollment)

# 선행 엣지(parsing 규약: from=의존 → to=선수). 정규화가 DB기초·관계대수를 요구.
db.add_all([
    ConceptEdge(from_concept_id=c_norm.id, to_concept_id=c_dbbasic.id, kind="prerequisite"),
    ConceptEdge(from_concept_id=c_norm.id, to_concept_id=c_algebra.id, kind="prerequisite"),
])

# 정규화 채점 블록(mcq) — 국소화 E2E용(정답 index=1). tracked+verified.
mcq = Block(
    section_id=s_norm.id,
    order_index=0,
    type="mcq",
    kind="learn",
    concept_id=c_norm.id,
    source="book",
    tracked=True,
    source_chunk_ids=[chunks[0].id],
    verified=True,
    data={
        "question": "정규화의 주 목적은?",
        "options": ["정렬 속도 향상", "데이터 중복·이상 제거", "인덱스 생성"],
        "answerIndex": 1,
    },
    meta={},
)
db.add(mcq)

# 정규화 cloze 블록 — segments 변환 E2E용. tracked=False(완료 판정에 불영향).
cloze = Block(
    section_id=s_norm.id,
    order_index=1,
    type="cloze",
    kind="learn",
    concept_id=c_norm.id,
    source="book",
    tracked=False,
    source_chunk_ids=[chunks[0].id],
    external_ref_ids=[],
    verified=True,
    data={"text": "정규화는 데이터 {{blank}}을 제거한다", "blanks": ["중복"], "hint": "이상현상"},
    meta={},
)
db.add(cloze)
db.commit()

print(f"COURSE_ID={course.id}")
print(f"CHAPTER_ID={chapter.id}")
print(f"USER_ID={DEV_USER_ID}")
print(f"CONCEPT_NORM={c_norm.id}")
print(f"CONCEPT_DBBASIC={c_dbbasic.id}")
print(f"CONCEPT_ALGEBRA={c_algebra.id}")
print(f"BLOCK_MCQ={mcq.id}")
print("EXPECT placement → mastered=1(db-overview) todo=2(normalization,transaction) locked=1(indexing)")
print("EXPECT localize 오답2회 → prerequisite blame=관계대수(depth2, 최상류)")
