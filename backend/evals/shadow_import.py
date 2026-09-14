from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Iterable


def source_registry() -> dict[str, dict]:
    path = Path(__file__).parent / "sources.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item for item in payload["sources"]}


def sanitize_text(value: str) -> str:
    """Remove common direct identifiers before shadow evaluation."""
    text = str(value or "")
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[PHONE]", text)
    text = re.sub(r"https?://\S+|www\.\S+", "[URL]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:\d[ -]*?){15,18}[0-9Xx]\b", "[ID]", text)
    return text.strip()


def _records(path: Path) -> Iterable[dict]:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        try:
            import pyarrow.parquet as parquet
        except ImportError as exc:
            raise ValueError("Parquet import requires: pip install -r requirements-eval.txt") from exc
        yield from parquet.read_table(path).to_pylist()
        return
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    payload = json.loads(path.read_text(encoding="utf-8")) if suffix == ".json" else None
    if suffix == ".json":
        rows = payload if isinstance(payload, list) else payload.get("data", [])
        yield from rows
        return
    if suffix == ".jsonl":
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                yield json.loads(line)
        return
    raise ValueError("shadow import supports CSV, JSON, JSONL or Parquet")


def _field_text(row: dict, field: str | None, source_id: str, *, kind: str) -> str:
    if not field:
        return ""
    if field != "__auto__":
        value = row.get(field, "")
        return "\n".join(str(item) for item in value) if isinstance(value, list) else str(value or "")
    if source_id == "hf-candidate-matching-synthetic" and kind == "resume":
        skills = "、".join(str(item) for item in row.get("skills", []))
        bullets = "\n".join(str(item) for item in row.get("experience_bullets", []))
        return (
            f"Target role: {row.get('role', '')}\n"
            f"Seniority: {row.get('seniority', '')}\n"
            f"Experience: {row.get('years_experience', '')} years\n"
            f"Education: {row.get('education', '')}\n"
            f"Skills: {skills}\n{row.get('summary', '')}\n{bullets}"
        )
    raise ValueError(f"no automatic {kind} adapter for source {source_id}")


def import_shadow_dataset(
    input_path: Path,
    output_path: Path,
    *,
    source_id: str,
    resume_field: str,
    jd_field: str | None,
    limit: int = 200,
) -> dict:
    source = source_registry().get(source_id)
    if not source:
        raise ValueError(f"unknown source_id: {source_id}")
    if not source["approved_for_shadow_data"]:
        raise ValueError(f"source {source_id} is reference-only and cannot be imported as shadow resumes")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    accepted: list[dict] = []
    rejected = 0
    for row in _records(input_path):
        resume = sanitize_text(_field_text(row, resume_field, source_id, kind="resume"))
        jd = sanitize_text(_field_text(row, jd_field, source_id, kind="jd")) if jd_field else ""
        if len(resume) < 30:
            rejected += 1
            continue
        digest = hashlib.sha256((resume + "\0" + jd).encode("utf-8")).hexdigest()
        accepted.append(
            {
                "record_id": digest[:16],
                "resume_text": resume,
                "job_description": jd,
                "source_id": source_id,
                "source_homepage": source["homepage"],
                "license": source["license"],
            }
        )
        if len(accepted) >= limit:
            break
    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in accepted) + ("\n" if accepted else ""),
        encoding="utf-8",
    )
    manifest = {
        "source": source,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "records": len(accepted),
        "rejected": rejected,
        "direct_identifiers_redacted": True,
        "privacy_review_required": True,
        "output": str(output_path),
    }
    output_path.with_suffix(output_path.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def import_shadow_preview(output_path: Path, *, source_id: str, limit: int = 100) -> dict:
    """Import the provider's small public preview without a Parquet dependency."""
    source = source_registry().get(source_id)
    if not source or not source.get("preview_api"):
        raise ValueError(f"source {source_id} does not provide an approved preview API")
    if not source["approved_for_shadow_data"]:
        raise ValueError(f"source {source_id} is not approved for shadow data")
    with urllib.request.urlopen(source["preview_api"], timeout=20) as response:
        raw = response.read()
    payload = json.loads(raw)
    rows = [item.get("row", {}) for item in payload.get("rows", [])][: min(limit, 100)]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    accepted = []
    for row in rows:
        resume = sanitize_text(_field_text(row, "__auto__", source_id, kind="resume"))
        if len(resume) < 30:
            continue
        digest = hashlib.sha256(resume.encode("utf-8")).hexdigest()
        accepted.append(
            {
                "record_id": digest[:16],
                "resume_text": resume,
                "job_description": "",
                "source_id": source_id,
                "source_homepage": source["homepage"],
                "source_revision": source.get("revision"),
                "license": source["license"],
            }
        )
    output_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in accepted) + ("\n" if accepted else ""),
        encoding="utf-8",
    )
    manifest = {
        "source": source,
        "preview_sha256": hashlib.sha256(raw).hexdigest(),
        "records": len(accepted),
        "direct_identifiers_redacted": True,
        "privacy_review_required": True,
        "output": str(output_path),
    }
    output_path.with_suffix(output_path.suffix + ".manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Sanitize a licensed local dataset for shadow evaluation")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", type=Path)
    input_group.add_argument("--from-preview", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".local/shadow/records.jsonl"))
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--resume-field", default="__auto__")
    parser.add_argument("--jd-field")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    if args.from_preview:
        manifest = import_shadow_preview(args.output, source_id=args.source_id, limit=args.limit)
    else:
        manifest = import_shadow_dataset(
            args.input,
            args.output,
            source_id=args.source_id,
            resume_field=args.resume_field,
            jd_field=args.jd_field,
            limit=args.limit,
        )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
