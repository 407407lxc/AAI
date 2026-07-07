from __future__ import annotations

import difflib
from pathlib import Path
from typing import Iterable

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cu",
    ".cuh",
    ".cpp",
    ".h",
    ".hpp",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

IGNORE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def _read_text(path: Path) -> list[str] | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return None


def capture_directory_diff(
    before_dir: str | Path,
    after_dir: str | Path,
    output_path: str | Path,
    before_label: str = "parent",
    after_label: str = "candidate",
) -> Path:
    """Write a git-like unified diff between two text-file directory trees."""
    before = Path(before_dir)
    after = Path(after_dir)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    before_files = {p.relative_to(before).as_posix(): p for p in _iter_files(before)} if before.exists() else {}
    after_files = {p.relative_to(after).as_posix(): p for p in _iter_files(after)} if after.exists() else {}
    all_paths = sorted(set(before_files) | set(after_files))

    chunks: list[str] = []
    for rel in all_paths:
        lhs = before_files.get(rel)
        rhs = after_files.get(rel)
        lhs_text = _read_text(lhs) if lhs else []
        rhs_text = _read_text(rhs) if rhs else []

        if lhs_text is None or rhs_text is None:
            if lhs and rhs and lhs.read_bytes() == rhs.read_bytes():
                continue
            chunks.append(f"diff --git a/{rel} b/{rel}\n")
            chunks.append("Binary files differ or file is not UTF-8 text\n")
            continue

        if lhs_text == rhs_text:
            continue

        chunks.append(f"diff --git a/{rel} b/{rel}\n")
        from_file = f"a/{rel}" if lhs else "/dev/null"
        to_file = f"b/{rel}" if rhs else "/dev/null"
        chunks.extend(
            difflib.unified_diff(
                lhs_text,
                rhs_text,
                fromfile=f"{before_label}/{from_file}",
                tofile=f"{after_label}/{to_file}",
            )
        )
        if chunks and not chunks[-1].endswith("\n"):
            chunks[-1] += "\n"

    if not chunks:
        chunks.append("# No text differences detected.\n")
    output.write_text("".join(chunks), encoding="utf-8")
    return output
