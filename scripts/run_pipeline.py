"""Orchestrate localization pipeline steps."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def run(script: str, extra: list[str] | None = None) -> int:
    cmd = [sys.executable, str(SCRIPTS / script), *(extra or [])]
    print("->", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run l10n pipeline")
    parser.add_argument("--base", default="HEAD~1")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--locale", default="fr_ca")
    parser.add_argument("--skip-pr", action="store_true")
    parser.add_argument("--skip-llm-review", action="store_true")
    args = parser.parse_args()

    steps = [
        ("diff_json_keys.py", ["--base", args.base, "--head", args.head]),
        ("translate_gemini.py", ["--locale", args.locale]),
        ("qa_check.py", ["--locale", args.locale]),
    ]
    if not args.skip_llm_review:
        steps.append(("llm_review.py", ["--locale", args.locale]))
    if not args.skip_pr:
        steps.append(("open_or_update_pr.py", ["--locale", args.locale]))

    for script, extra in steps:
        code = run(script, extra)
        if code != 0:
            return code
    print("Pipeline finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
