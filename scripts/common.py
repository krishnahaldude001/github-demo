"""Shared helpers for the localization pipeline."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "l10n.json"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def artifacts_dir(config: dict | None = None) -> Path:
    cfg = config or load_config()
    path = REPO_ROOT / cfg.get("artifacts_dir", "artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_locale_dir(name: str, config: dict | None = None) -> bool:
    cfg = config or load_config()
    return name in set(cfg.get("exclude_locale_dirs", []))


def to_repo_posix(path: Path | str) -> str:
    """Normalize a path to repo-relative POSIX (git-friendly)."""
    p = Path(path)
    if p.is_absolute():
        p = p.relative_to(REPO_ROOT)
    return PurePosixPath(*p.parts).as_posix()


def is_source_json_path(rel_path: str, config: dict | None = None) -> bool:
    """True for Folder N/file.json; false for locale subfolders and other paths."""
    cfg = config or load_config()
    parts = PurePosixPath(rel_path.replace("\\", "/")).parts
    if len(parts) != 2:
        return False
    root, name = parts
    if root not in cfg.get("source_roots", []):
        return False
    if is_locale_dir(root, cfg):
        return False
    return name.endswith(".json")


def iter_source_json_files(config: dict | None = None) -> list[Path]:
    """Return source JSON files (folder-root only; skip locale subfolders)."""
    cfg = config or load_config()
    sources: list[Path] = []
    for root_name in cfg.get("source_roots", []):
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.json")):
            if path.is_file():
                sources.append(path)
    return sources


def list_worktree_source_paths(config: dict | None = None) -> list[str]:
    return [to_repo_posix(p) for p in iter_source_json_files(config)]


def target_path_for(source: Path, locale: str, config: dict | None = None) -> Path:
    """Map Folder X/file.json → Folder X/<locale>/file.json."""
    _ = config
    return source.parent / locale / source.name


def flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested dicts to dotted keys; lists/scalars are leaves."""
    items: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            items.update(flatten_json(child, path))
    else:
        if not prefix:
            raise ValueError("JSON root must be an object for key-level diff")
        items[prefix] = value
    return items


def unflatten_json(flat: dict[str, Any]) -> dict:
    """Rebuild nested dict from dotted keys (best-effort for string leaves)."""
    root: dict[str, Any] = {}
    for dotted, value in flat.items():
        parts = dotted.split(".")
        cursor = root
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return root


def parse_json_text(text: str | None) -> dict | None:
    if text is None:
        return None
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object at root")
    return data


def read_worktree_text(rel_path: str) -> str | None:
    path = REPO_ROOT / Path(*PurePosixPath(rel_path).parts)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def git_show(ref: str, rel_path: str) -> str | None:
    """Return file contents at ref, or None if missing. ref=WORKTREE reads disk."""
    if ref.upper() == "WORKTREE":
        return read_worktree_text(rel_path)
    posix = to_repo_posix(rel_path)
    result = subprocess.run(
        ["git", "show", f"{ref}:{posix}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return result.stdout


def set_nested_value(root: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    cursor: Any = root
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value


def delete_nested_value(root: dict, dotted: str) -> None:
    parts = dotted.split(".")
    cursor: Any = root
    for part in parts[:-1]:
        if part not in cursor or not isinstance(cursor[part], dict):
            return
        cursor = cursor[part]
    cursor.pop(parts[-1], None)


def load_json_file(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def glossary_text() -> str:
    path = REPO_ROOT / "docs" / "glossary.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def git_name_status(base: str, head: str) -> list[tuple[str, str]]:
    """Return list of (status, path) from git diff --name-status."""
    if head.upper() == "WORKTREE":
        result = subprocess.run(
            ["git", "diff", "--name-status", "--find-renames", base],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    else:
        result = subprocess.run(
            ["git", "diff", "--name-status", "--find-renames", base, head],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"git diff failed ({base}..{head}): {result.stderr.strip() or result.stdout}"
        )
    rows: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            rows.append(("D", parts[1]))
            rows.append(("A", parts[2]))
        elif status.startswith("C") and len(parts) >= 3:
            rows.append(("A", parts[2]))
        elif len(parts) >= 2:
            rows.append((status[0], parts[-1]))
    return rows
