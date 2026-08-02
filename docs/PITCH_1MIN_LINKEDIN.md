# 1-minute LinkedIn pitch — recording guide

**Goal:** Show “update English content → Git automation translates + AI QA → PR ready”.

**Repo:** https://github.com/krishnahaldude001/github-demo

---

## Before you hit Record (2 minutes setup)

1. Confirm pipeline is on `main` (workflow + scripts pushed).
2. GitHub → **Settings → Secrets and variables → Actions** → add:
   - `GEMINI_API_KEY` = your Gemini key
3. Close extra browser tabs. Use a clean zoom (110–125%).
4. Open these 3 tabs ready:
   - `Folder 1/file1.json` (edit)
   - **Actions**
   - **Pull requests**

Optional backup (if Actions is slow): local terminal ready in `github-demo`.

---

## 60-second shot list

| Time | Show | Say |
|------|------|-----|
| 0–8s | Repo README / folders | “Manual localization is slow. Here’s continuous localization in Git.” |
| 8–22s | Edit one English string in `Folder 1/file1.json` → Commit to `main` | “I update one source string.” |
| 22–38s | **Actions** → `Localize` workflow running/green | “GitHub Actions detects the change, Gemini translates only what changed.” |
| 38–52s | Open the l10n PR → **Files changed** EN vs FR | “AI runs checklist QA and opens a pull request with French ready.” |
| 52–60s | PR labels + Merge button (don’t need to merge on camera) | “The team only reviews and merges. That’s the product.” |

---

## Exact click path

1. GitHub → `Folder 1/file1.json` → pencil → change `segment_1` text slightly → **Commit changes** to `main`
2. **Actions** tab → click latest **Localize** run
3. Wait until translate/QA/PR steps finish (or cut after it starts if narrating)
4. **Pull requests** → open `l10n: update fr_ca translations`
5. Show:
   - LLM auto checklist (checked/unchecked by AI)
   - Files changed (English → French)
   - Labels (`l10n`, `l10n-qa-pass` or `needs-l10n-review`)

---

## Spoken script (about 55 seconds)

> Localization usually means copy-paste, delays, and manual review.  
> Here I change one English string in Git.  
> GitHub Actions picks it up, Gemini translates only the changed keys, AI runs a QA checklist, and opens a pull request with French content.  
> No TMS required for this demo — fully automated in Git.  
> Humans only review and merge. That’s continuous localization.

---

## Backup if Actions isn’t ready

In terminal:

```bash
python scripts/diff_json_keys.py --base HEAD~1 --head HEAD
python scripts/translate_gemini.py --diff artifacts/diff-report.json --locale fr_ca
python scripts/qa_check.py --diff artifacts/diff-report.json --locale fr_ca
python scripts/llm_review.py --diff artifacts/diff-report.json --locale fr_ca
python scripts/open_or_update_pr.py
```

Then show the PR URL on screen.

---

## What clients should remember

1. Content change triggers automation  
2. Only deltas are translated  
3. AI checklist + PR gate  
4. Human merge control  
