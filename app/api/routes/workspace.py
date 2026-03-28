import json
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from jose import jwt
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.domain.schemas import ChatMode
from app.domain.workspace_schemas import (
    ChatSendRequest,
    ChatSendResponse,
    ConversationCreateRequest,
    ConversationDTO,
    ConversationMessageDTO,
    DevTokenRequest,
    FileDTO,
)
from app.infrastructure.db.database import SessionLocal
from app.infrastructure.db.models import Conversation, ConversationMessage, UserFile
from app.infrastructure.llm_provider import LLMProvider
from app.services.general_answer_service import GeneralAnswerService


router = APIRouter(prefix="/workspace", tags=["workspace"])

DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
TABLE_EXTENSIONS = {".csv", ".xlsx"}


class ConversationUpdateRequest(BaseModel):
    mode: ChatMode | None = None
    title: str | None = None


def _storage_root() -> Path:
    return Path("data") / "uploads"


def _safe_owner_folder(owner_id: str) -> str:
    return quote_plus(owner_id)


def _resolve_owner(client_id: str | None, access_token: str | None) -> tuple[str, bool]:
    if access_token:
        payload = decode_access_token(access_token)
        return str(payload["sub"]), True

    if not client_id:
        raise HTTPException(status_code=400, detail="client_id é obrigatório para sessão não autenticada.")

    return f"guest:{client_id}", False


def _to_conversation_dto(conversation: Conversation) -> ConversationDTO:
    return ConversationDTO(
        id=conversation.id,
        title=conversation.title,
        mode=conversation.mode,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _to_file_dto(file_row: UserFile) -> FileDTO:
    return FileDTO(
        id=file_row.id,
        original_name=file_row.original_name,
        category=file_row.category,
        media_type=file_row.media_type,
        created_at=file_row.created_at,
        thumbnail=_thumbnail_for(file_row),
    )


def _thumbnail_for(file_row: UserFile) -> str:
    extension = Path(file_row.original_name).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return "🖼️"
    if extension in TABLE_EXTENSIONS:
        return "📊"
    if extension in DOCUMENT_EXTENSIONS:
        return "📄"
    return "📎"


def _file_category(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension in TABLE_EXTENSIONS:
        return "table"
    return "document"


def _json_to_sources(raw_value: str | None) -> list[dict[str, str]]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def _read_text_excerpt(path: Path, limit: int = 1200) -> str:
    extension = path.suffix.lower()
    if extension in {".txt", ".md", ".csv"}:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except OSError:
            return ""
    return ""


SEARCH_CONFIRMATION_MARKERS = {
    "sim",
    "procure",
    "quero",
    "faca",
    "faça",
    "faca a busca",
    "faça a busca",
    "busca externa",
    "pode procurar",
    "pesquise",
}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return without_accents.lower().strip()


def _is_external_search_confirmation(message: str) -> bool:
    normalized = _normalize_text(message)
    compact = " ".join(normalized.split())
    if not compact:
        return False

    if compact in SEARCH_CONFIRMATION_MARKERS:
        return True

    if "busca externa" in compact:
        return True

    if len(compact.split()) <= 6 and any(marker in compact for marker in SEARCH_CONFIRMATION_MARKERS):
        return True

    return False


def _infer_previous_topic(user_history: list[str]) -> str | None:
    for item in reversed(user_history):
        if not item.strip():
            continue
        if _is_external_search_confirmation(item):
            continue
        return item.strip()
    return None


def _generate_answer(
    mode: ChatMode,
    content: str,
    owner_id: str,
    authenticated: bool,
    conversation_id: str,
    web_search_enabled: bool = False,
) -> tuple[str, bool, str | None, list[dict[str, str]], list[FileDTO]]:
    llm_provider = LLMProvider()
    general_answer_service = GeneralAnswerService()
    settings = get_settings()

    with SessionLocal() as db:
        attached_files = db.scalars(
            select(UserFile)
            .where(UserFile.conversation_id == conversation_id)
            .order_by(UserFile.created_at.desc())
        ).all()

        recent_messages = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(8)
        ).all()

        user_history = [item.content for item in reversed(recent_messages) if item.role == "user"]
        if user_history and user_history[-1].strip() == content.strip():
            user_history = user_history[:-1]

        history_for_inference = user_history

        if mode == ChatMode.GENERAL:
            if not web_search_enabled and _is_external_search_confirmation(content):
                previous_topic = _infer_previous_topic(history_for_inference)
                if previous_topic:
                    general_result = general_answer_service.answer(
                        previous_topic,
                        history_for_inference,
                        allow_web_search=True,
                        force_web_search=True,
                    )
                    answer = f"Perfeito, fiz a busca externa sobre '{previous_topic}'.\n\n{general_result.answer}"
                    return (
                        answer,
                        False,
                        None,
                        general_result.sources or [],
                        [_to_file_dto(item) for item in attached_files],
                    )

            general_result = general_answer_service.answer(
                content,
                history_for_inference,
                allow_web_search=web_search_enabled,
                force_web_search=web_search_enabled,
            )
            return (
                general_result.answer,
                False,
                None,
                general_result.sources or [],
                [_to_file_dto(item) for item in attached_files],
            )

        if mode in {ChatMode.RAG, ChatMode.SQL} and not authenticated:
            return (
                "Faça autenticação para usar este modo.",
                True,
                "authenticate",
                [],
                [_to_file_dto(item) for item in attached_files],
            )

        if mode == ChatMode.RAG:
            files = db.scalars(
                select(UserFile)
                .where(UserFile.owner_id == owner_id, UserFile.category == "document")
                .order_by(UserFile.created_at.desc())
                .limit(12)
            ).all()

            if not files:
                return (
                    "Nenhum documento interno encontrado para este usuário.",
                    False,
                    "upload_and_index_documents",
                    [],
                    [_to_file_dto(item) for item in attached_files],
                )

            context_chunks: list[str] = []
            sources: list[dict[str, str]] = []
            for item in files:
                path = Path(item.storage_path)
                excerpt = _read_text_excerpt(path)
                if excerpt:
                    context_chunks.append(excerpt)
                    sources.append({"file": item.original_name, "excerpt": excerpt[:220]})
                else:
                    sources.append({"file": item.original_name, "excerpt": "Arquivo disponível para consulta."})

            context_text = "\n\n".join(context_chunks) if context_chunks else "Arquivos sem conteúdo textual extraível."
            answer = llm_provider.answer_with_context(content, context_text)
            return (
                answer,
                False,
                None,
                sources,
                [_to_file_dto(item) for item in attached_files],
            )

        tables = db.scalars(
            select(UserFile)
            .where(UserFile.owner_id == owner_id, UserFile.category == "table")
            .order_by(UserFile.created_at.desc())
            .limit(20)
        ).all()

        if not tables:
            return (
                "Nenhuma tabela CSV/XLSX encontrada para este usuário.",
                False,
                "upload_tables",
                [],
                [_to_file_dto(item) for item in attached_files],
            )

        table_names = [item.original_name for item in tables]
        lower_question = content.lower()
        matched_tables = [table for table in table_names if table.lower() in lower_question]
        referenced_tables = matched_tables if matched_tables else table_names[:3]

        answer = (
            "Análise SQL orientada por metadados. "
            f"Tabelas em foco: {', '.join(referenced_tables)}. "
            "Envie uma pergunta mais específica (ex.: agregações, filtros, período) para refinarmos."
        )
        sources = [{"table": name} for name in referenced_tables]
        return (
            answer,
            False,
            None,
            sources,
            [_to_file_dto(item) for item in attached_files],
        )


@router.post("/auth/dev-token")
def create_dev_token(request: DevTokenRequest) -> dict[str, str]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": request.user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=12)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/conversations", response_model=ConversationDTO)
def create_conversation(request: ConversationCreateRequest) -> ConversationDTO:
    owner_id, _ = _resolve_owner(request.client_id, request.access_token)

    title = request.title or "Nova conversa"
    conversation = Conversation(
        owner_id=owner_id,
        title=title,
        mode=request.mode,
    )

    with SessionLocal() as db:
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return _to_conversation_dto(conversation)


@router.get("/conversations", response_model=list[ConversationDTO])
def list_conversations(client_id: str | None = None, access_token: str | None = None) -> list[ConversationDTO]:
    owner_id, _ = _resolve_owner(client_id, access_token)
    with SessionLocal() as db:
        rows = db.scalars(
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.updated_at.desc())
        ).all()
        return [_to_conversation_dto(item) for item in rows]


@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageDTO])
def get_conversation_messages(
    conversation_id: str,
    client_id: str | None = None,
    access_token: str | None = None,
) -> list[ConversationMessageDTO]:
    owner_id, _ = _resolve_owner(client_id, access_token)

    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

        messages = db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at.asc())
        ).all()

        return [
            ConversationMessageDTO(
                id=item.id,
                role=item.role,
                content=item.content,
                created_at=item.created_at,
                sources=_json_to_sources(item.sources),
            )
            for item in messages
        ]

@router.patch("/conversations/{conversation_id}", response_model=ConversationDTO)
def update_conversation(
    conversation_id: str,
    request: ConversationUpdateRequest,
    client_id: str | None = None,
    access_token: str | None = None,
) -> ConversationDTO:
    owner_id, _ = _resolve_owner(client_id, access_token)

    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

        if request.mode is not None:
            conversation.mode = request.mode

        if request.title:
            conversation.title = request.title[:200]

        conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(conversation)
        return _to_conversation_dto(conversation)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    client_id: str | None = None,
    access_token: str | None = None,
) -> dict[str, str]:
    owner_id, _ = _resolve_owner(client_id, access_token)
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

        db.delete(conversation)
        db.commit()

    return {"status": "deleted"}


@router.post("/conversations/{conversation_id}/messages", response_model=ChatSendResponse)
def send_message(
    conversation_id: str,
    request: ChatSendRequest,
) -> ChatSendResponse:
    owner_id, authenticated = _resolve_owner(request.client_id, request.access_token)

    conversation_mode: ChatMode | None = None
    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        conversation_mode = ChatMode(conversation.mode)

        user_message = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=request.content,
        )
        db.add(user_message)
        db.commit()

    answer, requires_login, next_action, sources, uploaded_files = _generate_answer(
        mode=conversation_mode,
        content=request.content,
        owner_id=owner_id,
        authenticated=authenticated,
        conversation_id=conversation_id,
        web_search_enabled=request.web_search_enabled,
    )

    with SessionLocal() as db:
        assistant_message = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            sources=json.dumps(sources, ensure_ascii=False),
        )
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = datetime.utcnow()
            if conversation.title == "Nova conversa":
                conversation.title = request.content[:80]

        db.add(assistant_message)
        db.commit()

    return ChatSendResponse(
        conversation_id=conversation_id,
        answer=answer,
        mode=conversation_mode,
        requires_login=requires_login,
        next_action=next_action,
        sources=sources,
        uploaded_files=uploaded_files,
    )


@router.post("/files/upload", response_model=FileDTO)
async def upload_file(
    conversation_id: str,
    mode: ChatMode,
    file: UploadFile = File(...),
    client_id: str | None = None,
    access_token: str | None = None,
) -> FileDTO:
    owner_id, authenticated = _resolve_owner(client_id, access_token)

    if mode in {ChatMode.RAG, ChatMode.SQL} and not authenticated:
        raise HTTPException(status_code=401, detail="Autenticação obrigatória para upload em RAG/SQL.")

    with SessionLocal() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None or conversation.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    extension = Path(file.filename or "").suffix.lower()
    category = _file_category(file.filename or "arquivo")

    owner_folder = _storage_root() / _safe_owner_folder(owner_id)
    owner_folder.mkdir(parents=True, exist_ok=True)

    generated_name = f"{uuid4()}{extension}"
    save_path = owner_folder / generated_name

    content = await file.read()
    save_path.write_bytes(content)

    row = UserFile(
        owner_id=owner_id,
        conversation_id=conversation_id,
        filename=generated_name,
        original_name=file.filename or generated_name,
        media_type=file.content_type or "application/octet-stream",
        category=category,
        storage_path=str(save_path),
    )

    with SessionLocal() as db:
        db.add(row)
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)

    return _to_file_dto(row)


@router.get("/files/documents", response_model=list[FileDTO])
def list_documents(client_id: str | None = None, access_token: str | None = None) -> list[FileDTO]:
    owner_id, _ = _resolve_owner(client_id, access_token)

    with SessionLocal() as db:
        rows = db.scalars(
            select(UserFile)
            .where(UserFile.owner_id == owner_id, UserFile.category == "document")
            .order_by(UserFile.created_at.desc())
        ).all()

    return [_to_file_dto(item) for item in rows]


@router.get("/files/tables", response_model=list[FileDTO])
def list_tables(client_id: str | None = None, access_token: str | None = None) -> list[FileDTO]:
    owner_id, _ = _resolve_owner(client_id, access_token)

    with SessionLocal() as db:
        rows = db.scalars(
            select(UserFile)
            .where(UserFile.owner_id == owner_id, UserFile.category == "table")
            .order_by(UserFile.created_at.desc())
        ).all()

    return [_to_file_dto(item) for item in rows]
