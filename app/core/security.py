from collections.abc import Mapping
from typing import Any

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.errors import AppError


def decode_access_token(token: str) -> Mapping[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise AppError(
            message="Token JWT inválido.",
            code="auth.invalid_jwt",
            status_code=401,
        ) from exc

    if not payload.get("sub"):
        raise AppError(
            message="JWT sem claim 'sub'.",
            code="auth.invalid_claims",
            status_code=401,
        )

    return payload
