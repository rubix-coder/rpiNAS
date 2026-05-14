from __future__ import annotations

from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, Text,
    UniqueConstraint, event, text,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_settings


class Base(DeclarativeBase):
    pass


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime)
    phash: Mapped[str | None] = mapped_column(Text, index=True)
    face_rects: Mapped[str | None] = mapped_column(Text)  # JSON

    aesthetic_score: Mapped[float | None] = mapped_column(Float)
    sharpness_score: Mapped[float | None] = mapped_column(Float)
    exposure_score: Mapped[float | None] = mapped_column(Float)
    face_count: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[float | None] = mapped_column(Float, index=True)

    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("images.id"))

    status: Mapped[str] = mapped_column(Text, default="pending")   # pending/scoring/scored/error
    error_message: Mapped[str | None] = mapped_column(Text)
    decision: Mapped[str] = mapped_column(Text, default="undecided", index=True)  # undecided/approved/rejected/skipped

    scanned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime)

    album_entries: Mapped[list["AlbumImage"]] = relationship(
        "AlbumImage", back_populates="image", cascade="all, delete-orphan"
    )


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime)
    export_path: Mapped[str | None] = mapped_column(Text)

    images: Mapped[list["AlbumImage"]] = relationship(
        "AlbumImage", back_populates="album", cascade="all, delete-orphan",
        order_by="AlbumImage.sort_order"
    )


class AlbumImage(Base):
    __tablename__ = "album_images"
    __table_args__ = (UniqueConstraint("album_id", "image_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    album_id: Mapped[int] = mapped_column(Integer, ForeignKey("albums.id", ondelete="CASCADE"), nullable=False)
    image_id: Mapped[int] = mapped_column(Integer, ForeignKey("images.id", ondelete="CASCADE"), nullable=False)
    print_size: Mapped[str] = mapped_column(Text, default="4x6")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    album: Mapped["Album"] = relationship("Album", back_populates="images")
    image: Mapped["Image"] = relationship("Image", back_populates="album_entries")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    scored_files: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="running")  # running/complete/failed


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


settings = get_settings()
engine: AsyncEngine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
