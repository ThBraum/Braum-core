import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from jose import jwt
from sqlalchemy import or_, select

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.domain.auth_schemas import AuthResponse, LoginRequest, RegisterRequest, UserMeDTO
from app.infrastructure.db.database import SessionLocal
from app.infrastructure.db.models import User


router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, hash_value = stored_hash.split("$", maxsplit=1)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return hmac.compare_digest(digest.hex(), hash_value)


def _create_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=12)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/register", response_model=AuthResponse)
def register(request: RegisterRequest) -> AuthResponse:
    username = request.username.strip()
    email = request.email.strip().lower()

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Email inválido.")

    with SessionLocal() as db:
        existing = db.scalars(
            select(User).where(or_(User.username == username, User.email == email)).limit(1)
        ).first()
        if existing:
            if existing.username == username:
                raise HTTPException(status_code=409, detail="Username já está em uso.")
            raise HTTPException(status_code=409, detail="Email já está em uso.")

        user = User(
            username=username,
            email=email,
            password_hash=_hash_password(request.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return AuthResponse(access_token=_create_token(user.id))


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest) -> AuthResponse:
    login_value = request.email_or_username.strip()
    with SessionLocal() as db:
        user = db.scalars(
            select(User)
            .where(or_(User.username == login_value, User.email == login_value.lower()))
            .limit(1)
        ).first()

        if user is None or not _verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    return AuthResponse(access_token=_create_token(user.id))


@router.get("/me", response_model=UserMeDTO)
def me(access_token: str) -> UserMeDTO:
    payload = decode_access_token(access_token)
    user_id = str(payload["sub"])

    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        return UserMeDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
        )
