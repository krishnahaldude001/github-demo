"""Phase 3: translate source JSON to target locales via Gemini."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

from common import (
    REPO_ROOT,
    delete_nested_value,
    flatten_json,
    glossary_text,
    load_config,
    load_json_file,
    set_nested_value,
    target_path_for,
    to_repo_posix,
    write_json_file,
)

load_dotenv(REPO_ROOT / ".env")


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Gemini response was not a JSON object")
    return data


def _locale_label(locale: str) -> str:
    labels = {
        "fr_ca": "French (Canada)",
        "fr_fr": "French (France)",
        "de_de": "German (Germany)",
        "es_es": "Spanish (Spain)",
        "ja_jp": "Japanese",
    }
    return labels.get(locale, locale)


def call_gemini(model_name: str, prompt: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing. Set it in .env or the environment.")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )
    raw = getattr(response, "text", None) or ""
    if not raw and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts
        raw = "".join(getattr(p, "text", "") for p in parts)
    return _extract_json_object(raw)


def build_prompt(
    *,
    locale: str,
    mode: str,
    units: dict[str, str],
    source_obj: dict,
    existing_target: dict | None,
) -> str:
    glossary = glossary_text()
    return f"""You are a professional software localization translator.

Target locale: {_locale_label(locale)} ({locale})
Mode: {mode}

Rules:
- Translate ONLY the strings in "units_to_translate".
- Return a JSON object mapping each dotted key to its translated string.
- Preserve placeholders exactly (e.g. {{name}}, %s, HTML tags).
- Do not invent keys. Do not wrap the answer in markdown.
- Keep product/proper nouns per glossary when provided.
- Prefer natural UI tone for the target locale.

Glossary / style notes:
{glossary or "(none)"}

Full source JSON (context only):
{json.dumps(source_obj, ensure_ascii=False, indent=2)}

Existing target JSON (keep unchanged keys stable; may be incomplete):
{json.dumps(existing_target or {{}}, ensure_ascii=False, indent=2)}

units_to_translate:
{json.dumps(units, ensure_ascii=False, indent=2)}
"""


def units_for_file(entry: dict[str, Any], source_obj: dict) -> tuple[str, dict[str, str]]:
    change_type = entry["change_type"]
    if change_type == "added":
        flat = flatten_json(source_obj)
        return "full", {k: str(v) if not isinstance(v, str) else v for k, v in flat.items()}

    if change_type == "deleted":
        return "delete", {}

    if change_type == "error":
        raise RuntimeError(f"Diff entry has error for {entry['source_path']}: {entry.get('error')}")

    units: dict[str, str] = {}
    for key, value in entry.get("units", {}).get("added", {}).items():
        units[key] = value if isinstance(value, str) else str(value)
    for key, payload in entry.get("units", {}).get("changed", {}).items():
        new_val = payload.get("new") if isinstance(payload, dict) else payload
        units[key] = new_val if isinstance(new_val, str) else str(new_val)
    return "delta", units


def apply_deletes(target: dict, deleted_keys: list[str]) -> None:
    for key in deleted_keys:
        delete_nested_value(target, key)


def translate_file_entry(entry: dict[str, Any], locale: str, model_name: str) -> Path | None:
    source_rel = entry["source_path"]
    source_path = REPO_ROOT / Path(*source_rel.replace("\\", "/").split("/"))
    if not source_path.is_file() and entry["change_type"] != "deleted":
        raise FileNotFoundError(f"Source missing: {source_rel}")

    target_path = target_path_for(source_path if source_path.exists() else REPO_ROOT / source_rel, locale)

    if entry["change_type"] == "deleted":
        if target_path.exists():
            target_path.unlink()
            print(f"Deleted target {to_repo_posix(target_path)}")
        return None

    source_obj = load_json_file(source_path)
    mode, units = units_for_file(entry, source_obj)
    existing = load_json_file(target_path) if target_path.is_file() else {}

    apply_deletes(existing, entry.get("deleted_keys", []))

    if not units:
        write_json_file(target_path, existing)
        print(f"Updated deletes only -> {to_repo_posix(target_path)}")
        return target_path

    prompt = build_prompt(
        locale=locale,
        mode=mode,
        units=units,
        source_obj=source_obj,
        existing_target=existing,
    )
    print(f"Gemini {mode} translate {len(units)} unit(s) -> {locale} for {source_rel}")
    translated = call_gemini(model_name, prompt)

    missing = [k for k in units if k not in translated]
    if missing:
        raise RuntimeError(f"Gemini missing keys: {missing}")

    if mode == "full":
        out: dict[str, Any] = {}
        for key, value in translated.items():
            if key in units:
                set_nested_value(out, key, value)
        write_json_file(target_path, out)
    else:
        out = existing
        for key in units:
            set_nested_value(out, key, translated[key])
        write_json_file(target_path, out)

    print(f"Wrote {to_repo_posix(target_path)}")
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate with Gemini")
    parser.add_argument("--diff", default="artifacts/diff-report.json")
    parser.add_argument("--locale", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    cfg = load_config()
    locale = args.locale or (cfg.get("target_locales") or ["fr_ca"])[0]
    model_name = args.model or cfg.get("gemini_model") or "gemini-2.0-flash"

    diff_path = Path(args.diff)
    if not diff_path.is_absolute():
        diff_path = REPO_ROOT / diff_path
    if not diff_path.is_file():
        print(f"Diff report not found: {diff_path}", file=sys.stderr)
        return 1

    report = json.loads(diff_path.read_text(encoding="utf-8"))
    files = report.get("files") or []
    if not files:
        print("No file changes in diff report — nothing to translate.")
        return 0

    for entry in files:
        if locale not in entry.get("locale_targets", [locale]):
            continue
        if entry.get("change_type") == "error":
            print(f"Skipping error entry: {entry.get('source_path')}: {entry.get('error')}")
            continue
        translate_file_entry(entry, locale, model_name)

    print("Gemini translation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
