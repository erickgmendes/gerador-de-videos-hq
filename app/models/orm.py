"""Modelos SQLAlchemy — só metadados. Arquivos grandes (áudio/imagem/vídeo)
vivem no filesystem sob PROJECTS_DIR; aqui guardamos apenas caminho relativo,
tamanho, duração e status (ver ARCHITECTURE.md, "Estratégia de Armazenamento").
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.states import ProjectState


def _uuid() -> str:
    return uuid.uuid4().hex[:8]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    bible_reference: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(40), default=ProjectState.CREATED.value)
    youtube_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    locations: Mapped[list["Location"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    image_prompts: Mapped[list["ImagePrompt"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column(Integer)
    location: Mapped[str] = mapped_column(String(200), default="")
    time: Mapped[str] = mapped_column(String(100), default="")
    characters: Mapped[list[str]] = mapped_column(JSON, default=list)
    action: Mapped[str] = mapped_column(Text, default="")
    emotion: Mapped[str] = mapped_column(String(100), default="")
    narration_excerpt: Mapped[str] = mapped_column(Text, default="")
    visual_importance: Mapped[str] = mapped_column(String(20), default="")
    estimated_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")

    project: Mapped[Project] = relationship(back_populates="scenes")
    image_prompts: Mapped[list["ImagePrompt"]] = relationship(back_populates="scene", cascade="all, delete-orphan")


class ImagePrompt(Base):
    """Um painel de quadrinho — não uma cena. Uma cena (~26s de áudio) vira
    vários painéis (Fase 4: cálculo por duração ÷ VIDEO_SEGMENT_SECONDS,
    não por "complexidade narrativa"), cada um com seu próprio prompt
    autossuficiente e, depois do upload, sua própria imagem."""

    __tablename__ = "image_prompts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"))
    global_order: Mapped[int] = mapped_column(Integer)  # numeração 001, 002... no projeto inteiro
    order_in_scene: Mapped[int] = mapped_column(Integer)  # 1-based dentro da cena
    shot_type: Mapped[str] = mapped_column(String(60), default="")
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="image_prompts")
    scene: Mapped[Scene] = relationship(back_populates="image_prompts")


class Character(Base):
    """Cache indexado de um bloco do biblia-visual-personagens.md do projeto.

    O arquivo .md continua sendo a fonte canônica; esta tabela existe só
    para permitir detectar rapidamente personagens de uma nova cena que
    ainda não têm entrada na Bíblia Visual (seção 11 da especificação).
    """

    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    visual_description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)

    project: Mapped[Project] = relationship(back_populates="characters")


class Location(Base):
    """Cache de continuidade dos cenários, mesmo papel que `Character` tem
    para personagens: a IA só descreve um local em detalhe na primeira
    cena em que ele aparece; da segunda cena em diante (mesmo que citado
    com um nome diferente — "o templo" vs. "o Templo de Jerusalém"), a
    descrição salva é reaproveitada literalmente, evitando que o mesmo
    cenário mude de arquitetura/iluminação de cena para cena."""

    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    visual_description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)

    project: Mapped[Project] = relationship(back_populates="locations")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="generated")
    status: Mapped[str] = mapped_column(String(40), default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="artifacts")


class Job(Base):
    """Rastreia operações longas assíncronas (Fase 2+): geração de narração,
    TTS, montagem, upload no YouTube. Existe desde a Fase 1 como
    infraestrutura central de retomada (seções 39-41), mesmo sem nenhuma
    operação longa ainda produzindo jobs.
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    job_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="jobs")


class AssemblyConfig(Base):
    """Configuração usada em uma execução de montagem (Fase 6). Guardada por
    projeto e versionada implicitamente pelo created_at — regenerar a
    montagem reaproveita a última configuração salva."""

    __tablename__ = "assembly_configs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    transition_type: Mapped[str] = mapped_column(String(20), default="crossfade")
    transition_duration: Mapped[float] = mapped_column(Float, default=0.5)
    fade_in: Mapped[bool] = mapped_column(default=True)
    fade_out: Mapped[bool] = mapped_column(default=True)
    narration_volume: Mapped[int] = mapped_column(Integer, default=100)
    bg_music_enabled: Mapped[bool] = mapped_column(default=False)
    bg_music_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    scene_duration_mode: Mapped[str] = mapped_column(String(20), default="automatica")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class YouTubePublication(Base):
    __tablename__ = "youtube_publications"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    video_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    visibility: Mapped[str] = mapped_column(String(20), default="private")
    category: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    """Preferências não sensíveis editáveis pela tela de Configurações.
    Segredos (API keys) nunca passam por aqui — só por .env."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(40), default="sistema")
