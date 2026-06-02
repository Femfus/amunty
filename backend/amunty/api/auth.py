"""Auth API — login and password change."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from amunty.deps import DB, CurrentUser
from amunty.models.user import User
from amunty.security import create_access_token, hash_password, verify_password

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: DB) -> LoginResponse:
    """Authenticate with the admin password and receive a JWT token."""
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=500, detail="No users exist. Restart the server.")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )

    token = create_access_token(user.id)
    return LoginResponse(token=token)


@router.post("/change-password", status_code=200)
async def change_password(body: ChangePasswordRequest, db: DB, user: CurrentUser) -> dict:
    """Change the admin password."""
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    user.password_hash = hash_password(body.new_password)
    await db.flush()
    return {"detail": "Password changed successfully."}


@router.get("/me")
async def get_me(user: CurrentUser) -> dict:
    """Return current user info."""
    return {"id": user.id, "created_at": user.created_at.isoformat()}
