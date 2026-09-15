"""JWT-based auth for the demo's single hardcoded user (see config.py's
``demo_username``/``demo_password``). Not designed to scale past one user --
swap for a real user store if that's ever needed.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import get_settings

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def authenticate_user(username: str, password: str) -> bool:
    settings = get_settings()
    if username != settings.demo_username:
        return False
    # Hashed on every call rather than precomputed/cached: this is a demo
    # single-user check, not a hot path, and it keeps config.py's
    # demo_password a plain, human-editable env var instead of requiring a
    # precomputed bcrypt hash string.
    stored_hash = bcrypt.hashpw(settings.demo_password.encode(), bcrypt.gensalt())
    return bcrypt.checkpw(password.encode(), stored_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user(token: str = Depends(_oauth2_scheme)) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if username is None:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION from None
    return username
