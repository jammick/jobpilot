import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Resume, ResumeChunk, ResumeFact
from app.schemas.contracts import KnowledgeManifestInput
from app.services.knowledge import validate_manifest
from app.services import analysis as analysis_service
from app.services.analysis import _fallback_jd_profile, _generic_requirements, profile_matches_jd
from app.services.facts import extract_resume_facts
from app.services.scoring import score_requirements


def test_ai_product_manager_example_knowledge_package_is_valid():
    path = Path(__file__).parents[1] / "app" / "seed" / "ai-product-manager-v1.json"
    manifest = KnowledgeManifestInput.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert validate_manifest(manifest) == []
    assert sum(rule.weight for rule in manifest.rules) == 100
    assert any(rule.required for rule in manifest.rules)


def test_hard_gate_caps_a_deterministic_requirement_score():
    report = score_requirements(
        [
            {"name": "产品策略", "weight": 25, "required": True, "status": "matched", "evidence": [{}]},
            {"name": "LLM/RAG 与 AI 技术理解", "weight": 25, "required": True, "status": "unmatched", "evidence": []},
            {"name": "产品交付", "weight": 20, "required": False, "status": "matched", "evidence": [{}]},
            {"name": "项目成果", "weight": 15, "required": False, "status": "matched", "evidence": [{}]},
            {"name": "商业理解", "weight": 10, "required": False, "status": "matched", "evidence": [{}]},
            {"name": "学历资格", "weight": 5, "required": False, "status": "matched", "evidence": [{}]},
        ]
    )
    assert report["raw_total"] == 75
    assert report["total"] == 59
    assert report["hard_gates"]["missing"] == ["LLM/RAG 与 AI 技术理解"]


def test_jd_fallback_separates_required_and_preferred_skills():
    profile = _fallback_jd_profile(
        "AI 产品经理\n必须理解 LLM 并具备 3 年产品经验。\n熟悉 LangChain 优先。",
        {"llm": "大语言模型", "langchain": "RAG"},
    )
    assert "大语言模型" in profile.required_skills
    assert "RAG" in profile.preferred_skills
    assert profile.experience_years == 3


def test_generic_jd_fallback_extracts_cross_role_skills_without_a_knowledge_package():
    profile = _fallback_jd_profile(
        "高级后端工程师\n必须掌握 Python、SQL 与 Docker。\n熟悉 Kubernetes 优先。",
        {},
    )
    assert {"Python", "SQL", "Docker"}.issubset(profile.required_skills)
    assert "Kubernetes" in profile.preferred_skills


def test_markdown_section_heading_is_not_used_as_job_title():
    profile = _fallback_jd_profile(
        "## 工作职责\n- 负责用户研究与需求分析\n## 任职要求\n- 熟悉 Figma",
        {},
    )
    assert profile.title == ""
    assert "工作职责" not in profile.responsibilities


def test_markdown_job_title_is_cleaned_but_preserved():
    profile = _fallback_jd_profile(
        "# Java 后端工程师\n## 工作职责\n- 负责支付系统开发\n## 任职要求\n- 掌握 Java 与 SQL",
        {},
    )
    assert profile.title == "Java 后端工程师"
    assert all(not item.startswith("#") for item in profile.responsibilities)


def test_auto_router_does_not_apply_ai_product_manager_profile_to_other_jobs():
    assert profile_matches_jd("ai_product_manager", "AI 产品经理", "AI 产品经理：负责 RAG 产品规划")
    assert not profile_matches_jd("ai_product_manager", "AI 产品经理", "Java 后端工程师：负责支付系统开发")
    assert not profile_matches_jd("ai_product_manager", "AI 产品经理", "传统消费品产品经理：负责供应链与市场分析")


def test_dynamic_jd_requirements_are_grouped_and_normalized():
    report = score_requirements(
        [
            {"name": "Python", "dimension": "核心技能", "weight": 33.333, "required": False, "status": "matched", "evidence": [{}]},
            {"name": "SQL", "dimension": "核心技能", "weight": 33.333, "required": False, "status": "partial", "evidence": [{}]},
            {"name": "数据管道", "dimension": "职责与场景", "weight": 33.333, "required": False, "status": "unmatched", "evidence": []},
        ]
    )
    assert report["total"] == 50
    assert report["dimensions"] == {"核心技能": 75, "职责与场景": 0}
    assert report["hard_gates"]["passed"] is True


def test_generic_requirements_use_traceable_resume_evidence(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    resume = Resume(
        user_id="test-user",
        original_name="backend.pdf",
        storage_name="backend.pdf",
        content="使用 Python 构建数据服务，负责接口交付。",
    )
    db.add(resume)
    db.flush()
    chunk = ResumeChunk(resume_id=resume.id, user_id=resume.user_id, content=resume.content)
    db.add(chunk)
    db.flush()
    for fact in extract_resume_facts(chunk.content, {"python": "Python"}):
        db.add(
            ResumeFact(
                resume_id=resume.id,
                fact_type=fact.fact_type,
                value=fact.value,
                source_chunk_id=chunk.id,
                source_quote=fact.quote,
                char_start=fact.char_start,
                char_end=fact.char_end,
                strength=fact.strength,
                details=fact.details,
            )
        )
    db.flush()
    monkeypatch.setattr(analysis_service, "embed_query", lambda _: None)

    requirements = _generic_requirements(
        {
            "db": db,
            "resume": resume,
            "jd_profile": {
                "required_skills": ["Python", "SQL"],
                "preferred_skills": [],
                "responsibilities": ["负责数据服务与接口交付"],
                "experience_years": None,
                "education": None,
                "keywords": [],
            },
        },
        [chunk],
    )
    by_name = {item["name"]: item for item in requirements}
    assert by_name["Python"]["status"] == "matched"
    assert by_name["Python"]["evidence"][0]["quote"] in chunk.content
    assert by_name["SQL"]["status"] == "unmatched"
    assert all(item["required"] is False for item in requirements)
    assert round(sum(item["weight"] for item in requirements), 6) == 100
