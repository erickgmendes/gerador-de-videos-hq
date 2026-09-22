"""Fixtures compartilhadas: cada teste roda com seu próprio banco SQLite e
sua própria pasta de projetos em um diretório temporário — nunca toca em
data/app.db ou projects/ do desenvolvimento."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.config as app_config
from app.config import get_settings
from app.db import Base
from app.models import orm  # noqa: F401 — garante que todos os modelos estejam
# registrados em Base.metadata antes de qualquer create_all() abaixo. Sem isso,
# rodar um arquivo de teste isoladamente (que não importe app.models por conta
# própria) cria um banco sem tabelas — só "funcionava" por acaso quando outro
# arquivo de teste, coletado antes, importava os modelos primeiro.


@pytest.fixture()
def test_settings(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    projects_dir = tmp_path / "projects"
    db_path = data_dir / "app.db"
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("PROJECTS_DIR", str(projects_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    # Aponta para um .env que não existe — isola os testes do .env real do
    # projeto (senão, uma GROQ_API_KEY salva de verdade via Configurações
    # vazaria para todo o resto da suíte). Testes que precisam de um .env
    # de verdade (ex. tests/unit/test_settings_service.py) sobrescrevem de
    # novo por cima disto.
    monkeypatch.setattr(app_config, "get_env_file_path", lambda: tmp_path / "unused.env")
    for key in (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "YOUTUBE_CLIENT_SECRET_FILE",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    settings.ensure_directories()
    yield settings
    get_settings.cache_clear()


@pytest.fixture()
def db_engine(test_settings):
    engine = create_engine(test_settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session_factory(db_engine):
    """A sessionmaker bound to the test's temp engine — pass this wherever
    production code expects `get_session_factory()`'s return value, so
    background-task code opening its own session still hits the test db."""
    return sessionmaker(bind=db_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def app_client(db_session_factory):
    from app.db import get_db, get_session_factory
    from app.main import create_app

    def override_get_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: db_session_factory

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client
