from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from mobile_api.db import get_db
from mobile_api.models import User
from mobile_api.settings import mobile_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user: User) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=mobile_settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "login": user.login,
        "role": user.role,
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, mobile_settings.jwt_secret, algorithm=mobile_settings.jwt_algorithm)
    return token, expires_at


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            mobile_settings.jwt_secret,
            algorithms=[mobile_settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token payload")

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or not found")
    return user

