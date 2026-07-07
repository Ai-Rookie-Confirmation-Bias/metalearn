"""모든 ORM 모델의 단일 임포트 지점.

SQLAlchemy는 임포트된 모델만 메타데이터에 등록한다. 요청 경로에 따라 일부
모델만 임포트되면 FK 해석(NoReferencedTableError)이 터지므로, 앱 시작 시
여기서 전부 로드한다(main.py에서 임포트). alembic env.py도 이 모듈을 쓰면 된다.
"""
from app.features.auth import models as _auth  # noqa: F401
from app.features.curriculum import models as _curriculum  # noqa: F401
from app.features.diagnostic import models as _diagnostic  # noqa: F401
from app.features.learning import models as _learning  # noqa: F401
from app.features.materials import models as _materials  # noqa: F401
from app.features.seed import models as _seed  # noqa: F401
