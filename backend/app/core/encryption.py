"""
Token encryption module using authenticated Fernet encryption (AES-128-CBC + HMAC-SHA256).
Protects OAuth refresh tokens at rest.
"""

import base64
import hashlib
from typing import Optional
import structlog
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

log = structlog.get_logger(__name__)

_fernet_instance: Optional[Fernet] = None


def get_fernet_key() -> bytes:
    """
    Derive or format a valid 32-byte urlsafe base64 Fernet key.
    Uses TOKEN_ENCRYPTION_KEY if provided, or derives safely from SECRET_KEY.
    """
    raw_key = settings.token_encryption_key
    if raw_key and raw_key.strip():
        key_str = raw_key.strip()
        # If it's already a valid Fernet key (44 chars urlsafe base64 of 32 bytes)
        try:
            decoded = base64.urlsafe_b64decode(key_str.encode("utf-8"))
            if len(decoded) == 32:
                return key_str.encode("utf-8")
        except Exception:
            pass

        # Otherwise derive deterministically via SHA-256
        derived = hashlib.sha256(key_str.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(derived)

    # Fallback to SECRET_KEY derivation for development/testing
    log.warning(
        "TOKEN_ENCRYPTION_KEY not set — deriving key from SECRET_KEY. "
        "Set TOKEN_ENCRYPTION_KEY in production."
    )
    derived = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def get_fernet() -> Fernet:
    """Get or create singleton Fernet instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = get_fernet_key()
        _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_token(token: str) -> str:
    """
    Encrypt a plaintext token string into an authenticated ciphertext string.
    Never returns plaintext.
    """
    if not token:
        raise ValueError("Cannot encrypt an empty token")
    fernet = get_fernet()
    encrypted_bytes = fernet.encrypt(token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an authenticated ciphertext string back into the original token.
    Raises ValueError on tampering or invalid key.
    """
    if not encrypted_token:
        raise ValueError("Cannot decrypt an empty token")
    fernet = get_fernet()
    try:
        decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken as exc:
        log.error("Failed to decrypt token: invalid ciphertext or corrupted key")
        raise ValueError("Token decryption failed: invalid ciphertext or corrupted key") from exc
