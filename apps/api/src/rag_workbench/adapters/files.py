from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from rag_workbench.config import settings

_OPAQUE_KEY = re.compile(r"^(?:file|stage)_[a-f0-9]{32}$")


class LocalFileStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.upload_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str, suffix: str) -> Path:
        if not _OPAQUE_KEY.fullmatch(key):
            raise ValueError("invalid_storage_key")
        path = (self.root / f"{key}{suffix}").resolve()
        if path.parent != self.root:
            raise ValueError("invalid_storage_key")
        return path

    async def stage(self, upload: UploadFile, limit: int) -> tuple[str, int, str]:
        stage_key = f"stage_{uuid.uuid4().hex}"
        path = self._path(stage_key, ".part")
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("xb") as stream:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("file_too_large")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            return stage_key, size, digest.hexdigest()
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def open(self, storage_key: str) -> BinaryIO:
        return self._path(storage_key, ".bin").open("rb")

    def staged_path(self, staged_key: str) -> Path:
        return self._path(staged_key, ".part")

    def final_path(self, storage_key: str) -> Path:
        return self._path(storage_key, ".bin")

    def finalize(self, staged_key: str, storage_key: str) -> None:
        source, destination = self.staged_path(staged_key), self.final_path(storage_key)
        if destination.exists():
            return
        os.replace(source, destination)

    def digest(self, key: str, staged: bool) -> str | None:
        path = self.staged_path(key) if staged else self.final_path(key)
        if not path.is_file():
            return None
        result = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                result.update(chunk)
        return result.hexdigest()

    def discard_stage(self, staged_key: str) -> None:
        self.staged_path(staged_key).unlink(missing_ok=True)

    def validate_staged(self, staged_key: str, filename: str) -> str:
        from rag_workbench.adapters.upload_validation import validate_staged_file

        return validate_staged_file(self.staged_path(staged_key), filename)
