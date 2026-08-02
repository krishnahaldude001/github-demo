# Git L10n Pipeline — Reference

## Target architecture

```text
Source commit (JSON)
  → GitHub Actions path filter
  → scripts/diff_json_keys.py
  → scripts/translate.py (LLM)
  → scripts/qa_check.py (+ optional GPT QA)
  → scripts/open_or_update_pr.py
  → Human review on GitHub PR
  → Merge
```

## Suggested future file layout

```text
.github/workflows/
  localize.yml              # trigger + orchestrate
scripts/
  diff_json_keys.py         # key-level added/changed/deleted
  translate.py              # full + delta translation
  qa_check.py               # structural + optional GPT QA
  open_or_update_pr.py      # idempotent PR create/update
docs/
  GIT_LOCALIZATION_PIPELINE_GUIDE.md
  PROGRESS.md
artifacts/                  # CI-only, usually not committed
  diff-report.json
  qa-report.md
```

## Key-level diff shape (implemented)

See `artifacts/diff-report.json` from:

```bash
python scripts/diff_json_keys.py --base HEAD --head WORKTREE
```

```json
{
  "files": [
    {
      "source_path": "Folder 1/file1.json",
      "change_type": "modified",
      "added_keys": ["segments.segment_7"],
      "changed_keys": ["segments.segment_1"],
      "deleted_keys": [],
      "locale_targets": ["fr_ca"],
      "units": {
        "added": { "segments.segment_7": "..." },
        "changed": { "segments.segment_1": { "old": "...", "new": "..." } },
        "deleted": {}
      }
    }
  ]
}
```

## LLM prompt expectations

For **delta** translation, send:

1. Target locale code  
2. Changed key/value pairs only (units to translate)  
3. Full source JSON as context (do not retranslate unchanged keys unless needed for consistency repair)  
4. Existing target JSON (so unchanged keys stay stable)  
5. Rules: preserve placeholders, do not add/remove keys except requested deletes  

For **new file** translation, send the full source JSON and locale.

## QA report shape (recommended)

```markdown
# QA Report
- Status: PASS | NEEDS_REVIEW | FAIL
- Files checked: N
- Hard failures: ...
- Soft findings: ...
- GPT score (optional): ...
```

## Labels

| Label | Meaning |
|-------|---------|
| `l10n` | Localization PR |
| `l10n-qa-pass` | Automated QA passed |
| `needs-l10n-review` | Human must review before merge |

## Optional integrations

- **Phrase TMS:** create jobs / use TM+termbase, export back into locale folders, open PR
- **Jira:** open issue when `needs-l10n-review` is applied

## Decisions still open

Track answers in `docs/PROGRESS.md` Phase 0:

- Locales beyond `fr_ca`
- LLM provider
- QA mode (rules / GPT / hybrid)
- Auto-merge policy
