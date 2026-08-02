"""One-shot: publish l10n branch + PR via GitHub Git Data API (fine-grained PAT friendly)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=True)

TOKEN = (os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or "").strip()
OWNER = "krishnahaldude001"
REPO = "github-demo"
BRANCH = "l10n/fr_ca-auto"
FILES = ["Folder 1/file1.json", "Folder 1/fr_ca/file1.json"]


def api(method: str, path: str, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "l10n-bot",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {exc.code}: {detail[:800]}") from exc


def main() -> int:
    if not TOKEN:
        print("Missing GITHUB_PAT", file=sys.stderr)
        return 1

    ref = api("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/main")
    base_sha = ref["object"]["sha"]
    commit = api("GET", f"/repos/{OWNER}/{REPO}/git/commits/{base_sha}")
    base_tree = commit["tree"]["sha"]
    print(f"base={base_sha[:7]}")

    tree_items = []
    for rel in FILES:
        content = subprocess.check_output(
            ["git", "show", f"{BRANCH}:{rel}"],
            cwd=ROOT,
        ).decode("utf-8")
        blob = api(
            "POST",
            f"/repos/{OWNER}/{REPO}/git/blobs",
            {"content": content, "encoding": "utf-8"},
        )
        tree_items.append(
            {"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]}
        )
        print(f"blob {rel}")

    tree = api(
        "POST",
        f"/repos/{OWNER}/{REPO}/git/trees",
        {"base_tree": base_tree, "tree": tree_items},
    )
    new_commit = api(
        "POST",
        f"/repos/{OWNER}/{REPO}/git/commits",
        {
            "message": "l10n(fr_ca): apply Gemini translations\n\nQA status: NEEDS_REVIEW",
            "tree": tree["sha"],
            "parents": [base_sha],
        },
    )
    sha = new_commit["sha"]
    print(f"commit={sha[:7]}")

    try:
        api(
            "POST",
            f"/repos/{OWNER}/{REPO}/git/refs",
            {"ref": f"refs/heads/{BRANCH}", "sha": sha},
        )
        print("created branch ref")
    except RuntimeError:
        api(
            "PATCH",
            f"/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
            {"sha": sha, "force": True},
        )
        print("updated branch ref")

    for name, color, desc in [
        ("l10n", "0E8A16", "Localization change"),
        ("needs-l10n-review", "D93F0B", "Needs human review"),
        ("l10n-qa-pass", "1D76DB", "QA passed"),
    ]:
        try:
            api(
                "POST",
                f"/repos/{OWNER}/{REPO}/labels",
                {"name": name, "color": color, "description": desc},
            )
        except RuntimeError:
            pass

    body_path = ROOT / "artifacts" / "pr-body.md"
    body = body_path.read_text(encoding="utf-8") if body_path.exists() else "l10n PR"
    title = "l10n: update fr_ca translations"

    prs = api(
        "GET",
        f"/repos/{OWNER}/{REPO}/pulls?state=open&head={OWNER}:{BRANCH}&base=main",
    )
    if prs:
        pr = prs[0]
        api(
            "PATCH",
            f"/repos/{OWNER}/{REPO}/pulls/{pr['number']}",
            {"title": title, "body": body},
        )
        pr_number = pr["number"]
        pr_url = pr["html_url"]
        print(f"updated PR #{pr_number}")
    else:
        pr = api(
            "POST",
            f"/repos/{OWNER}/{REPO}/pulls",
            {"title": title, "head": BRANCH, "base": "main", "body": body},
        )
        pr_number = pr["number"]
        pr_url = pr["html_url"]
        print(f"opened PR #{pr_number}")

    api(
        "POST",
        f"/repos/{OWNER}/{REPO}/issues/{pr_number}/labels",
        {"labels": ["l10n", "needs-l10n-review"]},
    )
    print(f"PR_URL={pr_url}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
