import re
from collections import defaultdict


def keywords(text: str) -> set[str]:
    raw = re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{1,}|[\u4e00-\u9fff]{2,}", text.lower())
    stop = {"负责", "要求", "相关", "岗位", "经验", "以及", "具有", "能力", "优先", "熟悉"}
    return {item for item in raw if item not in stop}


def score(job: str, resume: str) -> dict:
    job_words, resume_words = keywords(job), keywords(resume)
    overlap = sorted(job_words & resume_words)
    coverage = round(100 * len(overlap) / max(1, len(job_words)))
    experience = 75 if re.search(r"\d+\s*年|year", resume.lower()) else 45
    education = 80 if re.search(r"本科|硕士|博士|bachelor|master", resume.lower()) else 55
    weights = {"技能匹配": 0.40, "经验相关性": 0.30, "学历与资格": 0.10, "关键词覆盖": 0.20}
    dimensions = {"技能匹配": coverage, "经验相关性": experience, "学历与资格": education, "关键词覆盖": coverage}
    total = round(sum(dimensions[name] * weight for name, weight in weights.items()))
    confidence = min(95, 45 + min(len(overlap), 15) * 3 + (15 if len(resume) > 800 else 0))
    return {
        "total": total,
        "dimensions": dimensions,
        "weights": {name: round(value * 100) for name, value in weights.items()},
        "confidence": confidence,
        "matched_keywords": overlap[:30],
        "missing_keywords": sorted(job_words - resume_words)[:20],
    }


def score_requirements(requirements: list[dict]) -> dict:
    """Pure, deterministic rubric scorer used by the LangGraph agent.

    Requirement weights do not have to be pre-rounded to exactly 100.  The
    scorer normalizes them, which makes dynamically generated JD rubrics safe
    from floating point drift while keeping published 100-point rubrics fully
    backward compatible.
    """
    score_by_status = {"matched": 1.0, "partial": 0.5, "unmatched": 0.0}
    total_weight = sum(max(0.0, float(item.get("weight", 0))) for item in requirements)
    if total_weight <= 0:
        return {
            "total": 0,
            "raw_total": 0,
            "dimensions": {},
            "weights": {},
            "confidence": 0,
            "hard_gates": {"missing": [], "cap": 100, "passed": True},
            "missing_keywords": [],
            "matched_keywords": [],
        }

    def factor(item: dict) -> float:
        return score_by_status.get(item.get("status"), 0.0)

    earned = sum(max(0.0, float(item.get("weight", 0))) * factor(item) for item in requirements)
    normalized_earned = earned if abs(total_weight - 100) < 0.001 else earned / total_weight * 100
    raw_total = round(normalized_earned)
    missing_hard = [item["name"] for item in requirements if item["required"] and item["status"] == "unmatched"]
    cap = 100 if not missing_hard else 59 if len(missing_hard) == 1 else 39
    total = min(raw_total, cap)

    dimension_totals: dict[str, float] = defaultdict(float)
    dimension_earned: dict[str, float] = defaultdict(float)
    for item in requirements:
        name = item.get("dimension") or item["name"]
        weight = max(0.0, float(item.get("weight", 0)))
        dimension_totals[name] += weight
        dimension_earned[name] += weight * factor(item)
    dimensions = {
        name: round(dimension_earned[name] / weight * 100) if weight else 0
        for name, weight in dimension_totals.items()
    }
    weights = {name: round(weight / total_weight * 100) for name, weight in dimension_totals.items()}
    supported_weight = sum(
        max(0.0, float(item.get("weight", 0))) * factor(item)
        for item in requirements
        if item.get("evidence")
    )
    confidence = round(min(100, supported_weight / total_weight * 100))
    return {
        "total": total,
        "raw_total": raw_total,
        "dimensions": dimensions,
        "weights": weights,
        "confidence": confidence,
        "hard_gates": {"missing": missing_hard, "cap": cap, "passed": not missing_hard},
        "missing_keywords": list(dict.fromkeys(item["name"] for item in requirements if item["status"] == "unmatched")),
        "matched_keywords": list(dict.fromkeys(item["name"] for item in requirements if item["status"] == "matched")),
    }
