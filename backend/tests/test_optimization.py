import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Analysis, OptimizationChange, OptimizationDraft, Resume
from app.services.model_config import LLMConfig
from app.services.optimization import generate_optimization, optimization_change_violations, publish_draft


def test_resume_optimizer_requires_model_configuration():
    resume = Resume(
        user_id="test-user",
        original_name="resume.pdf",
        storage_name="stored.pdf",
        content="具有三年产品设计经验。",
    )
    analysis = Analysis(
        user_id="test-user",
        resume_id="resume-id",
        job_description="需要三年产品设计经验，负责需求分析和跨团队协作。",
        report={"total": 60, "requirements": []},
        status="completed",
    )

    with pytest.raises(HTTPException) as error:
        generate_optimization(resume, analysis, LLMConfig(None, None, "test-model"))
    assert error.value.status_code == 409
    assert "API Key" in str(error.value.detail)


def test_publish_draft_applies_only_accepted_changes():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    resume = Resume(
        user_id="test-user",
        original_name="resume.pdf",
        storage_name="stored.pdf",
        content="负责需求分析。参与项目管理。",
    )
    db.add(resume)
    db.flush()
    draft = OptimizationDraft(
        user_id=resume.user_id,
        resume_id=resume.id,
        headline="AI 产品经理",
        summary="优化表达",
        optimized_markdown="模型的整篇草稿不应直接发布",
    )
    db.add(draft)
    db.flush()
    db.add_all(
        [
            OptimizationChange(
                draft_id=draft.id,
                title="接受项",
                original_text="负责需求分析。",
                suggested_text="负责需求分析与优先级梳理。",
                rationale="更明确",
                evidence_quote="负责需求分析。",
                decision="accepted",
            ),
            OptimizationChange(
                draft_id=draft.id,
                title="拒绝项",
                original_text="参与项目管理。",
                suggested_text="主导项目管理。",
                rationale="强化表达",
                evidence_quote="参与项目管理。",
                decision="rejected",
            ),
        ]
    )
    db.commit()

    version = publish_draft(db, draft)

    assert version.markdown == "负责需求分析与优先级梳理。参与项目管理。"
    assert "主导项目管理" not in version.markdown


def test_optimization_guard_rejects_new_facts():
    resume = "在示例公司担任产品助理，负责需求分析。"
    violations = optimization_change_violations(
        resume,
        "负责需求分析。",
        "在新公司担任高级产品经理，使用 LangGraph 使转化率提升 30%。",
        "负责需求分析。",
        {"langgraph", "商业化"},
    )
    assert "introduced_number" in violations
    assert "introduced_technical_term" in violations
    assert "introduced_named_fact" in violations
    assert "introduced_knowledge_skill" in violations
