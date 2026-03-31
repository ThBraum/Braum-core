from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr = Field(min_length=5, max_length=255)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=120)


class LoginRequest(BaseModel):
    email_or_username: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=120)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMeDTO(BaseModel):
    id: str
    username: str
    email: EmailStr
    created_at: datetime
