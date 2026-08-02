# Git Localization Pipeline — Progress Tracker

**Repo:** https://github.com/krishnahaldude001/github-demo.git  
**Last updated:** 2026-08-02  

Use this file as the single source of truth for what is done vs pending.  
**Rule for agents:** Before any localization work, read this file. After finishing a step, mark it `[x]` and add a short note under Changelog.

### Locked Phase 0 decisions (demo MVP)

| Decision | Choice |
|----------|--------|
| Engine | **Gemini API only** — fully automated, **no Phrase** |
| Locales | **`fr_ca` only** (demo) |
| QA | **Simple rules** (JSON / keys / placeholders / empty) — keep demo fast |
| Delivery | Bot opens/updates a **PR** with translations + QA report |
| Merge | **No auto-merge** — show PR working; human merges for the demo |
| Jira | **No** |
| Secret | `GEMINI_API_KEY` in GitHub Actions secrets (or local `.env` for dry-run) |

---

## Status legend

| Mark | Meaning |
|------|---------|
| `[x]` | Completed |
| `[~]` | In progress |
| `[ ]` | Not started |
| `[!]` | Blocked / needs decision |

---

## Phase 0 — Discovery & design

- [x] Define pipeline goal: Git-monitored JSON → LLM translate → QA → human review → PR merge
- [x] Confirm GitHub as platform (`krishnahaldude001/github-demo`)
- [x] Inspect existing repo layout (`Folder 1`, `Folder 2`, `fr_ca` targets)
- [x] Note prior Phrase TMS PR history (optional TMS path)
- [x] Create human guide (`docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md`)
- [x] Create Cursor skill (`.cursor/skills/git-l10n-pipeline/`)
- [x] Create this progress tracker (`docs/PROGRESS.md`)
- [x] Decide target locales: **`fr_ca` only** for demo MVP
- [x] Decide LLM provider: **Google Gemini API** (`GEMINI_API_KEY`) — no Phrase
- [x] Decide QA approach: **rules-only** (simple demo gate)
- [x] Decide auto-merge policy: **never auto-merge**; open PR for human merge/demo

---

## Phase 1 — Repo structure & conventions

- [x] Standardize folder convention (source vs locale folders)
- [x] Document which paths are **source of truth** (`docs/CONVENTIONS.md`)
- [x] Document which paths are **generated targets** (`docs/CONVENTIONS.md` + `config/l10n.json`)
- [x] Add sample glossary / style notes file (`docs/glossary.md`)
- [x] Add `.github/` workflow folder (`localize.yml` scaffold)
- [x] Add `scripts/` for diff / translate / QA / PR helpers
- [x] Protect `main` with required PR review — **documented as manual GitHub setting** in `docs/CONVENTIONS.md`

---

## Phase 2 — Change detection (Git monitoring)

- [x] GitHub Actions workflow triggered on push/PR to source JSON paths
- [x] Path filters for watched folders (`Folder 1/*.json`, `Folder 2/*.json` — locale dirs excluded)
- [x] Detect **new file** vs **modified file** vs **deleted file**
- [x] Implement **key-level JSON diff** (`added` / `changed` / `deleted` keys)
- [x] Emit machine-readable diff artifact (`artifacts/diff-report.json`)

---

## Phase 3 — Translation engine

- [x] New file → full-file LLM translation
- [x] Delta change → translate only changed keys **with full file context**
- [x] Deleted keys → remove matching keys from target locale files
- [x] Preserve JSON structure / nesting / placeholders (`{name}`, `%s`, ICU, etc.)
- [x] Write translations into locale folders (e.g. `fr_ca/`)
- [x] Idempotent runs (re-run same commit does not duplicate work) — same diff reapplies same keys

---

## Phase 4 — Automated QA (GPT / rules gate)

- [x] Structural QA: valid JSON, all required keys present
- [x] Placeholder QA: source placeholders preserved in target
- [x] Empty / untranslated string detection
- [x] Optional glossary / forbidden-term checks (soft: Phrase / Team Fusion)
- [x] Optional GPT qualitative QA score + findings — **skipped** (rules-only MVP)
- [x] Produce `qa-report.md` (+ `qa-report.json`)
- [x] Gate logic:
  - QA pass → label `l10n-qa-pass`
  - QA fail / soft issues → label `needs-l10n-review`

---

## Phase 5 — Human review + Git PR flow

- [x] Bot opens/updates a translation PR (never force-push to `main`) — `scripts/open_or_update_pr.py`
- [x] PR body includes: changed keys summary, QA report, review checklist
- [x] Reviewer can **approve** or **request changes** in GitHub (standard PR review)
- [x] On approve + merge → translations land on `main`
- [x] Local dry-run: branch `l10n/fr_ca-auto` commit created; remote PR needs `GITHUB_PAT`
- [x] Jira: skipped for demo MVP
- [x] Phrase TMS: **out of scope** (Gemini-only automation)

---

## Phase 6 — Hardening & ops

- [ ] Secrets stored in GitHub Actions secrets (LLM API key, etc.)
- [ ] Rate-limit / retry handling for LLM calls
- [ ] Cost controls (batching, skip unchanged files)
- [ ] Logging & failure notifications
- [ ] End-to-end dry run on a sample source change
- [ ] Document rollback (revert translation PR)

---

## Current repo baseline (as of 2026-08-02)

| Path | Role |
|------|------|
| `Folder 1/file1.json` | English source |
| `Folder 1/fr_ca/file1.json` | French (Canada) target |
| `Folder 2/file2.json` | English source |
| `Folder 2/fr_ca/file2.json` | French (Canada) target |

Known history: older Phrase TMS PR exists in git history; **current plan ignores Phrase** and uses Gemini only.

---

## Changelog

| Date | What changed |
|------|----------------|
| 2026-08-02 | Pipeline designed; guide + skill + progress tracker created; repo cloned and inspected. Implementation not started yet. |
| 2026-08-02 | **Phase 0 locked:** Gemini-only, no Phrase, `fr_ca` only, rules QA, PR demo (no auto-merge). Ready for Phase 1. |
| 2026-08-02 | **Phase 1 done:** conventions, config, glossary, scripts scaffolds, workflow scaffold, .env.example, requirements. |
| 2026-08-02 | **Phase 2 done:** key-level `diff_json_keys.py`, path-filtered Actions triggers, `diff-report.json` artifact upload. |
| 2026-08-02 | **Phase 3 done + live test:** Gemini `gemini-2.5-flash` delta translate updated `Folder 1/fr_ca/file1.json`. |
| 2026-08-02 | **Phase 4 done:** rules QA live; demo run → `NEEDS_REVIEW` (5 soft untranslated `$$$` keys). |
| 2026-08-02 | **Phase 5 done:** `open_or_update_pr.py` + workflow step; local branch `l10n/fr_ca-auto` created. Remote PR pending `GITHUB_PAT`. |
| 2026-08-02 | **PR published:** https://github.com/krishnahaldude001/github-demo/pull/7 (`l10n` + `needs-l10n-review`). |
| 2026-08-02 | **Pitch prep:** LLM auto-checklist (`llm_review.py`), Actions wired, `docs/PITCH_1MIN_LINKEDIN.md`. |
