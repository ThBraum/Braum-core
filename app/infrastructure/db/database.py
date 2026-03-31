from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import SETTINGS

engine = create_engine(
    SETTINGS.sqlalchemy_url,
    pool_pre_ping=True,
    echo=SETTINGS.cors_localhost,
)

async_engine = None
AsyncSessionLocal: sessionmaker[AsyncSession] | None = None

try:
    async_engine = create_async_engine(
        SETTINGS.async_sqlalchemy_url,
        pool_pre_ping=True,
        echo=SETTINGS.cors_localhost,
        future=True,
    )
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
    )
except ModuleNotFoundError:
    AsyncSessionLocal = None

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def async_get_db():
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Async DB session indisponível. Instale o driver async correspondente ao DATABASE_URL."
        )
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


DepDatabaseSession = Annotated[Session, Depends(get_db)]
DepAsyncDatabaseSession = Annotated[AsyncSession, Depends(async_get_db)]
