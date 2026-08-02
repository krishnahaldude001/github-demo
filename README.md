# github-demo

Git-based localization demo: monitor JSON source files, translate with **Gemini**, run simple rules QA, open a PR (no Phrase).

**Remote:** https://github.com/krishnahaldude001/github-demo.git

## Start here

| Doc | Purpose |
|-----|---------|
| [docs/PITCH_1MIN_LINKEDIN.md](docs/PITCH_1MIN_LINKEDIN.md) | **1-minute LinkedIn recording guide** |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Checklist — completed vs pending |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | Source vs target folder rules |
| [docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md](docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md) | Full pipeline guide |
| [config/l10n.json](config/l10n.json) | Machine-readable pipeline config |

## Layout

```text
Folder 1/file1.json          → English source
Folder 1/fr_ca/file1.json    → fr-CA target
Folder 2/file2.json          → English source
Folder 2/fr_ca/file2.json    → fr-CA target
scripts/                     → pipeline helpers (Phase 1 scaffolds)
.github/workflows/localize.yml
```

## Status

- Phase 0–5: **done** (remote PR open needs `GITHUB_PAT`)
- Next: **Phase 6** (secrets/harden) or add PAT and publish the PR

```bash
python scripts/diff_json_keys.py --base HEAD --head WORKTREE
python scripts/translate_gemini.py --diff artifacts/diff-report.json --locale fr_ca
python scripts/qa_check.py --diff artifacts/diff-report.json --locale fr_ca
# Local commit only:
python scripts/open_or_update_pr.py --skip-push
# Push + open/update GitHub PR (needs GITHUB_PAT in .env):
python scripts/open_or_update_pr.py
```

