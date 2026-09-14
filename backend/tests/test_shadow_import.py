import json

import pytest

from evals.shadow_import import import_shadow_dataset, sanitize_text, source_registry
from evals.shadow_runner import run_shadow_checks


def test_shadow_import_redacts_direct_identifiers(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            [
                {
                    "resume": "候选人邮箱 test@example.com，手机 13800138000。负责 AI 产品需求与项目交付。",
                    "jd": "招聘 AI 产品经理，负责产品规划与 RAG 应用。",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "shadow.jsonl"
    manifest = import_shadow_dataset(
        source,
        output,
        source_id="hf-candidate-matching-synthetic",
        resume_field="resume",
        jd_field="jd",
    )
    record = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["records"] == 1
    assert "test@example.com" not in record["resume_text"]
    assert "13800138000" not in record["resume_text"]
    assert "[EMAIL]" in record["resume_text"]
    assert "[PHONE]" in record["resume_text"]


def test_reference_only_source_cannot_be_imported(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="reference-only"):
        import_shadow_dataset(
            source,
            tmp_path / "out.jsonl",
            source_id="onet-reference",
            resume_field="resume",
            jd_field=None,
        )


def test_approved_source_is_pinned_to_a_revision():
    source = source_registry()["hf-candidate-matching-synthetic"]
    assert len(source["revision"]) == 40
    assert source["license"] == "MIT"


def test_sanitizer_redacts_urls_and_ids():
    cleaned = sanitize_text("访问 https://example.com，身份证 110101199001011234")
    assert "https://" not in cleaned
    assert "110101199001011234" not in cleaned


def test_shadow_runner_checks_label_free_invariants(tmp_path):
    shadow = tmp_path / "records.jsonl"
    shadow.write_text(
        json.dumps(
            {
                "record_id": "sample-1",
                "resume_text": "负责需求分析，基于 LangChain 搭建知识库。推动跨团队协作并完成版本发布。",
                "job_description": "招聘 AI 产品经理，要求产品规划、RAG 和跨团队协作。",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = run_shadow_checks(shadow)
    assert summary["records"] == 1
    assert summary["invariance_pass_rate"] == 1.0
    assert summary["evidence_validity"] == 1.0
