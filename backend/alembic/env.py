"""Alembic 마이그레이션 환경. settings에서 DB URL과 모델 메타데이터를 가져옴."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base

# 모델 등록(메타데이터 채우기). 새 도메인은 models_registry에 추가한다.
#
# ⚠️ 여기에 직접 import를 늘리지 않는다. 이 파일과 main.py가 서로 다른 목록을
#    갖게 되면, 한쪽에만 등록된 모델이 FK 해석에서 터진다(NoReferencedTableError).
#    등록 지점은 models_registry 하나뿐이다 — quiz 모델도 거기에 넣었다.
import app.models_registry  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
