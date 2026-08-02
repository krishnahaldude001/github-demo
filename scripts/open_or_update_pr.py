"""Phase 5: open or update a localization PR (idempotent)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import REPO_ROOT, load_config, target_path_for, to_repo_posix

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

API = "https://api.github.com"


def run_git(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_token() -> str:
    token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_PAT")
        or ""
    ).strip()
    if not token:
        raise RuntimeError(
            "Missing GitHub token. Set GITHUB_TOKEN (Actions) or GH_TOKEN / GITHUB_PAT locally."
        )
    return token


def parse_remote_repo() -> tuple[str, str]:
    url = run_git(["remote", "get-url", "origin"]).stdout.strip()
    # https://github.com/owner/repo.git or git@github.com:owner/repo.git
    cleaned = url.replace(".git", "")
    if cleaned.startswith("git@"):
        path = cleaned.split(":", 1)[1]
    elif "github.com/" in cleaned:
        path = cleaned.split("github.com/", 1)[1]
    else:
        raise RuntimeError(f"Unsupported origin URL: {url}")
    owner, repo = path.strip("/").split("/")[:2]
    return owner, repo


def github_request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-demo-l10n-bot",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed ({exc.code}): {detail}") from exc


def ensure_label(owner: str, repo: str, token: str, name: str, color: str, description: str) -> None:
    encoded = urllib.parse.quote(name)
    try:
        github_request("GET", f"/repos/{owner}/{repo}/labels/{encoded}", token)
        return
    except RuntimeError as exc:
        if "(404)" not in str(exc):
            raise
    try:
        github_request(
            "POST",
            f"/repos/{owner}/{repo}/labels",
            token,
            {"name": name, "color": color, "description": description},
        )
    except RuntimeError as exc:
        if "(422)" not in str(exc):
            raise


def files_from_diff(diff: dict[str, Any], locale: str, include_source: bool) -> list[Path]:
    paths: list[Path] = []
    for entry in diff.get("files") or []:
        source_rel = entry["source_path"]
        source_path = REPO_ROOT / Path(*source_rel.replace("\\", "/").split("/"))
        if include_source and source_path.is_file() and entry.get("change_type") != "deleted":
            paths.append(source_path)
        if entry.get("change_type") == "deleted":
            continue
        target = target_path_for(source_path, locale)
        if target.is_file():
            paths.append(target)
    # unique preserve order
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def build_pr_body(
    *,
    locale: str,
    diff: dict[str, Any],
    qa: dict[str, Any],
    qa_md: str,
) -> str:
    llm = qa.get("llm_review") or {}
    checklist = llm.get("checklist") or []
    lines = [
        "## Localization PR (Gemini demo)",
        "",
        f"- **Locale:** `{locale}`",
        f"- **QA status:** `{qa.get('status')}`",
        f"- **Recommended label:** `{qa.get('recommended_label')}`",
        f"- **Diff base..head:** `{diff.get('base')}` .. `{diff.get('head')}`",
        "",
        "### Changed files / keys",
        "",
    ]
    for entry in diff.get("files") or []:
        lines.append(
            f"- `{entry['source_path']}` ({entry['change_type']}): "
            f"+{len(entry.get('added_keys', []))} "
            f"~{len(entry.get('changed_keys', []))} "
            f"-{len(entry.get('deleted_keys', []))}"
        )

    lines.extend(["", "### Review checklist (auto-filled by LLM)", ""])
    if checklist:
        for item in checklist:
            mark = "x" if item.get("passed") else " "
            notes = item.get("notes") or ""
            lines.append(f"- [{mark}] {item.get('label')} — {notes}")
        if llm.get("summary"):
            lines.extend(["", f"_LLM summary: {llm.get('summary')}_", ""])
    else:
        lines.extend(
            [
                "- [ ] Translations look correct for fr-CA",
                "- [ ] Placeholders / JSON structure look fine",
                "- [ ] Approve to merge, or request changes",
                "",
            ]
        )

    lines.extend(
        [
            "### QA report",
            "",
            qa_md.strip() or "_No QA markdown available._",
            "",
            "---",
            "_Opened by the localization pipeline. No auto-merge._",
            "",
        ]
    )
    return "\n".join(lines)


def current_branch() -> str:
    return run_git(["branch", "--show-current"]).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Open or update l10n PR")
    parser.add_argument("--diff", default="artifacts/diff-report.json")
    parser.add_argument("--qa-report", default="artifacts/qa-report.md")
    parser.add_argument("--qa-json", default="artifacts/qa-report.json")
    parser.add_argument("--locale", default="")
    parser.add_argument("--branch", default="")
    parser.add_argument("--base", default="main")
    parser.add_argument("--include-source", action="store_true", default=True)
    parser.add_argument("--no-include-source", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-push", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    locale = args.locale or (cfg.get("target_locales") or ["fr_ca"])[0]
    include_source = False if args.no_include_source else args.include_source
    branch = args.branch or f"{cfg.get('pr', {}).get('branch_prefix', 'l10n/')}{locale}-auto"

    diff_path = Path(args.diff)
    if not diff_path.is_absolute():
        diff_path = REPO_ROOT / diff_path
    qa_md_path = Path(args.qa_report)
    if not qa_md_path.is_absolute():
        qa_md_path = REPO_ROOT / qa_md_path
    qa_json_path = Path(args.qa_json)
    if not qa_json_path.is_absolute():
        qa_json_path = REPO_ROOT / qa_json_path

    if not diff_path.is_file():
        print(f"Missing diff report: {diff_path}", file=sys.stderr)
        return 1
    if not qa_json_path.is_file():
        print(f"Missing QA JSON: {qa_json_path}", file=sys.stderr)
        return 1

    diff = load_json(diff_path)
    qa = load_json(qa_json_path)
    qa_md = qa_md_path.read_text(encoding="utf-8") if qa_md_path.is_file() else ""

    paths = files_from_diff(diff, locale, include_source)
    if not paths:
        print("No translation files to commit — skipping PR.")
        return 0

    print("Files for PR:")
    for path in paths:
        print(f"  - {to_repo_posix(path)}")

    title = f"l10n: update {locale} translations"
    body = build_pr_body(locale=locale, diff=diff, qa=qa, qa_md=qa_md)
    labels_cfg = cfg.get("pr", {})
    labels = list(dict.fromkeys([*(labels_cfg.get("labels") or ["l10n"]), qa.get("recommended_label")]))

    if args.dry_run:
        print(f"[dry-run] branch={branch} title={title} labels={labels}")
        print(body[:500], "...")
        return 0

    original = current_branch() or "main"
    # Create/switch branch
    exists = run_git(["rev-parse", "--verify", branch], check=False)
    if exists.returncode == 0:
        run_git(["checkout", branch])
    else:
        run_git(["checkout", "-b", branch])

    rels = [to_repo_posix(p) for p in paths]
    run_git(["add", "--", *rels])
    staged = run_git(["diff", "--cached", "--name-only"]).stdout.strip()
    if staged:
        msg = (
            f"l10n({locale}): apply Gemini translations\n\n"
            f"QA status: {qa.get('status')} ({qa.get('recommended_label')})"
        )
        run_git(["commit", "-m", msg])
        print("Created commit on", branch)
    else:
        print("No staged content changes (commit may already exist).")

    if args.skip_push:
        print(f"Skipped push/PR API. Local branch ready: {branch}")
        body_path = REPO_ROOT / "artifacts" / "pr-body.md"
        body_path.write_text(body, encoding="utf-8")
        print(f"Wrote PR body draft: {to_repo_posix(body_path)}")
        if original and original != branch:
            run_git(["checkout", original], check=False)
        return 0

    token = resolve_token()
    owner, repo = parse_remote_repo()

    # Prefer non-interactive HTTPS with token.
    # Fine-grained PATs authenticate more reliably as <username>:<token>.
    push_urls = [
        f"https://{owner}:{token}@github.com/{owner}/{repo}.git",
        f"https://oauth2:{token}@github.com/{owner}/{repo}.git",
        f"https://x-access-token:{token}@github.com/{owner}/{repo}.git",
    ]
    push_err = ""
    for remote_url in push_urls:
        push = subprocess.run(
            [
                "git",
                "push",
                "-u",
                remote_url,
                f"HEAD:refs/heads/{branch}",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if push.returncode == 0:
            push_err = ""
            break
        push_err = push.stderr.strip() or push.stdout.strip()
    if push_err:
        raise RuntimeError(f"git push failed: {push_err}")
    print(f"Pushed branch {branch}")

    # Labels
    color_map = {
        labels_cfg.get("labels", ["l10n"])[0]: ("0E8A16", "Localization change"),
        labels_cfg.get("label_qa_pass", "l10n-qa-pass"): ("1D76DB", "QA passed"),
        labels_cfg.get("label_needs_review", "needs-l10n-review"): ("D93F0B", "Needs human review"),
    }
    for name in labels:
        color, desc = color_map.get(name, ("5319E7", "l10n"))
        ensure_label(owner, repo, token, name, color, desc)

    # Find open PR for this head
    prs = github_request(
        "GET",
        f"/repos/{owner}/{repo}/pulls?state=open&head={owner}:{branch}&base={args.base}",
        token,
    )
    if prs:
        pr = prs[0]
        pr_number = pr["number"]
        github_request(
            "PATCH",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            token,
            {"title": title, "body": body},
        )
        print(f"Updated PR #{pr_number}")
    else:
        pr = github_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            token,
            {"title": title, "head": branch, "base": args.base, "body": body},
        )
        pr_number = pr["number"]
        print(f"Opened PR #{pr_number}")

    github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{pr_number}/labels",
        token,
        {"labels": labels},
    )

    # Remove opposite QA label if present
    opposite = (
        labels_cfg.get("label_needs_review")
        if qa.get("recommended_label") == labels_cfg.get("label_qa_pass")
        else labels_cfg.get("label_qa_pass")
    )
    if opposite and opposite not in labels:
        try:
            github_request(
                "DELETE",
                f"/repos/{owner}/{repo}/issues/{pr_number}/labels/{urllib.parse.quote(opposite)}",
                token,
            )
        except RuntimeError:
            pass

    html_url = pr.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{pr_number}"
    print(f"PR URL: {html_url}")

    # Return to original branch when possible
    if original and original != branch:
        run_git(["checkout", original], check=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - surface clean CLI errors
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
