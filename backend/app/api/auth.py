from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt

from app.config import settings
from app.schemas.auth import LoginRequest, Token, TokenData
from app.api.deps import get_current_user

router = APIRouter()

# Hardcoded dev users — replace with DB lookup in production
_DEV_USERS = {
    "admin":   {"password": "admin123",   "role": "admin"},
    "agent":   {"password": "agent123",   "role": "agent"},
    "manager": {"password": "manager123", "role": "manager"},
}


def create_access_token(sub: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode(
        {"sub": sub, "role": role, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


@router.post("/auth/login", response_model=Token)
def login(body: LoginRequest):
    user = _DEV_USERS.get(body.username)
    if not user or user["password"] != body.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return Token(access_token=create_access_token(sub=body.username, role=user["role"]))


@router.get("/auth/me")
def me(current_user: TokenData = Depends(get_current_user)):
    return {"username": current_user.sub, "role": current_user.role}
