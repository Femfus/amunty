"""FastAPI dependency injection helpers."""

from __future__ import annotations

from typing import Annotated

import jwt
import jwt.exceptions
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from amunty.config import settings
from amunty.database import get_db
from amunty.models.user import User
from amunty.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Extract and validate the current user from the JWT bearer token.

    If auth is disabled globally, return the first (admin) user.
    """
    if not settings.auth_enabled:
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=500, detail="No users exist.")
        return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload["sub"]
    except (jwt.exceptions.PyJWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return user


# Type alias for use in route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
