from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class RegisterInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginInput(RegisterInput):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr


class ResumeResponse(BaseModel):
    id: str
    original_name: str
    created_at: datetime


class ResumeDetailResponse(ResumeResponse):
    content: str
    file_type: Literal["pdf", "docx"]


class BatchResumeResponse(BaseModel):
    imported: list[ResumeResponse]
    rejected: list[dict[str, str]]


class ResumeOptimizationResponse(BaseModel):
    headline: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    improvements: list[str] = Field(min_length=1, max_length=8)
    optimized_markdown: str = Field(min_length=1, max_length=30000)


class OptimizationChangeOutput(BaseModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    original_text: str = Field(min_length=1, max_length=2000)
    suggested_text: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=800)
    evidence_quote: str = Field(min_length=1, max_length=2000)
    decision: Literal["pending", "accepted", "rejected"] = "pending"


class OptimizationDraftResponse(ResumeOptimizationResponse):
    id: str
    status: str
    changes: list[OptimizationChangeOutput] = Field(default_factory=list)


class OptimizationDraftCreate(BaseModel):
    analysis_id: str


class ChangeDecisionInput(BaseModel):
    decision: Literal["accepted", "rejected"]


class AnalysisCreate(BaseModel):
    resume_id: str
    job_description: str = Field(min_length=30, max_length=15000)
    role_profile_id: str | None = None


class AnalysisSummary(BaseModel):
    id: str
    resume_id: str
    status: str
    total_score: int | None = None
    error_message: str | None = None
    attempt_count: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class AnalysisDetail(AnalysisSummary):
    report: dict | None = None


class ModelSettingsResponse(BaseModel):
    base_url: str | None = None
    chat_model: str
    api_key_configured: bool
    api_key_hint: str | None = None


class ModelSettingsUpdate(BaseModel):
    api_key: str | None = Field(default=None, min_length=1)
    base_url: str | None = Field(default=None, max_length=500)
    chat_model: str = Field(min_length=1, max_length=120)


class KnowledgeSourceInput(BaseModel):
    """Versioned provenance for a knowledge package or individual rule."""
    id: str = Field(pattern=r"^[a-z0-9_\-]{2,60}$")
    name: str = Field(min_length=1, max_length=160)
    url: str = Field(min_length=8, max_length=500)
    license: str = Field(default="review required", max_length=120)
    note: str = Field(default="", max_length=500)


class KnowledgeSkillInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    category: str = Field(default="general", max_length=80)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class CompetencyRuleInput(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_\-]{2,100}$")
    name: str = Field(min_length=1, max_length=160)
    weight: float = Field(gt=0, le=100)
    required: bool = False
    skills: list[str] = Field(min_length=1, max_length=12)
    description: str = Field(default="", max_length=2000)
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class KnowledgeManifestInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    role_key: str = Field(default="ai_product_manager", pattern=r"^[a-z0-9_\-]{2,80}$")
    version: str = Field(min_length=1, max_length=60)
    role_name: str = Field(default="AI 产品经理", max_length=160)
    sources: list[KnowledgeSourceInput] = Field(default_factory=list, max_length=20)
    skills: list[KnowledgeSkillInput] = Field(min_length=1, max_length=100)
    rules: list[CompetencyRuleInput] = Field(min_length=1, max_length=20)

    @field_validator("rules")
    @classmethod
    def weights_total_one_hundred(cls, rules: list[CompetencyRuleInput]):
        if round(sum(rule.weight for rule in rules), 3) != 100:
            raise ValueError("规则权重之和必须为 100")
        return rules

    @model_validator(mode="after")
    def source_references_exist(self):
        known = {source.id for source in self.sources}
        for item in [*self.skills, *self.rules]:
            unknown = set(item.source_ids) - known
            if unknown:
                raise ValueError(f"来源引用不存在：{', '.join(sorted(unknown))}")
        return self


class KnowledgeBaseSummary(BaseModel):
    id: str
    name: str
    role_key: str
    version: str
    status: str
    embedding_model: str
    created_at: datetime


class KnowledgeBaseDetail(KnowledgeBaseSummary):
    manifest: dict
    document_count: int = 0
    validation: list[str] = Field(default_factory=list)


class KnowledgeSearchInput(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)
