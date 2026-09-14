from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.models import Analysis, CompetencyRule, KnowledgeBase, RoleProfile, Resume, Skill, SkillAlias, User
from app.schemas.contracts import KnowledgeManifestInput
from app.services.analysis import index_resume, run_analysis
from app.services.optimization import optimization_change_violations
from evals.generator import GeneratedCase, generate_cases, load_dataset
from evals.perturbations import append_keyword_stuffing, inject_prompt_attack, reorder_statements


@dataclass
class CaseResult:
    case_id: str
    passed: bool
    expected_total: int
    actual_total: int | None
    errors: list[str]


@dataclass
class EvaluationSummary:
    dataset_version: str
    total_cases: int
    passed_cases: int
    score_accuracy: float
    status_accuracy: float
    evidence_validity: float
    deterministic_rate: float
    optimization_guard_accuracy: float
    optimization_guard_failures: list[str]
    metamorphic_pass_rate: float
    metamorphic_failures: list[str]
    results: list[CaseResult]


def _seed_knowledge(db: Session, manifest_path: Path) -> tuple[User, RoleProfile]:
    manifest = KnowledgeManifestInput.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    user = User(email="eval@jobpilot.local", password_hash="offline-eval")
    db.add(user)
    db.flush()
    base = KnowledgeBase(
        user_id=user.id,
        name=manifest.name,
        role_key=manifest.role_key,
        version=manifest.version,
        status="published",
        embedding_model="offline-keyword-eval",
        manifest=manifest.model_dump(),
    )
    db.add(base)
    db.flush()
    profile = RoleProfile(knowledge_base_id=base.id, role_key=manifest.role_key, name=manifest.role_name)
    db.add(profile)
    db.flush()
    skills: dict[str, Skill] = {}
    for definition in manifest.skills:
        skill = Skill(knowledge_base_id=base.id, canonical_name=definition.name, category=definition.category)
        db.add(skill)
        db.flush()
        skills[definition.name.lower()] = skill
        for alias in {definition.name, *definition.aliases}:
            db.add(SkillAlias(skill_id=skill.id, alias=alias.strip().lower()))
    for rule in manifest.rules:
        db.add(
            CompetencyRule(
                role_profile_id=profile.id,
                rule_key=rule.key,
                name=rule.name,
                weight=rule.weight,
                required=rule.required,
                skill_names=[skills[name.lower()].canonical_name for name in rule.skills],
                description=rule.description,
            )
        )
    db.commit()
    return user, profile


def _execute(db: Session, user: User, profile: RoleProfile, case: GeneratedCase, run_number: int | str) -> dict:
    resume = Resume(
        user_id=user.id,
        original_name=f"{case.case_id}.txt",
        storage_name=f"{case.case_id}-{run_number}.txt",
        content=case.resume_text,
    )
    db.add(resume)
    db.flush()
    index_resume(db, resume)
    analysis = Analysis(
        user_id=user.id,
        resume_id=resume.id,
        role_profile_id=profile.id,
        job_description=case.job_description,
    )
    db.add(analysis)
    db.commit()
    run_analysis(db, analysis, resume, profile.id)
    db.refresh(analysis)
    if not analysis.report:
        raise RuntimeError(analysis.error_message or "Agent did not produce a report")
    return analysis.report


def evaluate_dataset(limit: int | None = None) -> EvaluationSummary:
    dataset = load_dataset()
    manifest_path = Path(__file__).parents[1] / dataset["knowledge_package"]
    cases = generate_cases()[:limit]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user, profile = _seed_knowledge(db, manifest_path)
    settings = get_settings()
    original_api_key = settings.openai_api_key
    settings.openai_api_key = None
    results: list[CaseResult] = []
    status_checks = evidence_checks = evidence_total = deterministic_checks = 0
    metamorphic_failures: list[str] = []
    metamorphic_checks = 0
    try:
        for case in cases:
            errors: list[str] = []
            first = _execute(db, user, profile, case, 1)
            second = _execute(db, user, profile, case, 2)
            actual_statuses = {item["rule_key"]: item["status"] for item in first["requirements"]}
            for rule_key, expected in case.expected_statuses.items():
                status_checks += 1
                if actual_statuses.get(rule_key) != expected:
                    errors.append(f"{rule_key}: expected {expected}, got {actual_statuses.get(rule_key)}")
            if first["total"] != case.expected_total:
                errors.append(f"score: expected {case.expected_total}, got {first['total']}")
            if first["hard_gates"]["cap"] != case.expected_cap:
                errors.append(f"cap: expected {case.expected_cap}, got {first['hard_gates']['cap']}")
            if first["total"] == second["total"] and actual_statuses == {
                item["rule_key"]: item["status"] for item in second["requirements"]
            }:
                deterministic_checks += 1
            else:
                errors.append("repeated execution produced a different result")
            for requirement in first["requirements"]:
                for evidence in requirement["evidence"]:
                    evidence_total += 1
                    if evidence["quote"] in case.resume_text:
                        evidence_checks += 1
                    else:
                        errors.append(f"untraceable evidence in {requirement['rule_key']}")
            matched_without_evidence = [
                item["rule_key"] for item in first["requirements"]
                if item["status"] == "matched" and not item["evidence"]
            ]
            if matched_without_evidence:
                errors.append(f"matched without evidence: {matched_without_evidence}")
            for variant_name, transform in (
                ("reorder", reorder_statements),
                ("keyword_stuffing", append_keyword_stuffing),
                ("prompt_injection", inject_prompt_attack),
            ):
                variant = GeneratedCase(
                    case_id=case.case_id,
                    level=case.level,
                    resume_text=transform(case.resume_text),
                    job_description=case.job_description,
                    expected_statuses=case.expected_statuses,
                    expected_total=case.expected_total,
                    expected_cap=case.expected_cap,
                    tags=case.tags,
                )
                variant_report = _execute(db, user, profile, variant, variant_name)
                variant_statuses = {item["rule_key"]: item["status"] for item in variant_report["requirements"]}
                metamorphic_checks += 1
                if variant_report["total"] != first["total"] or variant_statuses != actual_statuses:
                    metamorphic_failures.append(
                        f"{case.case_id}/{variant_name}: score or statuses changed"
                    )
            results.append(CaseResult(case.case_id, not errors, case.expected_total, first.get("total"), errors))
    finally:
        settings.openai_api_key = original_api_key
        db.close()
    exact_statuses = status_checks - sum(
        1 for result in results for error in result.errors if ": expected " in error and not error.startswith(("score:", "cap:"))
    )
    manifest = KnowledgeManifestInput.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    protected_terms = {
        term.lower()
        for skill in manifest.skills
        for term in (skill.name, *skill.aliases)
    }
    guard_failures: list[str] = []
    guard_cases = dataset.get("optimization_guard_cases", [])
    for guard_case in guard_cases:
        violations = optimization_change_violations(
            guard_case["resume"],
            guard_case["original"],
            guard_case["suggested"],
            guard_case["evidence"],
            protected_terms,
        )
        actual_valid = not violations
        if actual_valid != guard_case["expected_valid"]:
            guard_failures.append(
                f"{guard_case['id']}: expected valid={guard_case['expected_valid']}, violations={violations}"
            )
    return EvaluationSummary(
        dataset_version=dataset["dataset_version"],
        total_cases=len(results),
        passed_cases=sum(result.passed for result in results),
        score_accuracy=round(sum(result.actual_total == result.expected_total for result in results) / max(1, len(results)), 4),
        status_accuracy=round(exact_statuses / max(1, status_checks), 4),
        evidence_validity=round(evidence_checks / max(1, evidence_total), 4),
        deterministic_rate=round(deterministic_checks / max(1, len(results)), 4),
        optimization_guard_accuracy=round((len(guard_cases) - len(guard_failures)) / max(1, len(guard_cases)), 4),
        optimization_guard_failures=guard_failures,
        metamorphic_pass_rate=round((metamorphic_checks - len(metamorphic_failures)) / max(1, metamorphic_checks), 4),
        metamorphic_failures=metamorphic_failures,
        results=results,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic JobPilot Agent evaluations")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Print the complete machine-readable report")
    args = parser.parse_args()
    summary = evaluate_dataset(args.limit)
    if args.json:
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    else:
        print(f"JobPilot Agent Eval v{summary.dataset_version}")
        print(f"cases={summary.passed_cases}/{summary.total_cases} score_accuracy={summary.score_accuracy:.1%}")
        print(f"status_accuracy={summary.status_accuracy:.1%} evidence_validity={summary.evidence_validity:.1%} deterministic={summary.deterministic_rate:.1%}")
        print(f"optimization_guard_accuracy={summary.optimization_guard_accuracy:.1%}")
        print(f"metamorphic_pass_rate={summary.metamorphic_pass_rate:.1%}")
        for result in summary.results:
            if not result.passed:
                print(f"FAIL {result.case_id}: {'; '.join(result.errors)}")
        for failure in summary.optimization_guard_failures:
            print(f"FAIL optimization_guard {failure}")
        for failure in summary.metamorphic_failures:
            print(f"FAIL metamorphic {failure}")
    return 0 if summary.passed_cases == summary.total_cases and not summary.optimization_guard_failures and not summary.metamorphic_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
