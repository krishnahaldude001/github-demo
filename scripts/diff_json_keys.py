"""Phase 2: key-level JSON diff between two git refs for source files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    REPO_ROOT,
    artifacts_dir,
    flatten_json,
    git_name_status,
    git_show,
    is_source_json_path,
    list_worktree_source_paths,
    load_config,
    parse_json_text,
    to_repo_posix,
)


def diff_flat_maps(
    base_flat: dict[str, Any] | None, head_flat: dict[str, Any] | None
) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    """Return added_keys, changed_keys, deleted_keys, and unit payloads for translate."""
    base_flat = base_flat or {}
    head_flat = head_flat or {}
    added = sorted(k for k in head_flat if k not in base_flat)
    deleted = sorted(k for k in base_flat if k not in head_flat)
    changed = sorted(
        k for k in head_flat if k in base_flat and base_flat[k] != head_flat[k]
    )
    units: dict[str, Any] = {
        "added": {k: head_flat[k] for k in added},
        "changed": {k: {"old": base_flat[k], "new": head_flat[k]} for k in changed},
        "deleted": {k: base_flat[k] for k in deleted},
    }
    return added, changed, deleted, units


def classify_file(
    source_path: str,
    base_text: str | None,
    head_text: str | None,
    locales: list[str],
) -> dict[str, Any] | None:
    if base_text is None and head_text is None:
        return None

    try:
        if base_text is None and head_text is not None:
            change_type = "added"
            head_flat = flatten_json(parse_json_text(head_text))
            added, changed, deleted, units = diff_flat_maps(None, head_flat)
        elif base_text is not None and head_text is None:
            change_type = "deleted"
            base_flat = flatten_json(parse_json_text(base_text))
            added, changed, deleted, units = diff_flat_maps(base_flat, None)
        else:
            change_type = "modified"
            base_flat = flatten_json(parse_json_text(base_text))
            head_flat = flatten_json(parse_json_text(head_text))
            added, changed, deleted, units = diff_flat_maps(base_flat, head_flat)
            if not added and not changed and not deleted:
                return None
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return {
            "source_path": source_path,
            "change_type": "error",
            "added_keys": [],
            "changed_keys": [],
            "deleted_keys": [],
            "locale_targets": locales,
            "units": {"added": {}, "changed": {}, "deleted": {}},
            "head_exists": head_text is not None,
            "base_exists": base_text is not None,
            "error": str(exc),
        }

    return {
        "source_path": source_path,
        "change_type": change_type,
        "added_keys": added,
        "changed_keys": changed,
        "deleted_keys": deleted,
        "locale_targets": locales,
        "units": units,
        "head_exists": head_text is not None,
        "base_exists": base_text is not None,
    }


def collect_source_paths(base: str, head: str, config: dict) -> list[str]:
    paths: set[str] = set()
    for _status, path in git_name_status(base, head):
        norm = to_repo_posix(path)
        if is_source_json_path(norm, config):
            paths.add(norm)
    # Untracked / new worktree sources not yet in base
    if head.upper() == "WORKTREE":
        for path in list_worktree_source_paths(config):
            if git_show(base, path) is None and git_show("WORKTREE", path) is not None:
                paths.add(path)
    return sorted(paths)


def build_diff_report(base: str, head: str, config: dict | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    locales = list(cfg.get("target_locales", ["fr_ca"]))
    files: list[dict[str, Any]] = []

    for source_path in collect_source_paths(base, head, cfg):
        entry = classify_file(
            source_path,
            git_show(base, source_path),
            git_show(head, source_path),
            locales,
        )
        if entry:
            files.append(entry)

    return {
        "base": base,
        "head": head,
        "source_language": cfg.get("source_language", "en"),
        "target_locales": locales,
        "files": files,
        "summary": {
            "file_count": len(files),
            "added_files": sum(1 for f in files if f["change_type"] == "added"),
            "modified_files": sum(1 for f in files if f["change_type"] == "modified"),
            "deleted_files": sum(1 for f in files if f["change_type"] == "deleted"),
            "error_files": sum(1 for f in files if f["change_type"] == "error"),
            "added_keys": sum(len(f["added_keys"]) for f in files),
            "changed_keys": sum(len(f["changed_keys"]) for f in files),
            "deleted_keys": sum(len(f["deleted_keys"]) for f in files),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff JSON keys for localization")
    parser.add_argument("--base", default="HEAD", help="Base git ref")
    parser.add_argument(
        "--head",
        default="WORKTREE",
        help="Head git ref, or WORKTREE for current files on disk",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output path (default: artifacts/diff-report.json)",
    )
    args = parser.parse_args()

    cfg = load_config()
    out = Path(args.out) if args.out else artifacts_dir(cfg) / "diff-report.json"
    if not out.is_absolute():
        out = REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    report = build_diff_report(args.base, args.head, cfg)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = report["summary"]
    print(
        f"Wrote {to_repo_posix(out)} | files={summary['file_count']} "
        f"(+{summary['added_files']} ~{summary['modified_files']} "
        f"-{summary['deleted_files']} !{summary['error_files']}) "
        f"keys(+{summary['added_keys']} ~{summary['changed_keys']} -{summary['deleted_keys']})"
    )
    return 1 if summary["error_files"] else 0


if __name__ == "__main__":
    sys.exit(main())
