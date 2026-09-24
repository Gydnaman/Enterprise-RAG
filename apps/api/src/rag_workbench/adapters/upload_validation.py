from __future__ import annotations

import codecs
import zipfile
from pathlib import Path, PurePath

from rag_workbench.domain.rules import normalize_display_filename


def validate_staged_file(path: Path, original_filename: str) -> str:
    filename = normalize_display_filename(original_filename)
    suffix = PurePath(filename).suffix.lower()
    if suffix not in {".pdf", ".docx", ".md", ".txt"}:
        raise ValueError("unsupported_file")
    with path.open("rb") as stream:
        prefix = stream.read(8)
    if suffix == ".pdf":
        if not prefix.startswith(b"%PDF-"):
            raise ValueError("file_signature_mismatch")
        return "application/pdf"
    if suffix == ".docx":
        if not prefix.startswith(b"PK\x03\x04"):
            raise ValueError("file_signature_mismatch")
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > 10_000 or "word/document.xml" not in archive.namelist():
                    raise ValueError("file_signature_mismatch")
                total = 0
                for item in infos:
                    total += item.file_size
                    if item.file_size > 50 * 1024 * 1024 or total > 200 * 1024 * 1024:
                        raise ValueError("unsupported_file")
                    if item.file_size and (
                        not item.compress_size or item.file_size / item.compress_size > 100
                    ):
                        raise ValueError("unsupported_file")
        except zipfile.BadZipFile as exc:
            raise ValueError("file_signature_mismatch") from exc
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise ValueError("file_signature_mismatch") from exc
    return "text/markdown" if suffix == ".md" else "text/plain"
