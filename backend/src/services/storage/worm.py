"""Phase 9E — WORM storage backend abstraction (filesystem pilot)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from config import settings


class WormStorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, *, sealed: bool = False) -> str:
        ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Returns False when WORM/hold prevents deletion."""
        ...


class FilesystemWormBackend(WormStorageBackend):
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.worm_filesystem_path
        self.root.mkdir(parents=True, exist_ok=True)
        self.sealed_dir = self.root / "sealed"
        self.sealed_dir.mkdir(exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("..", "").lstrip("/")
        return self.root / safe

    def put(self, key: str, data: bytes, *, sealed: bool = False) -> str:
        dest = (self.sealed_dir if sealed else self.root) / key.replace("..", "").lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> bool:
        path = self._path(key)
        if not path.exists():
            return True
        if path.is_relative_to(self.sealed_dir):
            return False
        path.unlink()
        return True


def get_worm_backend() -> WormStorageBackend | None:
    backend = settings.worm_backend.strip().lower()
    if backend in ("", "none", "disabled"):
        return None
    if backend == "filesystem":
        return FilesystemWormBackend()
    raise ValueError(f"Unsupported WORM_BACKEND: {backend}")
