import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

ENCRYPTED_PREFIX = "enc:v1:"


@lru_cache
def _cipher() -> Fernet:
    key_material = get_settings().health_info_encryption_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(key_material).digest())
    return Fernet(key)


def encrypt_health_info(value: str | None) -> str | None:
    if value is None or value.startswith(ENCRYPTED_PREFIX):
        return value
    token = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_health_info(value: str | None) -> str | None:
    if value is None:
        return None
    if not value.startswith(ENCRYPTED_PREFIX):
        return value
    try:
        token = value.removeprefix(ENCRYPTED_PREFIX).encode("ascii")
        return _cipher().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("health_info 无法解密，请检查加密密钥配置") from exc
