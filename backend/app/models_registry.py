"""모든 ORM 모델의 단일 임포트 지점.

SQLAlchemy는 임포트된 모델만 메타데이터에 등록한다. 요청 경로에 따라 일부
모델만 로드되면 FK 해석이 터지므로(NoReferencedTableError) 여기서 전부
로드한다. main.py와 alembic/env.py 양쪽이 이 모듈만 임포트하면 된다.

새 도메인을 추가하면 여기에 한 줄 추가할 것.
"""
from app.features.course import models as _course  # noqa: F401
from app.features.learning import models as _learning  # noqa: F401
from app.features.parsing import models as _parsing  # noqa: F401
from app.features.quiz import models as _quiz  # noqa: F401
