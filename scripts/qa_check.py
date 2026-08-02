"""Phase 4: rules-based QA for translated JSON targets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    REPO_ROOT,
    artifacts_dir,
    extract_placeholders,
    flatten_json,
    load_config,
    load_json_file,
    target_path_for,
    to_repo_posix,
)

# Old Phrase-style / dummy placeholders
DUMMY_TARGET_RE = re.compile(r"^[\s$]+$")


def looks_untranslated(source: str, target: str) -> bool:
    if not source.strip():
        return False
    if target.strip() == source.strip():
        return True
    if DUMMY_TARGET_RE.match(target.strip()):
        return True
    # mostly dollar signs used as fake MT output
    letters = sum(ch.isalpha() for ch in target)
    dollars = target.count("$")
    if dollars >= 3 and letters == 0:
        return True
    return False


def check_file(entry: dict[str, Any], locale: str) -> dict[str, Any]:
    source_rel = entry["source_path"]
    source_path = REPO_ROOT / Path(*source_rel.replace("\\", "/").split("/"))
    target_path = target_path_for(source_path, locale)

    hard: list[str] = []
    soft: list[str] = []
    info: list[str] = []

    touched = set(entry.get("added_keys", []) + entry.get("changed_keys", []))
    deleted = set(entry.get("deleted_keys", []))

    if entry.get("change_type") == "deleted":
        if target_path.exists():
            hard.append(f"Target still exists after source delete: {to_repo_posix(target_path)}")
        else:
            info.append("Source deleted and target removed.")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    if entry.get("change_type") == "error":
        hard.append(f"Diff error: {entry.get('error')}")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    if not source_path.is_file():
        hard.append(f"Source missing on disk: {source_rel}")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    try:
        source_obj = load_json_file(source_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        hard.append(f"Source JSON invalid: {exc}")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    if not target_path.is_file():
        hard.append(f"Target missing: {to_repo_posix(target_path)}")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    try:
        target_obj = load_json_file(target_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        hard.append(f"Target JSON invalid: {exc}")
        return {
            "source_path": source_rel,
            "target_path": to_repo_posix(target_path),
            "locale": locale,
            "hard": hard,
            "soft": soft,
            "info": info,
        }

    source_flat = flatten_json(source_obj)
    target_flat = flatten_json(target_obj)

    for key in sorted(source_flat):
        if key not in target_flat:
            hard.append(f"Missing key in target: {key}")

    for key in sorted(deleted):
        if key in target_flat:
            hard.append(f"Deleted key still present in target: {key}")

    for key, src_val in sorted(source_flat.items()):
        if key not in target_flat:
            continue
        tgt_val = target_flat[key]
        src_text = src_val if isinstance(src_val, str) else json.dumps(src_val, ensure_ascii=False)
        tgt_text = tgt_val if isinstance(tgt_val, str) else json.dumps(tgt_val, ensure_ascii=False)

        if src_text.strip() and not str(tgt_text).strip():
            hard.append(f"Empty target for non-empty source: {key}")

        src_ph = extract_placeholders(src_text)
        tgt_ph = extract_placeholders(tgt_text)
        if sorted(src_ph) != sorted(tgt_ph):
            hard.append(
                f"Placeholder mismatch on {key}: source={src_ph} target={tgt_ph}"
            )

        untranslated = isinstance(src_val, str) and isinstance(tgt_val, str) and looks_untranslated(
            src_val, tgt_val
        )
        if untranslated:
            msg = f"Likely untranslated: {key}"
            if key in touched:
                hard.append(msg)
            else:
                soft.append(msg)

    # Soft glossary: product names that should stay
    for key in touched:
        src_val = source_flat.get(key)
        tgt_val = target_flat.get(key)
        if not isinstance(src_val, str) or not isinstance(tgt_val, str):
            continue
        for term in ("Phrase", "Team Fusion"):
            if term in src_val and term not in tgt_val:
                soft.append(f"Glossary term '{term}' missing in target for {key}")

    info.append(
        f"Checked {len(source_flat)} source keys; touched={len(touched)}; deleted={len(deleted)}"
    )
    return {
        "source_path": source_rel,
        "target_path": to_repo_posix(target_path),
        "locale": locale,
        "hard": hard,
        "soft": soft,
        "info": info,
    }


def decide_status(file_results: list[dict[str, Any]], config: dict) -> dict[str, str]:
    hard_count = sum(len(f["hard"]) for f in file_results)
    soft_count = sum(len(f["soft"]) for f in file_results)
    labels = config.get("pr", {})
    if hard_count:
        return {
            "status": "FAIL",
            "recommended_label": labels.get("label_needs_review", "needs-l10n-review"),
            "reason": f"{hard_count} hard failure(s)",
        }
    if soft_count:
        return {
            "status": "NEEDS_REVIEW",
            "recommended_label": labels.get("label_needs_review", "needs-l10n-review"),
            "reason": f"{soft_count} soft finding(s)",
        }
    return {
        "status": "PASS",
        "recommended_label": labels.get("label_qa_pass", "l10n-qa-pass"),
        "reason": "All rules checks passed",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# QA Report",
        "",
        f"- **Status:** {report['status']}",
        f"- **Recommended label:** `{report['recommended_label']}`",
        f"- **Reason:** {report['reason']}",
        f"- **Generated:** {report['generated_at']}",
        f"- **Locale:** {report['locale']}",
        f"- **Diff:** `{report['diff_path']}`",
        "",
        "## Summary",
        "",
        f"- Files checked: {report['summary']['files_checked']}",
        f"- Hard failures: {report['summary']['hard_failures']}",
        f"- Soft findings: {report['summary']['soft_findings']}",
        "",
    ]
    for item in report["files"]:
        lines.append(f"### `{item['source_path']}` -> `{item['target_path']}`")
        lines.append("")
        if item["hard"]:
            lines.append("**Hard**")
            for msg in item["hard"]:
                lines.append(f"- {msg}")
            lines.append("")
        if item["soft"]:
            lines.append("**Soft**")
            for msg in item["soft"]:
                lines.append(f"- {msg}")
            lines.append("")
        if item["info"]:
            lines.append("**Info**")
            for msg in item["info"]:
                lines.append(f"- {msg}")
            lines.append("")
        if not item["hard"] and not item["soft"]:
            lines.append("- No issues.")
            lines.append("")
    lines.append("## Gate policy (demo MVP)")
    lines.append("")
    lines.append("- `PASS` -> label `l10n-qa-pass`")
    lines.append("- `NEEDS_REVIEW` / `FAIL` -> label `needs-l10n-review`")
    lines.append("- GPT qualitative QA: skipped (rules-only)")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rules QA for l10n targets")
    parser.add_argument("--diff", default="artifacts/diff-report.json")
    parser.add_argument("--out", default="")
    parser.add_argument("--locale", default="")
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit 1 on FAIL or NEEDS_REVIEW (default: exit 1 only on FAIL)",
    )
    args = parser.parse_args()

    cfg = load_config()
    locale = args.locale or (cfg.get("target_locales") or ["fr_ca"])[0]

    diff_path = Path(args.diff)
    if not diff_path.is_absolute():
        diff_path = REPO_ROOT / diff_path
    if not diff_path.is_file():
        print(f"Diff report not found: {diff_path}", file=sys.stderr)
        return 1

    out_md = Path(args.out) if args.out else artifacts_dir(cfg) / "qa-report.md"
    if not out_md.is_absolute():
        out_md = REPO_ROOT / out_md
    out_json = out_md.with_suffix(".json")

    report_in = json.loads(diff_path.read_text(encoding="utf-8"))
    files = report_in.get("files") or []
    results = [check_file(entry, locale) for entry in files]

    decision = decide_status(results, cfg)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diff_path": to_repo_posix(diff_path),
        "locale": locale,
        "status": decision["status"],
        "recommended_label": decision["recommended_label"],
        "reason": decision["reason"],
        "summary": {
            "files_checked": len(results),
            "hard_failures": sum(len(f["hard"]) for f in results),
            "soft_findings": sum(len(f["soft"]) for f in results),
        },
        "files": results,
    }

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"QA {report['status']} | label={report['recommended_label']} | "
        f"hard={report['summary']['hard_failures']} soft={report['summary']['soft_findings']} | "
        f"wrote {to_repo_posix(out_md)}"
    )

    if report["status"] == "FAIL":
        return 1
    if args.strict_exit and report["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
