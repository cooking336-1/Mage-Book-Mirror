"""Custom model fields for cryptographic security and statutory compliance.

Provides:
- EncryptedCharField: Transparent AES-128-CBC + HMAC-SHA256 (Fernet) field-level
  encryption for personally identifiable information (PII) such as Ghana Card
  PINs and GRA Taxpayer Identification Numbers (TINs) per Act 843.
"""

from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet() -> Fernet:
    """Retrieves or instantiates a Fernet cipher instance using FIELD_ENCRYPTION_KEY."""
    raw_key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if not raw_key:
        raise ValueError(
            "FIELD_ENCRYPTION_KEY is not configured in Django settings. "
            "Please configure a valid 32-byte base64-encoded key."
        )
    key_bytes = raw_key.encode("utf-8") if isinstance(raw_key, str) else raw_key
    return Fernet(key_bytes)


class EncryptedCharField(models.CharField):
    """Transparent column-level encryption field using cryptography.fernet.Fernet.

    Persists ciphertext in the database column while presenting decrypted plaintext
    to the Python runtime, ORM, serializers, and validators.
    """

    description = "Fernet encrypted character string"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Fernet tokens are ~100-120 chars; enforce minimum DB column width of 255 chars
        max_length = kwargs.get("max_length")
        if max_length is None or max_length < 255:
            kwargs["max_length"] = 255
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, list[Any], dict[str, Any]]:
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs

    def get_internal_type(self) -> str:
        return "CharField"

    def get_prep_value(self, value: Any) -> Any:
        """Encrypts plaintext string to Fernet ciphertext token before database write."""
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value

        str_val = str(value)
        # Avoid double encryption if value is already a valid Fernet token
        if str_val.startswith("gAAAAA"):
            try:
                get_fernet().decrypt(str_val.encode("utf-8"))
                return str_val
            except (InvalidToken, Exception):
                pass

        fernet = get_fernet()
        encrypted_bytes = fernet.encrypt(str_val.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def from_db_value(self, value: Any, expression: Any, connection: Any) -> Any:
        """Decrypts Fernet ciphertext token from database column into plaintext string."""
        if value is None or value == "":
            return value

        str_val = str(value)
        if str_val.startswith("gAAAAA"):
            try:
                fernet = get_fernet()
                decrypted_bytes = fernet.decrypt(str_val.encode("utf-8"))
                return decrypted_bytes.decode("utf-8")
            except (InvalidToken, Exception):
                # If key changed or legacy plaintext, return original value to prevent data loss
                return str_val
        return str_val

    def to_python(self, value: Any) -> Any:
        """Ensures value accessed in python is decrypted."""
        if value is None or value == "":
            return value

        str_val = str(value)
        if str_val.startswith("gAAAAA"):
            try:
                fernet = get_fernet()
                decrypted_bytes = fernet.decrypt(str_val.encode("utf-8"))
                return decrypted_bytes.decode("utf-8")
            except (InvalidToken, Exception):
                return str_val
        return str_val
