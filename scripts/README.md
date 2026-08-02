# Localization scripts

Phase 1 = scaffolding. Logic is filled in Phases 2–5.

| Script | Phase | Role |
|--------|-------|------|
| `diff_json_keys.py` | **2 (live)** | Key-level added/changed/deleted → `artifacts/diff-report.json` |
| `translate_gemini.py` | **3 (live)** | Full + delta translation via Gemini |
| `qa_check.py` | **4 (live)** | Rules QA → `artifacts/qa-report.md` + `.json` |
| `open_or_update_pr.py` | **5 (live)** | Branch + commit + push + open/update PR + labels |
| `run_pipeline.py` | 2–5 | Orchestrates the steps above |

### Phase 5 notes

- Idempotent branch: `l10n/fr_ca-auto`
- Labels: `l10n` + `l10n-qa-pass` or `needs-l10n-review`
- Local PR publish needs `GITHUB_PAT` in `.env`
- `--skip-push` creates the local branch/commit + `artifacts/pr-body.md` without calling GitHub |

### Phase 2 local smoke test

```bash
# Edit a source string, then:
python scripts/diff_json_keys.py --base HEAD --head WORKTREE
# Inspect artifacts/diff-report.json, then discard the edit if needed
```

## Local setup

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Put GEMINI_API_KEY in .env
```

## Config

All scripts should read `config/l10n.json` and (when needed) `GEMINI_API_KEY` from the environment.
