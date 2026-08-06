"""코스 조립 — 자료를 묶고, 역할을 정하고, 목차를 복사한다.

여기까지가 "사람과 무관한 것"의 끝이다. 진단·커리큘럼 변형은 이 위에 얹는다.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.features.course.models import (
    Course,
    CourseDocument,
    CoursePrereq,
    CourseTopic,
    TopicOrigin,
)
from app.features.course.prereq import PrereqScreen
from app.features.course.schemas import CourseTree
from app.features.course.tree import CourseTreeBuilder
from app.features.parsing.pipeline import link
from app.features.parsing.models import (
    Concept,
    ConceptEdge,
    DensityGrade,
    Document,
    DocTopic,
    MaterialRole,
)

_log = logging.getLogger("uvicorn.error")

# 뼈대 우선순위. 낮을수록 먼저 — 교수님 PPT가 교재를 이긴다.
# 슬라이드는 "교수님이 정한 시험 범위"라서 목차 권위가 가장 높고,
# 교재는 범위가 넓어 그중 일부만 다루는 일이 흔하다.
_SKELETON_PRIORITY = {"pptx": 0, "image": 1, "pdf": 2}


class CourseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── 조립 ──────────────────────────────────────────────────────

    def create(
        self,
        *,
        user_id: uuid.UUID,
        document_ids: list[uuid.UUID],
        title: str | None = None,
        roles: dict[uuid.UUID, str] | None = None,
    ) -> Course:
        """자료들을 한 수업으로 묶는다.

        roles를 주면 그대로 쓰고, 없으면 밀도로 제안한다.
        """
        documents = list(
            self.db.scalars(select(Document).where(Document.id.in_(document_ids)))
        )
        if not documents:
            raise ValueError("자료를 찾을 수 없습니다.")
        missing = set(document_ids) - {d.id for d in documents}
        if missing:
            raise ValueError(f"자료를 찾을 수 없습니다: {missing}")

        assigned = roles or self.suggest_roles(documents)
        skeleton = self._pick_skeleton(documents, assigned)

        course = Course(
            user_id=user_id,
            title=title or skeleton.filename,
        )
        self.db.add(course)
        self.db.flush()

        for seq, document in enumerate(
            sorted(documents, key=lambda d: self._skeleton_rank(d))
        ):
            self.db.add(
                CourseDocument(
                    course_id=course.id,
                    document_id=document.id,
                    role=assigned[document.id],
                    seq=seq,
                )
            )

        copied = self.copy_topics(course, skeleton)
        self.db.flush()
        _log.info(
            "코스 생성: %r — 자료 %d개 (뼈대 %s) · 목차 %d개 복사",
            course.title, len(documents), skeleton.filename, copied,
        )
        return course

    def suggest_roles(self, documents: list[Document]) -> dict[uuid.UUID, str]:
        """역할 제안.

        원칙(PARSING_v3 §2): **올린 자료는 전부 뼈대 후보다.** 사용자가 올린
        것 자체가 "내가 배울 범위"라서다. 본문까지 겸할 수 있는지는 밀도가
        정한다 — 슬라이드는 표제어만 있어 설명을 못 대고, 교재는 둘 다 된다.

        자료가 하나뿐이면 그 하나가 뼈대이자 본문이다(교재로만 공부하는 경우).
        """
        if len(documents) == 1:
            only = documents[0]
            role = (
                MaterialRole.BODY.value
                if only.density_grade == DensityGrade.FULL.value
                else MaterialRole.SKELETON.value
            )
            return {only.id: role}

        skeleton = min(documents, key=self._skeleton_rank)
        assigned: dict[uuid.UUID, str] = {}
        for document in documents:
            if document.id == skeleton.id:
                assigned[document.id] = MaterialRole.SKELETON.value
            elif document.density_grade == DensityGrade.FULL.value:
                assigned[document.id] = MaterialRole.BODY.value
            else:
                # 뼈대도 본문도 아니면 참고로 둔다 — 개념 매칭에만 쓴다.
                assigned[document.id] = MaterialRole.REFERENCE.value
        return assigned

    def _skeleton_rank(self, document: Document) -> tuple[int, int, str]:
        """뼈대 후보 순위. 형식 → 밀도가 낮은 쪽 → 파일명(결정적 정렬).

        밀도가 **낮은** 쪽을 뼈대로 올리는 게 맞다. 얇은 자료(PPT)는 범위를
        정하는 데 쓰고 두꺼운 자료(교재)가 내용을 채우는 구조이기 때문이다.
        """
        return (
            _SKELETON_PRIORITY.get(document.source_format, 3),
            document.chars_per_page or 0,
            document.filename,
        )

    def _pick_skeleton(
        self, documents: list[Document], roles: dict[uuid.UUID, str]
    ) -> Document:
        skeletons = [
            d for d in documents if roles.get(d.id) == MaterialRole.SKELETON.value
        ]
        return min(skeletons or documents, key=self._skeleton_rank)

    def copy_topics(self, course: Course, skeleton: Document) -> int:
        """뼈대 자료의 목차를 이 코스로 복사한다.

        **복사지 참조가 아니다.** 사용자가 제목을 바꾸고 순서를 옮기고 단원을
        끼워 넣어도 원본(doc_topics)은 그대로 남아야 다음 사람이 같은 책을
        깨끗한 상태로 받는다.
        """
        topics = list(
            self.db.scalars(
                select(DocTopic)
                .where(DocTopic.document_id == skeleton.id)
                .order_by(DocTopic.seq)
            )
        )
        for topic in topics:
            self.db.add(
                CourseTopic(
                    course_id=course.id,
                    seq=topic.seq,
                    title=topic.title,
                    source_topic_id=topic.id,
                    origin=TopicOrigin.BOOK.value,
                )
            )
        return len(topics)

    # ── 조회 ──────────────────────────────────────────────────────

    def get(self, course_id: uuid.UUID) -> Course:
        course = self.db.get(Course, course_id)
        if course is None:
            raise ValueError(f"코스를 찾을 수 없습니다: {course_id}")
        return course

    async def prereqs(
        self, course_id: uuid.UUID, *, refresh: bool = False
    ) -> list[CoursePrereq]:
        """16' — 이 코스를 시작하기 전에 알아야 하는 것.

        **게으르게 계산한다.** 코스 생성은 동기이고 여기는 임베딩 호출이 필요해
        비동기라서, 생성 경로에 끼우면 업로드가 느려진다. 결과는 저장되므로
        두 번째 호출부터는 조회뿐이다.

        후보가 하나도 없는 자료(밑바닥부터 다 가르치는 책)는 행이 안 남아 매번
        다시 계산하지만, 그 경로는 LLM 호출이 0회라 사실상 공짜다.
        """
        course = self.get(course_id)
        existing = list(
            self.db.scalars(
                select(CoursePrereq)
                .where(CoursePrereq.course_id == course_id)
                .order_by(CoursePrereq.subject, CoursePrereq.seq)
            )
        )
        if existing and not refresh:
            return existing

        rows = await PrereqScreen(self.db).screen(course)
        self.db.commit()
        return sorted(rows, key=lambda r: (r.subject, r.seq))

    async def tree(self, course_id: uuid.UUID, *, force_link: bool = False) -> CourseTree:
        """18 — **뼈대 목차 순서 + 본문 자료 설명.** 이 서비스가 하려는 것의 본체.

        연결도 게으르게 계산한다(prereqs와 같은 사정). 문서쌍 단위로 저장돼
        있어서 같은 두 책을 쓰는 다음 사람은 계산이 없다.
        """
        course = self.get(course_id)
        document_ids = [cd.document_id for cd in course.documents]
        skeleton_id = next(
            (cd.document_id for cd in course.documents
             if cd.role == MaterialRole.SKELETON.value),
            document_ids[0] if document_ids else None,
        )
        body_ids = [d for d in document_ids if d != skeleton_id]

        linker = link.ConceptLinker(self.db)
        for other in body_ids:
            await linker.link_pair(skeleton_id, other, force=force_link)
        self.db.commit()

        return CourseTreeBuilder(self.db).build(
            course, skeleton_id=skeleton_id, body_ids=body_ids
        )

    def gaps(self, course_id: uuid.UUID) -> list[dict]:
        """끊긴 고리 — 이 코스의 자료들이 '알아야 한다'고 말하지만 설명이 없는 개념.

        ⑥ 외부 조달의 입력이자, 보강 단원을 어디에 끼울지의 근거다.
        몇 개 단원이 이 개념을 필요로 하는지(topics)와 몇 번 참조되는지(refs)를
        함께 준다 — 여러 단원이 부르면 단원으로 만들 값어치가 있고, 한 번만
        부르면 그 단원 설명에 한 줄 끼우면 된다.
        """
        course = self.get(course_id)
        document_ids = [cd.document_id for cd in course.documents]
        if not document_ids:
            return []

        rows = self.db.execute(
            select(
                Concept.id,
                Concept.name,
                Concept.global_key,
                Concept.definition,
            ).where(
                Concept.document_id.in_(document_ids),
                ~Concept.segment_links.any(),
            )
        ).all()

        gaps = []
        for concept_id, name, global_key, definition in rows:
            refs = self.db.execute(
                select(ConceptEdge.from_concept_id).where(
                    ConceptEdge.to_concept_id == concept_id
                )
            ).scalars().all()
            topic_ids = set(
                self.db.execute(
                    select(Concept.topic_id).where(Concept.id.in_(refs))
                ).scalars().all()
            ) - {None}
            gaps.append(
                {
                    "concept_id": concept_id,
                    "name": name,
                    "global_key": global_key,
                    "definition": definition,
                    "refs": len(refs),
                    "topics": len(topic_ids),
                }
            )

        gaps.sort(key=lambda g: (-g["topics"], -g["refs"], g["name"]))
        return gaps
