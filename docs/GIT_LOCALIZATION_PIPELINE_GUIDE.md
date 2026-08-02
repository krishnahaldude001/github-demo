# Git Localization Pipeline — Guide

**Repository:** [krishnahaldude001/github-demo](https://github.com/krishnahaldude001/github-demo.git)  
**Progress tracker:** [PROGRESS.md](./PROGRESS.md)  
**Cursor skill:** [../.cursor/skills/git-l10n-pipeline/SKILL.md](../.cursor/skills/git-l10n-pipeline/SKILL.md)

This guide describes the end-to-end localization workflow we are building with Git automation. Use it with `PROGRESS.md` so no step is skipped.

---

## 1. Goal

Automate localization for JSON source files in Git:

1. Monitor source folders for adds / edits / deletes  
2. Translate with an LLM  
   - **New file** → translate the whole file  
   - **Delta change** → translate only changed keys, with full file context  
3. Run standard QA (rules + optional GPT QA)  
4. If QA is good → open PR ready to merge  
5. If issues → mark for human approve/reject in Git  
6. Merge via pull request

---

## 2. Current repo layout

```text
github-demo/
├── Folder 1/
│   ├── file1.json              # SOURCE (English)
│   └── fr_ca/file1.json        # TARGET (fr-CA)
├── Folder 2/
│   ├── file2.json              # SOURCE (English)
│   └── fr_ca/file2.json        # TARGET (fr-CA)
├── config/
│   └── l10n.json               # Pipeline config
├── scripts/                    # Diff / Gemini / QA / PR helpers
├── .github/workflows/
│   └── localize.yml            # CI scaffold (manual dispatch for now)
├── docs/
│   ├── CONVENTIONS.md
│   ├── glossary.md
│   ├── GIT_LOCALIZATION_PIPELINE_GUIDE.md
│   └── PROGRESS.md
└── .cursor/skills/git-l10n-pipeline/
```

**Convention** — see [CONVENTIONS.md](./CONVENTIONS.md) and `config/l10n.json`.

| Item | Rule |
|------|------|
| Source files | JSON at folder root (e.g. `Folder 1/file1.json`) |
| Target files | Same filename under locale subfolder (e.g. `Folder 1/fr_ca/file1.json`) |
| Source of truth | Source JSON only — bots must not rewrite source on the same path |
| Delivery | Always via Pull Request, never direct push to `main` for generated translations |

---

## 3. Pipeline architecture

```text
Developer commits source JSON
        │
        ▼
GitHub Actions (path-filtered)
        │
        ▼
Key-level JSON diff
  ├── added file     → full translate
  ├── changed keys   → delta translate (+ full file context)
  └── deleted keys   → remove from targets
        │
        ▼
LLM translation → write locale JSON
        │
        ▼
QA gate (structure + placeholders + optional GPT)
  ├── PASS  → PR label: l10n-qa-pass
  └── FAIL  → PR label: needs-l10n-review
        │
        ▼
Open / update translation PR
        │
        ▼
Human approve or request changes in GitHub
        │
        ▼
Merge PR → translations on main
```

---

## 4. Step-by-step build order

Complete these in order. Check off each item in [PROGRESS.md](./PROGRESS.md).

### Phase 0 — Decisions (LOCKED for demo MVP)

1. Locales: **`fr_ca` only**  
2. Engine: **Google Gemini API** (`GEMINI_API_KEY`) — **no Phrase**  
3. QA: **rules-only** (JSON / keys / placeholders / empty)  
4. Merge: open PR for demo; **no auto-merge** (human merges)

### Phase 1 — Structure

1. Keep source/target separation clear — **done** (`docs/CONVENTIONS.md`, `config/l10n.json`)  
2. Add `scripts/` for automation helpers — **done** (scaffolds)  
3. Add `.github/workflows/` for CI — **done** (`localize.yml` manual dispatch)  
4. Enable branch protection on `main` (PR required) — **manual** in GitHub settings (see CONVENTIONS.md)

### Phase 2 — Monitoring & diff

1. Trigger workflow when source JSON changes — **done** (`push`/`pull_request` on `Folder 1/*.json`, `Folder 2/*.json`)  
2. Exclude locale folders from “source changed” triggers — **done** (root `*.json` only)  
3. Compute key-level diff artifact — **done** (`scripts/diff_json_keys.py` → `artifacts/diff-report.json`)  
4. Classify: new file / delta / delete — **done** (`added` / `modified` / `deleted`)

### Phase 3 — Translation

1. Full translate for new files — **done** (`translate_gemini.py` mode `full`)  
2. Delta translate for changed keys with full-file context — **done** (live-tested)  
3. Delete removed keys in targets — **done**  
4. Keep placeholders and JSON shape intact — **done**  
5. Model: **`gemini-2.5-flash`** via `GEMINI_API_KEY`

### Phase 4 — QA

1. Validate JSON + key coverage — **done**  
2. Check placeholders / empty strings — **done**  
3. Optional GPT qualitative review — **skipped** (rules-only)  
4. Attach `qa-report.md` — **done** (`artifacts/qa-report.md` + `.json`)  
5. Apply pass/fail labels — **done** (`recommended_label` in report; PR apply in Phase 5)

### Phase 5 — Human + PR

1. Bot opens or updates one translation PR per change set — **done** (`l10n/<locale>-auto`)  
2. Reviewer approves or requests changes — **via GitHub PR**  
3. Merge only through GitHub PR — **enforced by convention (no auto-merge)**  
4. Optional Jira / Phrase — **out of scope**

Local remote PR requires `GITHUB_PAT` in `.env` (see `.env.example`). Actions uses `GITHUB_TOKEN`.

### Phase 6 — Harden

1. Secrets, retries, cost controls  
2. Dry-run on a sample change  
3. Document rollback (revert the PR)

---

## 5. Translation rules (must follow)

1. **Key-level, not whole-file blind rewrite** for edits  
2. Always send **changed keys + full source file context** to the LLM  
3. Do not invent keys that do not exist in source  
4. Preserve placeholders exactly (`{count}`, `%s`, ICU pieces, HTML tags if present)  
5. Keep stable key order when practical (cleaner diffs)  
6. Re-running the same commit must be **idempotent**

---

## 6. QA gate definition (MVP)

**Hard fail (must fix / human review):**

- Invalid JSON  
- Missing keys vs source  
- Broken / missing placeholders  
- Empty target values for non-empty source  

**Soft fail (label for human review):**

- Low GPT confidence  
- Suspicious length change  
- Glossary / terminology mismatch  

**Pass:**

- All hard checks green  
- Soft checks empty or within threshold  

---

## 7. Git / PR conventions

| Item | Convention |
|------|------------|
| Branch name | `l10n/<locale>-<short-sha>` or `l10n/auto-<date>` |
| PR title | `l10n: update <locale> translations` |
| Labels | `l10n`, `l10n-qa-pass`, `needs-l10n-review` |
| Review | Approve / Request changes in GitHub |
| Merge | Squash or merge commit; no direct push of bot output to `main` |

---

## 8. How agents / humans must use this project

1. Open [PROGRESS.md](./PROGRESS.md) first  
2. Pick the **next unchecked** item in order  
3. Do not skip phases unless explicitly asked  
4. After completing work, mark the checkbox `[x]` and add a Changelog row  
5. Follow the Cursor skill at `.cursor/skills/git-l10n-pipeline/SKILL.md`

---

## 9. Integrations (demo MVP)

| Tool | Role |
|------|------|
| Gemini API | Full + delta translation |
| GitHub Actions | Folder monitoring, translate, QA, PR automation |
| Phrase / Jira | **Out of scope** for this demo |

---

## 10. Success criteria for MVP

MVP is done when:

1. A source JSON edit on `main` (or a watched branch) triggers the workflow  
2. Only changed keys are translated (or full file if new)  
3. A translation PR is opened with a QA report  
4. Failures get `needs-l10n-review`  
5. A human can approve/reject in GitHub and merge  

Track completion only via [PROGRESS.md](./PROGRESS.md).
