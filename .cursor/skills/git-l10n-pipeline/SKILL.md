---
name: git-l10n-pipeline
description: >-
  Builds and maintains the Git-based JSON localization demo for
  krishnahaldude001/github-demo: folder monitoring, key-level diff, Gemini
  full/delta translation, simple rules QA, and PR open for human merge.
  No Phrase. Use when working on localization automation, Gemini l10n CI,
  translation PRs, PROGRESS.md, or github-demo i18n.
---

# Git Localization Pipeline

## Mandatory first actions

Before any localization work in this repo:

1. Read `docs/PROGRESS.md` (source of truth for completed vs pending steps).
2. Read `docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md` if the task touches design or next phases.
3. Work on the **next unfinished phase/step in order**. Do not skip steps unless the user explicitly asks to skip.
4. After finishing work, update `docs/PROGRESS.md`:
   - Mark completed items `[x]`
   - Add a Changelog row with date + what changed

## Project facts

- **Repo:** https://github.com/krishnahaldude001/github-demo.git
- **Source JSON:** `Folder 1/file1.json`, `Folder 2/file2.json` (folder-root JSON)
- **Target locale:** `Folder */fr_ca/*.json` only (demo MVP)
- **Engine:** Google **Gemini API** via `GEMINI_API_KEY` — **no Phrase**, no Jira
- **Delivery model:** GitHub Actions → Gemini translate → rules QA → open PR → human merge
- **Never** push generated translations directly to `main`; **never auto-merge**

## Pipeline checklist (do not miss steps)

Copy and track during implementation sessions:

```text
Pipeline progress:
- [x] Phase 0: locked (Gemini, fr_ca, rules QA, PR no auto-merge, no Phrase)
- [x] Phase 1: structure (scripts/, workflows/, conventions, config)
- [x] Phase 2: monitoring + key-level JSON diff artifact
- [x] Phase 3: Gemini translation (full / delta+context / deletes)
- [x] Phase 4: rules QA + qa-report.md + labels
- [x] Phase 5: open/update PR (demo)
- [x] LLM auto-checklist review (`llm_review.py`) for LinkedIn pitch
- [ ] Phase 6: GEMINI_API_KEY as GitHub Actions secret + end-to-end Actions dry-run
```

Sync the same status into `docs/PROGRESS.md`.

## Implementation rules

### Change detection

- Watch source JSON paths; treat locale subfolders as targets, not sources.
- Diff at **key level** (`added` / `changed` / `deleted`), not only whole-file text.
- Emit a machine-readable report (e.g. `diff-report.json`).

### Translation

| Change type | Action |
|-------------|--------|
| New source file | Full-file LLM translation |
| Changed keys | Translate only those keys, send full source file as context |
| Deleted keys | Remove matching keys from target locale files |

Also:

- Preserve placeholders and JSON structure
- Do not invent keys
- Keep runs idempotent (same commit → same outcome; update existing open l10n PR when possible)

### QA gate

Hard fail → `needs-l10n-review`:

- Invalid JSON
- Missing keys
- Broken placeholders
- Empty targets for non-empty source

Pass → `l10n-qa-pass` (still merge via PR; human review recommended for MVP).

Attach `qa-report.md` in the PR body or as a bot comment.

### Git / PR

- Branch: `l10n/<locale>-<short-sha>` or `l10n/auto-<date>`
- Labels: `l10n`, `l10n-qa-pass`, `needs-l10n-review`
- Human merges the PR for the demo (no Phrase / no Jira)

## Session workflow for the agent

1. Read `docs/PROGRESS.md`
2. Tell the user which next unchecked step you will execute
3. Implement only that step (or a tightly related pair) unless asked for a larger chunk
4. Verify the step works
5. Update `docs/PROGRESS.md` checkboxes + Changelog
6. Stop and summarize what is done vs still pending

## Do not

- Skip updating `PROGRESS.md`
- Rewrite English source files as part of translation output
- Force-push or commit generated locale files straight to `main`
- Mark a phase complete without evidence (workflow file, script, or successful dry-run)

## Additional resources

- Full human guide: [docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md](../../../docs/GIT_LOCALIZATION_PIPELINE_GUIDE.md)
- Progress tracker: [docs/PROGRESS.md](../../../docs/PROGRESS.md)
- Architecture details: [reference.md](reference.md)
