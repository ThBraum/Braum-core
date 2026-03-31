from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.web import router as web_router
from app.api.routes.workspace import router as workspace_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.infrastructure.db import models as db_models  # noqa: F401
from app.infrastructure.db.base import Base
from app.infrastructure.db.database import engine

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="API central com orquestração dos fluxos Geral, RAG e SQL.",
)

register_exception_handlers(app)
app.include_router(web_router)
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(auth_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
