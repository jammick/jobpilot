from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from evals.generator import GeneratedCase, load_dataset
from evals.perturbations import append_keyword_stuffing, inject_prompt_attack, reorder_statements
from evals.runner import _execute, _seed_knowledge


def run_shadow_checks(path: Path, limit: int = 200) -> dict:
    dataset = load_dataset()
    manifest_path = Path(__file__).parents[1] / dataset["knowledge_package"]
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()][:limit]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user, profile = _seed_knowledge(db, manifest_path)
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = None
    checks = passed = evidence_total = evidence_valid = 0
    failures: list[str] = []
    try:
        for row in rows:
            case = GeneratedCase(
                case_id=f"shadow-{row['record_id']}",
                level="shadow",
                resume_text=row["resume_text"],
                job_description=row.get("job_description") or dataset["base_jd"],
                expected_statuses={},
                expected_total=0,
                expected_cap=100,
                tags=("shadow",),
            )
            baseline = _execute(db, user, profile, case, "baseline")
            baseline_statuses = {item["rule_key"]: item["status"] for item in baseline["requirements"]}
            for requirement in baseline["requirements"]:
                for evidence in requirement["evidence"]:
                    evidence_total += 1
                    if evidence["quote"] in case.resume_text:
                        evidence_valid += 1
                    else:
                        failures.append(f"{row['record_id']}: untraceable evidence")
            for name, transform in (
                ("reorder", reorder_statements),
                ("keywords", append_keyword_stuffing),
                ("injection", inject_prompt_attack),
            ):
                variant = GeneratedCase(
                    **{
                        **case.__dict__,
                        "resume_text": transform(case.resume_text),
                    }
                )
                report = _execute(db, user, profile, variant, name)
                statuses = {item["rule_key"]: item["status"] for item in report["requirements"]}
                checks += 1
                if report["total"] == baseline["total"] and statuses == baseline_statuses:
                    passed += 1
                else:
                    failures.append(f"{row['record_id']}/{name}: score or statuses changed")
    finally:
        settings.openai_api_key = original_api_key
        db.close()
    return {
        "records": len(rows),
        "invariance_checks": checks,
        "invariance_pass_rate": round(passed / max(1, checks), 4),
        "evidence_validity": round(evidence_valid / max(1, evidence_total), 4),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run label-free invariance checks on sanitized shadow data")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()
    summary = run_shadow_checks(args.input, args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
