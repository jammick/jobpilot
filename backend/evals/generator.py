from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


RULE_KEYS = (
    "product_strategy",
    "ai_literacy",
    "delivery",
    "outcomes",
    "business",
    "education",
)


@dataclass(frozen=True)
class GeneratedCase:
    case_id: str
    level: str
    resume_text: str
    job_description: str
    expected_statuses: dict[str, str]
    expected_total: int
    expected_cap: int
    tags: tuple[str, ...]


def dataset_path() -> Path:
    return Path(__file__).parent / "cases" / "ai_product_manager_v1.json"


def load_dataset(path: Path | None = None) -> dict:
    return json.loads((path or dataset_path()).read_text(encoding="utf-8"))


def generate_cases(path: Path | None = None) -> list[GeneratedCase]:
    """Render natural-language fixtures from structured, known facts."""
    dataset = load_dataset(path)
    strong_library = dataset["evidence_library"]
    partial_library = dataset["partial_evidence_library"]
    output: list[GeneratedCase] = []
    for spec in dataset["cases"]:
        strong, partial, mentioned = set(spec["strong"]), set(spec["partial"]), set(spec.get("mentioned", []))
        if (strong & partial) or (strong & mentioned) or (partial & mentioned):
            raise ValueError(f"{spec['id']} contains overlapping evidence levels")
        unknown = (strong | partial | mentioned) - set(RULE_KEYS)
        if unknown:
            raise ValueError(f"{spec['id']} contains unknown rules: {sorted(unknown)}")
        variant = int(spec.get("variant", 0))
        statements = [
            f"候选人级别：{spec['level']}。",
            "个人说明：拥有一般项目经历，日常工作包括资料整理、会议记录与进度沟通。",
        ]
        expected: dict[str, str] = {}
        for rule_key in RULE_KEYS:
            if rule_key in strong:
                options = strong_library[rule_key]
                statements.append(options[variant % len(options)])
                expected[rule_key] = "matched"
            elif rule_key in partial:
                options = partial_library[rule_key]
                statements.append(options[variant % len(options)])
                expected[rule_key] = "partial"
            elif rule_key in mentioned:
                options = partial_library[rule_key]
                statements.append(options[2 % len(options)])
                expected[rule_key] = "unmatched"
            else:
                expected[rule_key] = "unmatched"
        output.append(
            GeneratedCase(
                case_id=spec["id"],
                level=spec["level"],
                resume_text="\n".join(statements),
                job_description=dataset["base_jd"],
                expected_statuses=expected,
                expected_total=spec["expected_total"],
                expected_cap=spec["expected_cap"],
                tags=tuple(spec.get("tags", [])),
            )
        )
    return output
