from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

HARD_UPLOAD_MAX_BYTES = 26_214_400


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/workbench.db")
    upload_dir: Path = Path(os.getenv("UPLOAD_DIR", "./data/uploads")).resolve()
    upload_max_bytes: int = min(
        max(1, int(os.getenv("UPLOAD_MAX_BYTES", str(HARD_UPLOAD_MAX_BYTES)))),
        HARD_UPLOAD_MAX_BYTES,
    )
    rag_mode: str = os.getenv("RAG_MODE", "mock")
    web_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv(
            "WEB_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
        ).split(",")
        if origin.strip()
    )


settings = Settings()
