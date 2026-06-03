from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


ENCRYPTED_PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    if not settings.email_encryption_key:
        return None
    return Fernet(settings.email_encryption_key.encode("utf-8"))


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "" or value.startswith(ENCRYPTED_PREFIX):
        return value
    fernet = _fernet()
    if fernet is None:
        return value
    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or not value.startswith(ENCRYPTED_PREFIX):
        return value
    fernet = _fernet()
    if fernet is None:
        raise RuntimeError("Falta EMAIL_ENCRYPTION_KEY para leer credenciales cifradas")
    try:
        return fernet.decrypt(value.removeprefix(ENCRYPTED_PREFIX).encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("No fue posible descifrar credenciales de correo") from exc
