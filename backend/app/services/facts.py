from __future__ import annotations

import re
from dataclasses import dataclass, field


EXTRACTOR_VERSION = "rules-v1"
BOUNDARIES = "\n。！？；;.!?"
ACTION_MARKERS = (
    "负责", "主导", "设计", "搭建", "实现", "推动", "优化", "使用", "基于",
    "完成", "开展", "制定", "通过", "参与", "验证", "led", "built", "designed",
    "delivered", "implemented", "used",
)
WEAK_MARKERS = (
    "了解", "熟悉概念", "学习过", "接触过", "know about", "familiar with",
)
MENTION_MARKERS = ("关键词", "技能清单", "skills:", "keywords:")
OUTCOME_MARKERS = (
    "指标", "a/b", "转化率", "留存", "准确率", "成本", "效率", "%", "提升", "降低",
    "增长", "减少", "节省", "缩短", "达到", "超过", "覆盖", "零故障", "满意度",
)


@dataclass(frozen=True)
class ExtractedFact:
    fact_type: str
    value: str
    quote: str
    char_start: int
    char_end: int
    strength: str = "strong"
    details: dict = field(default_factory=dict)


def sentence_span(text: str, position: int) -> tuple[str, int, int]:
    def is_boundary(index: int) -> bool:
        char = text[index]
        if char not in BOUNDARIES:
            return False
        # Dots inside Node.js, version numbers, URLs or dates are not sentence
        # boundaries. This prevents truncated or misleading evidence quotes.
        if char == "." and index > 0 and index + 1 < len(text):
            if text[index - 1].isalnum() and text[index + 1].isalnum():
                return False
        return True

    left_boundary = next((index for index in range(position - 1, -1, -1) if is_boundary(index)), -1)
    left = left_boundary + 1
    right_boundary = next((index for index in range(position, len(text)) if is_boundary(index)), len(text))
    right = right_boundary + 1 if right_boundary < len(text) else right_boundary
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    return text[left:right], left, right


def evidence_strength(statement: str, skill: str) -> str:
    lower = statement.lower()
    if any(marker in lower for marker in MENTION_MARKERS):
        return "mentioned"
    if skill == "学历资格":
        return "strong"
    if any(marker in lower for marker in WEAK_MARKERS) and not any(marker in lower for marker in ACTION_MARKERS):
        return "weak"
    return "strong" if any(marker in lower for marker in ACTION_MARKERS) else "weak"


def has_outcome_signal(statement: str) -> bool:
    lower = statement.lower()
    if any(marker in lower for marker in OUTCOME_MARKERS):
        return True
    return bool(
        re.search(
            r"\d+(?:\.\d+)?\s*(?:倍|人|位|户|场|次|项|条|个|家|元|万元|小时|分钟|秒|天|ms|qps)",
            lower,
        )
    )


def _alias_pattern(alias: str) -> str:
    escaped = re.escape(alias.lower())
    # ASCII aliases need token boundaries: BI must not match Mobile and AI must
    # not match email. Chinese phrases remain valid as in-string phrases.
    if re.search(r"[a-z0-9]", alias, flags=re.IGNORECASE):
        return rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return escaped


def _add(
    output: list[ExtractedFact],
    seen: set[tuple[str, str, int]],
    fact_type: str,
    value: str,
    text: str,
    position: int,
    *,
    strength: str = "strong",
    details: dict | None = None,
) -> None:
    quote, start, end = sentence_span(text, position)
    key = (fact_type, value.lower(), start)
    if quote and key not in seen and text[start:end] == quote:
        output.append(ExtractedFact(fact_type, value, quote, start, end, strength, details or {}))
        seen.add(key)


def extract_resume_facts(text: str, aliases: dict[str, str]) -> list[ExtractedFact]:
    """Extract traceable facts without calling an LLM.

    The rules intentionally prefer precision over recall. LLM enrichment can be
    added later, but any enriched fact must still pass the same span validation.
    """
    output: list[ExtractedFact] = []
    seen: set[tuple[str, str, int]] = set()
    lower = text.lower()

    for alias, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        for match in re.finditer(_alias_pattern(alias), lower):
            quote, _, _ = sentence_span(text, match.start())
            _add(
                output,
                seen,
                "skill",
                canonical,
                text,
                match.start(),
                strength=evidence_strength(quote, canonical),
                details={"matched_alias": text[match.start():match.end()]},
            )

    patterns = (
        ("education", r"本科|学士|硕士|研究生|博士|大专|bachelor|master|phd"),
        ("role", r"(?:AI|高级|资深|助理|初级|中级)?(?:产品经理|项目经理|工程师|设计师|分析师|总监)"),
        ("organization", r"[\u4e00-\u9fffA-Za-z0-9·]{2,24}(?:公司|集团|大学|学院)"),
        ("experience_years", r"(?<!\d)(\d{1,2})\s*(?:年|years?)"),
        ("employment_period", r"(?:19|20)\d{2}(?:[./年-]\d{1,2})?\s*(?:-|—|–|至|~)\s*(?:(?:19|20)\d{2}(?:[./年-]\d{1,2})?|至今|present)"),
    )
    for fact_type, pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            value = match.group(1) if fact_type == "experience_years" else match.group(0)
            details = {"years": int(value)} if fact_type == "experience_years" else {}
            _add(output, seen, fact_type, value, text, match.start(), details=details)

    for position in range(len(text)):
        if position and text[position - 1] not in BOUNDARIES:
            continue
        statement, start, end = sentence_span(text, position)
        if statement and has_outcome_signal(statement) and any(marker in statement.lower() for marker in ACTION_MARKERS):
            key = ("quantified_outcome", statement.lower(), start)
            if key not in seen:
                output.append(
                    ExtractedFact(
                        "quantified_outcome",
                        statement,
                        statement,
                        start,
                        end,
                        "strong",
                        {"numbers": re.findall(r"\d+(?:\.\d+)?%?", statement)},
                    )
                )
                seen.add(key)
    return output


def summarize_facts(facts: list) -> dict:
    by_type: dict[str, list[str]] = {}
    for fact in facts:
        by_type.setdefault(fact.fact_type, [])
        if fact.value not in by_type[fact.fact_type]:
            by_type[fact.fact_type].append(fact.value)
    years = [int(value) for value in by_type.get("experience_years", []) if str(value).isdigit()]
    return {
        "counts": {key: len(values) for key, values in by_type.items()},
        "experience_years": max(years) if years else None,
        "education": by_type.get("education", []),
        "roles": by_type.get("role", []),
        "organizations": by_type.get("organization", []),
        "quantified_outcomes": by_type.get("quantified_outcome", []),
    }
