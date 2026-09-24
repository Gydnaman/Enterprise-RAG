from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import PurePath

from rag_workbench.config import HARD_UPLOAD_MAX_BYTES


def normalize_display_filename(filename: str) -> str:
    value = unicodedata.normalize("NFC", PurePath(filename.replace("\\", "/")).name)
    value = "".join(ch for ch in value if ch.isprintable() and ch not in "/\\")
    encoded = value.encode("utf-8")[:255]
    while True:
        try:
            value = encoded.decode("utf-8")
            break
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return value or "upload.txt"


def validate_idempotency_key(value: str | None) -> str:
    if (
        value is None
        or not 1 <= len(value) <= 128
        or not value.isascii()
        or not value.isprintable()
    ):
        raise ValueError("invalid_request")
    return value


def validate_upload(filename: str, data: bytes, maximum: int) -> tuple[str, str]:
    name = normalize_display_filename(filename)
    suffix = PurePath(name).suffix.lower()
    if suffix not in {".pdf", ".docx", ".md", ".txt"}:
        raise ValueError("unsupported_file")
    if len(data) > min(maximum, HARD_UPLOAD_MAX_BYTES):
        raise ValueError("file_too_large")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("file_signature_mismatch")
        media = "application/pdf"
    elif suffix == ".docx":
        if not data.startswith(b"PK\x03\x04") or b"word/document.xml" not in data:
            raise ValueError("file_signature_mismatch")
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        try:
            data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("file_signature_mismatch") from exc
        media = "text/markdown" if suffix == ".md" else "text/plain"
    return media, hashlib.sha256(data).hexdigest()


def safe_error_code(value: str) -> str:
    return value if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value) else "internal_error"
