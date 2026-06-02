"""Security utilities: password hashing, JWT tokens, Fernet encryption, first-run setup."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from cryptography.fernet import Fernet

from amunty.config import settings

logger = logging.getLogger("amunty.security")

# ---------------------------------------------------------------------------
# Fernet encryption for API keys at rest
# ---------------------------------------------------------------------------

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-load Fernet cipher.  Key is persisted to disk so it survives restarts."""
    global _fernet
    if _fernet is not None:
        return _fernet

    key_path = settings.data_dir / "encryption.key"

    if settings.encryption_key:
        key = settings.encryption_key.encode()
    elif key_path.exists():
        key = key_path.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(key)
        logger.info("Generated new encryption key at %s", key_path)

    _fernet = Fernet(key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string for safe database storage."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a previously encrypted string."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def create_access_token(user_id: str) -> str:
    """Create a signed JWT access token."""
    payload = {
        "sub": user_id,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT token.  Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# First-run setup
# ---------------------------------------------------------------------------


async def ensure_first_run() -> None:
    """Create the admin user if no users exist yet."""
    from amunty.database import async_session
    from amunty.models.user import User

    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        existing = result.scalar_one_or_none()

        if existing is not None:
            return  # Already initialized

        # Generate or use pre-set password
        password = settings.amunty_admin_password or secrets.token_urlsafe(18)

        import uuid

        user = User(
            id=str(uuid.uuid4()),
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.commit()

        logger.warning(
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║  [Amunty] First-run setup complete!                     ║\n"
            "║  Admin password: %-38s ║\n"
            "║  Change it in Settings after login.                     ║\n"
            "╚══════════════════════════════════════════════════════════╝",
            password,
        )
