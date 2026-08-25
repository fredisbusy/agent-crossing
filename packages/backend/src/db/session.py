import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://agent:agent@localhost:5432/agent_crossing"
)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    with engine.begin() as connection:
        table_name = connection.scalar(text("SELECT to_regclass('public.game_sessions')"))
        if table_name is None:
            raise RuntimeError(
                "database migrations are not applied; run pnpm db:migrate"
                " (uv run alembic upgrade head)"
            )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
