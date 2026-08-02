# Localization conventions

Machine-readable config: [`../config/l10n.json`](../config/l10n.json)

## Source of truth (English)

| Path pattern | Example |
|--------------|---------|
| `Folder */*.json` at folder root (not inside a locale dir) | `Folder 1/file1.json`, `Folder 2/file2.json` |

Rules:
- Humans / product commits edit **source** files only.
- Automation must **never** overwrite source files.

## Generated targets (translated)

| Locale | Path pattern | Example |
|--------|--------------|---------|
| `fr_ca` | `Folder */fr_ca/*.json` | `Folder 1/fr_ca/file1.json` |

Rules:
- Same filename as source, under the locale subfolder.
- Written only by the localization pipeline.
- Delivered to `main` **only via Pull Request** (no direct bot push to `main`).

## Watched vs ignored

| Watched (triggers pipeline) | Ignored as source |
|-----------------------------|-------------------|
| New/changed/deleted source JSON | Changes only under `fr_ca/` |
| | `docs/`, `scripts/`, `.github/`, `.cursor/` |

## Branch protection (manual GitHub setting)

For the demo, enable on `main` in GitHub → Settings → Branches:

1. Require a pull request before merging  
2. Require at least 1 approval (optional but recommended)  
3. Do not allow direct pushes of bot translation commits to `main`

Documented here because branch rules are repo settings, not files in git.
