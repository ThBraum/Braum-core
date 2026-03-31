"""
Configuração de logging estruturado para observabilidade.

Provides:
- Structured logging com JSON
- Request/Response tracing
- Performance metrics
- Sensitive data filtering
"""

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class SensitiveDataFilter(logging.Filter):
    """Remove dados sensíveis de logs."""

    SENSITIVE_PATTERNS = [
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "authorization_header",
        "access_token",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg"):
            for pattern in self.SENSITIVE_PATTERNS:
                if isinstance(record.msg, str) and pattern.lower() in record.msg.lower():
                    record.msg = f"[REDACTED: {pattern}]"
        return True


class JSONFormatter(logging.Formatter):
    """Formata logs como JSON estruturado."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Configura logging estruturado para toda a aplicação."""
    settings = get_settings()

    # Logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Remove handlers padrão
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    console_formatter = (
        JSONFormatter()
        if settings.debug
        else logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(SensitiveDataFilter())
    root_logger.addHandler(console_handler)

    # Handler para arquivo (se configurado)
    if settings.log_file_path:
        log_dir = Path(settings.log_file_path).parent
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            settings.log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(SensitiveDataFilter())
        root_logger.addHandler(file_handler)

    # Desabilita loggers verbose de libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
