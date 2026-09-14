from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine():
    settings = get_settings()
    settings.ensure_directories()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_factory() -> sessionmaker:
    """Fábrica de sessões para uso fora do ciclo de requisição (background
    tasks). Indireção deliberada — não usar a variável global `SessionLocal`
    diretamente em código que precise ser testável, pois os testes
    substituem esta função (não a variável) para apontar para um banco
    temporário, do mesmo jeito que fazem com get_db via dependency_overrides."""
    return SessionLocal
