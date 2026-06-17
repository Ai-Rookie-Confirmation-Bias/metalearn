# uv 기반 파이썬 환경 및 uvicorn 실행 설정
FROM python:3.12-slim

# uv 설치
RUN pip install --no-cache-dir uv

WORKDIR /app

# 의존성 먼저 복사 → 레이어 캐시 활용.
# uv.lock이 아직 없으면 uv sync가 생성한다(첫 빌드). 락이 생기면 --frozen으로 바꿔도 됨.
COPY pyproject.toml uv.lock* ./
RUN uv sync

# 앱 소스 복사
COPY . .

# 컨테이너의 venv를 PATH에 추가
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
