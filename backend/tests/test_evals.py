from evals.generator import RULE_KEYS, generate_cases
from evals.runner import evaluate_dataset


def test_synthetic_dataset_has_twenty_labeled_cases():
    cases = generate_cases()
    assert len(cases) == 20
    assert all(set(case.expected_statuses) == set(RULE_KEYS) for case in cases)
    assert any("hard_gate" in case.tags for case in cases)
    assert any("keyword_stuffing" in case.tags for case in cases)


def test_agent_passes_offline_evaluation_smoke_suite():
    summary = evaluate_dataset(limit=5)
    assert summary.passed_cases == summary.total_cases
    assert summary.evidence_validity == 1.0
    assert summary.deterministic_rate == 1.0
    assert summary.optimization_guard_accuracy == 1.0
    assert summary.metamorphic_pass_rate == 1.0
