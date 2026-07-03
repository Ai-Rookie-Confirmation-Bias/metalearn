"""학습 서빙 E2E 확인용 dev 픽스처 시드(임시 스크립트).

유저/문서/청크/코스/개념/챕터/절을 심고 ID를 출력한다. 멱등(재실행 시 기존 삭제 후 재생성).
사용: docker compose exec -T backend uv run python dev_seed_serving.py
"""
import uuid

from app.core.database import SessionLocal
from app.features.auth.models import User
from app.features.curriculum.models import Chapter, Section
from app.features.materials.models import DocChunk, Document
from app.features.seed.models import Concept, Course, ExternalRef

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TITLE = "[DEV] 정보처리기사 서빙 검증"

db = SessionLocal()

# 멱등: 같은 제목의 이전 픽스처 제거
for old in db.query(Course).filter(Course.title == TITLE).all():
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

course = Course(document_id=doc.id, user_id=DEV_USER_ID, title=TITLE, category="IT")
db.add(course)
db.flush()

c_norm = Concept(
    course_id=course.id,
    key="normalization",
    name="정규화",
    description="중복 제거와 이상 방지를 위한 릴레이션 분해",
    source="book",
    depth_level=5,
)
c_db_basic = Concept(
    course_id=course.id,
    key="db-basic",
    name="DB 기초",
    description="테이블/키 등 관계형 모델의 기본",
    source="ai_prereq",
    depth_level=2,
)
db.add_all([c_norm, c_db_basic])
db.flush()

ref = ExternalRef(
    concept_id=c_db_basic.id,
    source_kind="corpus",
    title="관계형 데이터베이스 개론",
    url="https://example.org/rdb-basics",
    snippet="관계형 모델에서 테이블은 행과 열로 구성되며 기본키로 각 행을 식별한다.",
)
db.add(ref)
db.flush()

chapter = Chapter(course_id=course.id, order_index=10, title="1장 데이터베이스", origin="book")
db.add(chapter)
db.flush()

s1 = Section(chapter_id=chapter.id, concept_id=c_norm.id, order_index=10, title="정규화")
s2 = Section(chapter_id=chapter.id, concept_id=c_db_basic.id, order_index=20, title="보충: DB 기초")
db.add_all([s1, s2])
db.commit()

print(f"COURSE_ID={course.id}")
print(f"CHAPTER_ID={chapter.id}")
print(f"SECTION_BOOK={s1.id}")
print(f"SECTION_PREREQ={s2.id}")
