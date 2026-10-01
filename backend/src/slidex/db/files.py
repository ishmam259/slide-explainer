"""Content-addressed file store: data/files/<sha256[:2]>/<sha256>.<ext>."""

from __future__ import annotations

import hashlib
import mimetypes
import re
import shutil
import tempfile
from pathlib import Path

_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FileStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _target(self, digest: str, ext: str) -> Path:
        if not _EXT_RE.fullmatch(ext):
            raise ValueError(f"Invalid extension: {ext!r}")
        return self.root / digest[:2] / f"{digest}.{ext}"

    def put_bytes(self, data: bytes, ext: str) -> str:
        digest = sha256_bytes(data)
        target = self._target(digest, ext.lower())
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
                tmp.write(data)
            Path(tmp.name).replace(target)
        return digest

    def put_file(self, src: Path, ext: str) -> str:
        digest = sha256_file(src)
        target = self._target(digest, ext.lower())
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".part")
            shutil.copyfile(src, tmp)
            tmp.replace(target)
        return digest

    def path(self, digest: str) -> Path:
        if not _HASH_RE.fullmatch(digest):
            raise ValueError("Invalid file hash")
        matches = [p for p in (self.root / digest[:2]).glob(f"{digest}.*") if p.suffix != ".part"]
        if not matches:
            raise FileNotFoundError(digest)
        return matches[0]

    def exists(self, digest: str) -> bool:
        try:
            self.path(digest)
        except FileNotFoundError, ValueError:
            return False
        return True

    def read(self, digest: str) -> bytes:
        return self.path(digest).read_bytes()

    def media_type(self, digest: str) -> str:
        guessed, _ = mimetypes.guess_type(self.path(digest).name)
        return guessed or "application/octet-stream"
