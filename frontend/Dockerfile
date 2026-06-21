# pnpm 기반 Vite 빌드 및 서빙 설정
FROM node:20-slim

# corepack으로 pnpm 활성화 + 버전 고정(package.json의 packageManager와 일치)
RUN corepack enable && corepack prepare pnpm@10.12.3 --activate

WORKDIR /app

# 의존성 먼저 복사 → 레이어 캐시 활용
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 앱 소스 복사
COPY . .

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
