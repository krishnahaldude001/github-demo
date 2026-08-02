# Demo test content — how to trigger the pipeline

## What we added

New source file:

`Folder 1/file_demo.json`

It mixes normal text + variables/placeholders:

- `{ProductName}`
- `{userName}`
- `{orderId}`
- `{SupportEmail}`

These must stay **unchanged** in French. Only surrounding words are translated.

---

## How to trigger (recommended for LinkedIn)

### Option A — Edit on GitHub (best for video)

1. Open https://github.com/krishnahaldude001/github-demo/blob/main/Folder%201/file_demo.json  
2. Edit one string (example below)  
3. **Commit directly to `main`**  
4. Open **Actions** → **Localize**  
5. Open PR: https://github.com/krishnahaldude001/github-demo/pull/7  

### Option B — Local command example

```bash
cd "github-demo"

# 1) Edit the source file (example change)
#    Change "Click here to continue" -> "Click here to get started"

# 2) Commit + push to main (triggers Actions)
git add "Folder 1/file_demo.json"
git commit -m "demo: update file_demo.json source string"
git push origin main
```

Then watch:

- Actions: https://github.com/krishnahaldude001/github-demo/actions  
- PR: https://github.com/krishnahaldude001/github-demo/pull/7  

---

## Example edits you can make on camera

| Change | Why it’s good on video |
|--------|-------------------------|
| Edit `cta` text | Shows delta translation of 1 key |
| Add `"thanks": "Thank you, {userName}."` | Shows new key + placeholder kept |
| Add a brand-new file `Folder 2/file_new.json` | Shows full-file translation |

---

## Expected French behavior

Source:

`Hello, {userName}!`

Target should look like:

`Bonjour, {userName}!`

Not:

`Bonjour, {nomUtilisateur}!`
