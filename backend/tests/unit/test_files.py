import hashlib
from pathlib import Path

import pytest

from slidex.db.files import FileStore


def test_put_bytes_is_content_addressed(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    data = b"hello slides"
    digest = store.put_bytes(data, "png")
    expected = hashlib.sha256(data).hexdigest()
    assert digest == expected
    path = store.path(digest)
    assert path == tmp_path / expected[:2] / f"{expected}.png"
    assert path.read_bytes() == data


def test_identical_bytes_stored_once(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    a = store.put_bytes(b"same", "pdf")
    b = store.put_bytes(b"same", "pdf")
    assert a == b
    assert len(list(tmp_path.rglob("*.pdf"))) == 1


def test_put_file_ignores_original_filename(tmp_path: Path) -> None:
    src = tmp_path / "..evil name;rm -rf.pptx"
    src.write_bytes(b"deck")
    store = FileStore(tmp_path / "store")
    digest = store.put_file(src, "pptx")
    assert store.path(digest).name == f"{digest}.pptx"
    assert "evil" not in str(store.path(digest))


def test_unknown_hash_raises(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.path("0" * 64)


@pytest.mark.parametrize("bad", ["../etc/passwd", "abc", "Z" * 64])
def test_invalid_hash_rejected(tmp_path: Path, bad: str) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(ValueError):
        store.path(bad)


def test_extension_is_sanitized(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(ValueError):
        store.put_bytes(b"x", "png/../../x")
