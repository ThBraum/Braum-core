from fastapi import APIRouter

from app.domain.schemas import ChatRequest, ChatResponse
from app.services.orchestrator import get_chat_orchestrator


router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    orchestrator = get_chat_orchestrator()
    return orchestrator.handle_request(request)
