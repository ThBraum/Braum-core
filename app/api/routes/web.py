from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def chat_ui() -> str:
    html_path = Path(__file__).resolve().parents[2] / "web" / "chat.html"
    with html_path.open("r", encoding="utf-8") as file_handle:
        return file_handle.read()
