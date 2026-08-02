"""LLM auto-checklist review via Gemini (for PR pitch / Phase 4+)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

from common import (
    REPO_ROOT,
    artifacts_dir,
    flatten_json,
    load_config,
    load_json_file,
    target_path_for,
    to_repo_posix,
)

load_dotenv(REPO_ROOT / ".env")


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object from Gemini")
    return data


def call_gemini(model_name: str, prompt: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    )
    raw = getattr(response, "text", None) or ""
    if not raw and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts
        raw = "".join(getattr(p, "text", "") for p in parts)
    return _extract_json_object(raw)


def units_payload(entry: dict[str, Any], source: dict, target: dict) -> dict[str, Any]:
    source_flat = flatten_json(source)
    target_flat = flatten_json(target)
    keys = sorted(
        set(entry.get("added_keys", []) + entry.get("changed_keys", []))
        or set(source_flat)
    )
    pairs = []
    for key in keys:
        pairs.append(
            {
                "key": key,
                "source": source_flat.get(key),
                "target": target_flat.get(key),
            }
        )
    return {"pairs": pairs, "all_source_keys": len(source_flat), "all_target_keys": len(target_flat)}


def build_prompt(locale: str, files_payload: list[dict[str, Any]]) -> str:
    return f"""You are a localization QA reviewer for a software demo.

Target locale: {locale} (French Canada if fr_ca).

Review ONLY the provided source/target pairs and answer the checklist.

Return JSON with this exact shape:
{{
  "status": "PASS" | "NEEDS_REVIEW" | "FAIL",
  "summary": "one short sentence",
  "checklist": [
    {{
      "id": "translations_ok",
      "label": "Translations look correct for fr-CA",
      "passed": true,
      "notes": "short note"
    }},
    {{
      "id": "structure_ok",
      "label": "Placeholders / JSON structure look fine",
      "passed": true,
      "notes": "short note"
    }},
    {{
      "id": "approve_ready",
      "label": "Approve to merge, or request changes",
      "passed": true,
      "notes": "PASS means approve-ready; false means request changes / human review"
    }}
  ]
}}

Rules:
- If many targets are dummy $$$ placeholders, mark translations_ok and approve_ready as false, status NEEDS_REVIEW.
- If placeholders are broken, mark structure_ok false and status FAIL or NEEDS_REVIEW.
- Be strict but practical for a demo.
- Do not wrap in markdown.

Files payload:
{json.dumps(files_payload, ensure_ascii=False, indent=2)}
"""


def render_checklist_md(review: dict[str, Any]) -> str:
    lines = [
        "## LLM auto checklist",
        "",
        f"- **LLM status:** `{review.get('status')}`",
        f"- **Summary:** {review.get('summary', '')}",
        "",
    ]
    for item in review.get("checklist") or []:
        mark = "x" if item.get("passed") else " "
        lines.append(f"- [{mark}] {item.get('label')} — {item.get('notes', '')}")
    lines.append("")
    return "\n".join(lines)


def merge_into_qa_reports(review: dict[str, Any], cfg: dict) -> None:
    art = artifacts_dir(cfg)
    qa_json_path = art / "qa-report.json"
    qa_md_path = art / "qa-report.md"

    if qa_json_path.is_file():
        qa = json.loads(qa_json_path.read_text(encoding="utf-8"))
    else:
        qa = {
            "status": "NEEDS_REVIEW",
            "recommended_label": "needs-l10n-review",
            "reason": "rules QA missing; LLM review only",
            "summary": {"files_checked": 0, "hard_failures": 0, "soft_findings": 0},
            "files": [],
        }

    qa["llm_review"] = review

    # Escalate final gate using LLM + existing rules status
    rules_status = qa.get("status", "NEEDS_REVIEW")
    llm_status = review.get("status", "NEEDS_REVIEW")
    rank = {"PASS": 0, "NEEDS_REVIEW": 1, "FAIL": 2}
    final = rules_status if rank.get(rules_status, 1) >= rank.get(llm_status, 1) else llm_status
    # If either needs review/fail, don't stay PASS
    if rules_status != "PASS" or llm_status != "PASS":
        final = "FAIL" if "FAIL" in (rules_status, llm_status) else "NEEDS_REVIEW"

    labels = cfg.get("pr", {})
    qa["status"] = final
    qa["recommended_label"] = (
        labels.get("label_qa_pass", "l10n-qa-pass")
        if final == "PASS"
        else labels.get("label_needs_review", "needs-l10n-review")
    )
    qa["reason"] = f"rules={rules_status}; llm={llm_status}"
    qa_json_path.write_text(json.dumps(qa, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checklist_md = render_checklist_md(review)
    if qa_md_path.is_file():
        existing = qa_md_path.read_text(encoding="utf-8")
        # refresh status line if present
        existing = re.sub(
            r"^- \*\*Status:\*\* .*",
            f"- **Status:** {final}",
            existing,
            count=1,
            flags=re.M,
        )
        existing = re.sub(
            r"^- \*\*Recommended label:\*\* .*",
            f"- **Recommended label:** `{qa['recommended_label']}`",
            existing,
            count=1,
            flags=re.M,
        )
        if "## LLM auto checklist" in existing:
            existing = re.sub(
                r"## LLM auto checklist[\s\S]*?(?=## |\Z)",
                checklist_md + "\n",
                existing,
                count=1,
            )
        else:
            existing = existing.rstrip() + "\n\n" + checklist_md
        qa_md_path.write_text(existing, encoding="utf-8")
    else:
        qa_md_path.write_text(
            f"# QA Report\n\n- **Status:** {final}\n\n{checklist_md}",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM checklist review")
    parser.add_argument("--diff", default="artifacts/diff-report.json")
    parser.add_argument("--locale", default="")
    parser.add_argument("--model", default="")
    args = parser.parse_args()

    cfg = load_config()
    locale = args.locale or (cfg.get("target_locales") or ["fr_ca"])[0]
    model_name = args.model or cfg.get("gemini_model") or "gemini-2.5-flash"

    diff_path = Path(args.diff)
    if not diff_path.is_absolute():
        diff_path = REPO_ROOT / diff_path
    if not diff_path.is_file():
        print(f"Missing diff report: {diff_path}", file=sys.stderr)
        return 1

    report = json.loads(diff_path.read_text(encoding="utf-8"))
    files_payload: list[dict[str, Any]] = []
    for entry in report.get("files") or []:
        if entry.get("change_type") in {"deleted", "error"}:
            continue
        source_rel = entry["source_path"]
        source_path = REPO_ROOT / Path(*source_rel.replace("\\", "/").split("/"))
        target_path = target_path_for(source_path, locale)
        if not source_path.is_file() or not target_path.is_file():
            continue
        source = load_json_file(source_path)
        target = load_json_file(target_path)
        files_payload.append(
            {
                "source_path": source_rel,
                "target_path": to_repo_posix(target_path),
                "change_type": entry.get("change_type"),
                **units_payload(entry, source, target),
            }
        )

    if not files_payload:
        print("No files for LLM review.")
        return 0

    print(f"LLM checklist review for {len(files_payload)} file(s)...")
    review = call_gemini(model_name, build_prompt(locale, files_payload))
    review["generated_at"] = datetime.now(timezone.utc).isoformat()
    review["engine"] = model_name

    out = artifacts_dir(cfg) / "llm-review.json"
    out.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    merge_into_qa_reports(review, cfg)

    print(
        f"LLM review {review.get('status')} | wrote {to_repo_posix(out)} "
        f"and updated artifacts/qa-report.*"
    )
    return 0 if review.get("status") != "FAIL" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
