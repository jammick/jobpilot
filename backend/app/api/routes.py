import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DB, KnowledgeAdmin
from app.core.config import get_settings
from app.core.security import create_token, hash_password, verify_password
from app.models import AgentRun, Analysis, EvaluationRun, KnowledgeBase, KnowledgeChunk, KnowledgeDocument, OptimizationChange, OptimizationDraft, Resume, ResumeChunk, ResumeVersion, RoleProfile, User
from app.schemas.contracts import AnalysisCreate, AnalysisDetail, AnalysisSummary, BatchResumeResponse, ChangeDecisionInput, KnowledgeBaseDetail, KnowledgeBaseSummary, KnowledgeSearchInput, LoginInput, ModelSettingsResponse, ModelSettingsUpdate, OptimizationDraftCreate, OptimizationDraftResponse, RegisterInput, ResumeDetailResponse, ResumeOptimizationResponse, ResumeResponse, TokenResponse, UserResponse
from app.services.analysis import index_resume
from app.services.documents import save_and_extract
from app.services.knowledge import detail as knowledge_detail, import_knowledge_base, publish_knowledge_base, search_knowledge_chunks
from app.services.optimization import create_optimization_draft, publish_draft
from app.services.model_config import masked_api_key, save_user_llm_config, user_llm_config
from app.services.tasks import QueueUnavailableError, dispatch_analysis, dispatch_evaluation

router = APIRouter()


@router.get("/developer/status")
def developer_status(db: DB, _: KnowledgeAdmin):
    settings = get_settings()
    dialect = db.get_bind().dialect.name
    return {"database": dialect, "vector_database": dialect == "postgresql", "embedding_model": settings.embedding_model, "embedding_configured": bool(settings.openai_api_key), "task_mode": settings.task_mode, "queue_configured": settings.task_mode.lower() == "queue"}


@router.get("/developer/observability")
def developer_observability(db: DB, _: KnowledgeAdmin):
    runs = db.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(200).all()
    durations = [run.duration_ms for run in runs if run.duration_ms is not None]
    successful = [run for run in runs if run.status in {"completed", "needs_review"}]
    metrics = [run.metrics or {} for run in runs]
    node_values: dict[str, list[int]] = {}
    for item in metrics:
        for node, duration in item.get("node_durations_ms", {}).items():
            node_values.setdefault(node, []).append(int(duration or 0))
    return {
        "total_runs": len(runs),
        "success_rate": round(len(successful) / max(1, len(runs)), 4),
        "failed_runs": sum(run.status == "failed" for run in runs),
        "needs_review_runs": sum(run.status == "needs_review" for run in runs),
        "average_duration_ms": round(sum(durations) / max(1, len(durations))),
        "model_calls": sum(int(item.get("model_calls", 0)) for item in metrics),
        "input_tokens": sum(int(item.get("input_tokens", 0)) for item in metrics),
        "output_tokens": sum(int(item.get("output_tokens", 0)) for item in metrics),
        "estimated_cost_usd": round(sum(float(item.get("estimated_cost_usd", 0)) for item in metrics), 6),
        "average_node_duration_ms": {
            node: round(sum(values) / max(1, len(values))) for node, values in node_values.items()
        },
        "recent_runs": [
            {
                "id": run.id,
                "analysis_id": run.analysis_id,
                "status": run.status,
                "duration_ms": run.duration_ms,
                "metrics": run.metrics or {},
                "error_code": run.error_code,
                "created_at": run.created_at,
                "trace": run.trace or [],
            }
            for run in runs[:20]
        ],
    }


@router.get("/developer/evaluations")
def developer_evaluations(db: DB, _: KnowledgeAdmin):
    return db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(20).all()


@router.post("/developer/evaluations", status_code=201)
def create_developer_evaluation(db: DB, _: KnowledgeAdmin):
    evaluation = EvaluationRun(status="queued", dataset_version="ai-product-manager-v1")
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    try:
        dispatch_evaluation(evaluation.id)
    except QueueUnavailableError as exc:
        evaluation.status = "failed"
        evaluation.error_code = "EVALUATION_QUEUE_UNAVAILABLE"
        db.commit()
        raise HTTPException(503, str(exc)) from exc
    db.expire_all()
    return db.get(EvaluationRun, evaluation.id)


@router.get("/settings/model", response_model=ModelSettingsResponse)
def model_settings(user: CurrentUser, db: DB):
    config = user_llm_config(db, user.id)
    return {"base_url": config.base_url, "chat_model": config.chat_model, "api_key_configured": bool(config.api_key), "api_key_hint": masked_api_key(config.api_key)}


@router.put("/settings/model", response_model=ModelSettingsResponse)
def update_model_settings(payload: ModelSettingsUpdate, user: CurrentUser, db: DB):
    """Persist the user's chat model; only a non-reusable key hint is returned."""
    config = save_user_llm_config(
        db,
        user.id,
        api_key=payload.api_key,
        base_url=payload.base_url or None,
        chat_model=payload.chat_model,
    )
    return {"base_url": config.base_url, "chat_model": config.chat_model, "api_key_configured": bool(config.api_key), "api_key_hint": masked_api_key(config.api_key)}


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseSummary])
def knowledge_bases(user: CurrentUser, db: DB, _: KnowledgeAdmin):
    return db.query(KnowledgeBase).filter_by(user_id=user.id).order_by(KnowledgeBase.created_at.desc()).all()


@router.get("/role-profiles")
def role_profiles(user: CurrentUser, db: DB):
    """Return only safe, published role-model metadata to product users.

    Knowledge documents, rules, weights and developer controls remain behind
    the knowledge-admin dependency.
    """
    rows = db.query(RoleProfile, KnowledgeBase).join(KnowledgeBase, RoleProfile.knowledge_base_id == KnowledgeBase.id).filter(KnowledgeBase.user_id == user.id, KnowledgeBase.status == "published").order_by(KnowledgeBase.created_at.desc()).all()
    return [{"id": profile.id, "name": profile.name, "role_key": profile.role_key, "knowledge_base_id": base.id, "version": base.version} for profile, base in rows]


@router.get("/knowledge-bases/{base_id}", response_model=KnowledgeBaseDetail)
def knowledge_base(base_id: str, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    base = db.query(KnowledgeBase).filter_by(id=base_id, user_id=user.id).first()
    if not base:
        raise HTTPException(404, "知识包不存在")
    count = db.query(func.count(KnowledgeDocument.id)).filter_by(knowledge_base_id=base.id).scalar() or 0
    return knowledge_detail(base, count)


@router.get("/knowledge-bases/{base_id}/insights")
def knowledge_insights(base_id: str, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    base = db.query(KnowledgeBase).filter_by(id=base_id, user_id=user.id).first()
    if not base:
        raise HTTPException(404, "知识包不存在")
    chunks = db.query(KnowledgeChunk).filter_by(knowledge_base_id=base.id).all()
    vectors = [chunk.embedding for chunk in chunks if chunk.embedding is not None]
    return {"knowledge_base_id": base.id, "documents": db.query(func.count(KnowledgeDocument.id)).filter_by(knowledge_base_id=base.id).scalar() or 0, "chunks": len(chunks), "vectors": len(vectors), "dimension": len(vectors[0]) if vectors else None, "sample_chunks": [{"id": chunk.id, "content": chunk.content[:300], "vector_indexed": chunk.embedding is not None} for chunk in chunks[:5]]}


@router.post("/knowledge-bases/{base_id}/search")
def search_knowledge(base_id: str, payload: KnowledgeSearchInput, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    base = db.query(KnowledgeBase).filter_by(id=base_id, user_id=user.id).first()
    if not base:
        raise HTTPException(404, "知识包不存在")
    mode, results = search_knowledge_chunks(db, base.id, payload.query, payload.limit)
    return {"mode": mode, "results": results}


@router.post("/knowledge-bases/import", response_model=KnowledgeBaseDetail, status_code=201)
async def import_base(manifest: UploadFile, user: CurrentUser, db: DB, _: KnowledgeAdmin, documents: list[UploadFile] | None = None):
    base = await import_knowledge_base(db, user.id, manifest, documents or [])
    count = db.query(func.count(KnowledgeDocument.id)).filter_by(knowledge_base_id=base.id).scalar() or 0
    return knowledge_detail(base, count)


@router.post("/knowledge-bases/{base_id}/validate", response_model=KnowledgeBaseDetail)
def validate_base(base_id: str, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    base = db.query(KnowledgeBase).filter_by(id=base_id, user_id=user.id).first()
    if not base:
        raise HTTPException(404, "知识包不存在")
    count = db.query(func.count(KnowledgeDocument.id)).filter_by(knowledge_base_id=base.id).scalar() or 0
    return knowledge_detail(base, count)


@router.post("/knowledge-bases/{base_id}/publish", response_model=KnowledgeBaseDetail)
def publish_base(base_id: str, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    base = db.query(KnowledgeBase).filter_by(id=base_id, user_id=user.id).first()
    if not base:
        raise HTTPException(404, "知识包不存在")
    base = publish_knowledge_base(db, user.id, base)
    count = db.query(func.count(KnowledgeDocument.id)).filter_by(knowledge_base_id=base.id).scalar() or 0
    return knowledge_detail(base, count)


@router.post("/knowledge-bases/{base_id}/rollback", response_model=KnowledgeBaseDetail)
def rollback_base(base_id: str, user: CurrentUser, db: DB, _: KnowledgeAdmin):
    return publish_base(base_id, user, db, _)


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterInput, db: DB):
    if db.query(User).filter_by(email=payload.email.lower()).first():
        raise HTTPException(409, "该邮箱已注册")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_token(user.id)}


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginInput, db: DB):
    user = db.query(User).filter_by(email=payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "邮箱或密码错误")
    return {"access_token": create_token(user.id)}


@router.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser): return user


@router.post("/resumes", response_model=ResumeResponse, status_code=201)
async def upload_resume(file: UploadFile, user: CurrentUser, db: DB):
    storage_name, content = await save_and_extract(file)
    resume = Resume(user_id=user.id, original_name=file.filename or "resume", storage_name=storage_name, content=content)
    db.add(resume); db.flush(); index_resume(db, resume); db.commit(); db.refresh(resume)
    return resume


@router.post("/resumes/batch", response_model=BatchResumeResponse, status_code=201)
async def upload_resumes(files: list[UploadFile], user: CurrentUser, db: DB):
    if not files or len(files) > 10:
        raise HTTPException(400, "每次请选择 1 到 10 份简历")
    imported, rejected = [], []
    for file in files:
        try:
            storage_name, content = await save_and_extract(file)
            resume = Resume(user_id=user.id, original_name=file.filename or "resume", storage_name=storage_name, content=content)
            db.add(resume); db.flush(); index_resume(db, resume); db.commit(); db.refresh(resume)
            imported.append(resume)
        except HTTPException as exc:
            db.rollback()
            rejected.append({"file_name": file.filename or "unknown", "reason": str(exc.detail)})
        except Exception:
            db.rollback()
            rejected.append({"file_name": file.filename or "unknown", "reason": "导入失败，请稍后重试"})
    return {"imported": imported, "rejected": rejected}


@router.get("/resumes", response_model=list[ResumeResponse])
def resumes(user: CurrentUser, db: DB):
    return db.query(Resume).filter_by(user_id=user.id).order_by(Resume.created_at.desc()).all()


def owned_resume(resume_id: str, user: User, db: Session) -> Resume:
    resume = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not resume:
        raise HTTPException(404, "简历不存在")
    return resume


@router.get("/resumes/{resume_id}", response_model=ResumeDetailResponse)
def resume_detail(resume_id: str, user: CurrentUser, db: DB):
    resume = owned_resume(resume_id, user, db)
    suffix = Path(resume.original_name).suffix.lower().lstrip(".")
    return {
        "id": resume.id,
        "original_name": resume.original_name,
        "created_at": resume.created_at,
        "content": resume.content,
        "file_type": suffix,
    }


@router.get("/resumes/{resume_id}/file")
def resume_file(resume_id: str, user: CurrentUser, db: DB):
    resume = owned_resume(resume_id, user, db)
    path = get_settings().upload_dir / resume.storage_name
    if not path.is_file():
        raise HTTPException(404, "简历源文件不存在")
    media_type = (
        "application/pdf"
        if Path(resume.original_name).suffix.lower() == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=resume.original_name,
        content_disposition_type="inline",
    )


@router.post("/resumes/{resume_id}/optimize", response_model=ResumeOptimizationResponse)
def optimize_owned_resume(resume_id: str, user: CurrentUser, db: DB):
    owned_resume(resume_id, user, db)
    raise HTTPException(409, "简历优化必须关联一份已完成的岗位分析，请先选择简历并填写岗位 JD")


def draft_payload(db: Session, draft: OptimizationDraft) -> dict:
    changes = db.query(OptimizationChange).filter_by(draft_id=draft.id).all()
    return {"id": draft.id, "status": draft.status, "headline": draft.headline, "summary": draft.summary, "improvements": [change.rationale for change in changes], "optimized_markdown": draft.optimized_markdown, "changes": [{"title": change.title, "original_text": change.original_text, "suggested_text": change.suggested_text, "rationale": change.rationale, "evidence_quote": change.evidence_quote, "decision": change.decision, "id": change.id} for change in changes]}


@router.post("/resumes/{resume_id}/optimizations", response_model=OptimizationDraftResponse, status_code=201)
def create_draft(resume_id: str, payload: OptimizationDraftCreate, user: CurrentUser, db: DB):
    resume = owned_resume(resume_id, user, db)
    analysis = db.query(Analysis).filter_by(id=payload.analysis_id, user_id=user.id, resume_id=resume.id).first()
    if not analysis:
        raise HTTPException(404, "关联分析不存在")
    if analysis.status not in {"completed", "needs_review"} or not analysis.report:
        raise HTTPException(409, "岗位分析尚未完成，暂时不能生成定向优化草稿")
    return draft_payload(db, create_optimization_draft(db, resume, analysis))


@router.get("/optimizations/{draft_id}", response_model=OptimizationDraftResponse)
def get_draft(draft_id: str, user: CurrentUser, db: DB):
    draft = db.query(OptimizationDraft).filter_by(id=draft_id, user_id=user.id).first()
    if not draft:
        raise HTTPException(404, "优化草稿不存在")
    return draft_payload(db, draft)


@router.post("/optimizations/{draft_id}/changes/{change_id}/decision", response_model=OptimizationDraftResponse)
def decide_change(draft_id: str, change_id: str, payload: ChangeDecisionInput, user: CurrentUser, db: DB):
    draft = db.query(OptimizationDraft).filter_by(id=draft_id, user_id=user.id, status="draft").first()
    if not draft:
        raise HTTPException(404, "优化草稿不存在或已发布")
    change = db.query(OptimizationChange).filter_by(id=change_id, draft_id=draft.id).first()
    if not change:
        raise HTTPException(404, "修改项不存在")
    change.decision = payload.decision
    db.commit()
    return draft_payload(db, draft)


@router.post("/optimizations/{draft_id}/publish")
def publish_optimization(draft_id: str, user: CurrentUser, db: DB):
    draft = db.query(OptimizationDraft).filter_by(id=draft_id, user_id=user.id, status="draft").first()
    if not draft:
        raise HTTPException(404, "优化草稿不存在或已发布")
    version = publish_draft(db, draft)
    return {"id": version.id, "resume_id": version.resume_id, "label": version.label, "markdown": version.markdown, "created_at": version.created_at}


@router.get("/resumes/{resume_id}/versions")
def resume_versions(resume_id: str, user: CurrentUser, db: DB):
    if not db.query(Resume).filter_by(id=resume_id, user_id=user.id).first():
        raise HTTPException(404, "简历不存在")
    return db.query(ResumeVersion).filter_by(resume_id=resume_id).order_by(ResumeVersion.created_at.desc()).all()


@router.delete("/resumes/{resume_id}", status_code=204)
def delete_resume(resume_id: str, user: CurrentUser, db: DB):
    resume = db.query(Resume).filter_by(id=resume_id, user_id=user.id).first()
    if not resume: raise HTTPException(404, "简历不存在")
    if db.query(Analysis).filter_by(resume_id=resume.id, user_id=user.id, status="running").first():
        raise HTTPException(409, "该简历仍有分析正在执行，请等待完成后再删除")
    db.query(ResumeChunk).filter_by(resume_id=resume.id, user_id=user.id).delete()
    path = get_settings().upload_dir / resume.storage_name
    if path.exists(): os.remove(path)
    db.delete(resume); db.commit()
    return Response(status_code=204)


@router.post("/analyses", response_model=AnalysisDetail, status_code=201)
def create_analysis(payload: AnalysisCreate, user: CurrentUser, db: DB):
    resume = db.query(Resume).filter_by(id=payload.resume_id, user_id=user.id).first()
    if not resume: raise HTTPException(404, "简历不存在")
    if payload.role_profile_id:
        valid_profile = db.query(RoleProfile).join(KnowledgeBase, RoleProfile.knowledge_base_id == KnowledgeBase.id).filter(RoleProfile.id == payload.role_profile_id, KnowledgeBase.user_id == user.id, KnowledgeBase.status == "published").first()
        if not valid_profile:
            raise HTTPException(422, "目标岗位能力模型不存在或尚未发布")
    analysis = Analysis(user_id=user.id, resume_id=resume.id, role_profile_id=payload.role_profile_id, job_description=payload.job_description)
    db.add(analysis); db.commit(); db.refresh(analysis)
    try:
        dispatch_analysis(analysis.id, payload.role_profile_id)
    except QueueUnavailableError as exc:
        analysis.status = "failed"
        analysis.error_message = str(exc)
        db.commit()
        db.refresh(analysis)
        return analysis
    db.expire_all()
    analysis = owned_analysis(analysis.id, user, db)
    return analysis


@router.get("/analyses", response_model=list[AnalysisSummary])
def analyses(user: CurrentUser, db: DB):
    return db.query(Analysis).filter_by(user_id=user.id).order_by(Analysis.created_at.desc()).all()


def owned_analysis(analysis_id: str, user: User, db: Session) -> Analysis:
    result = db.query(Analysis).filter_by(id=analysis_id, user_id=user.id).first()
    if not result: raise HTTPException(404, "分析记录不存在")
    return result


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def analysis_detail(analysis_id: str, user: CurrentUser, db: DB): return owned_analysis(analysis_id, user, db)


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str, user: CurrentUser, db: DB):
    item = owned_analysis(analysis_id, user, db)
    if item.status == "running":
        raise HTTPException(409, "分析正在执行，请等待完成后再删除")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/analyses/{analysis_id}/retry", response_model=AnalysisDetail)
def retry_analysis(analysis_id: str, user: CurrentUser, db: DB):
    item = owned_analysis(analysis_id, user, db)
    resume = db.query(Resume).filter_by(id=item.resume_id, user_id=user.id).first()
    if not resume:
        raise HTTPException(404, "关联简历不存在")
    if item.status == "running" and item.started_at:
        started_at = item.started_at if item.started_at.tzinfo else item.started_at.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        if elapsed < get_settings().analysis_job_timeout_seconds:
            raise HTTPException(409, "分析任务正在执行，无需重复提交")
    if item.status != "queued":
        item.status = "queued"
        item.error_message = None
        item.report = None
        item.finished_at = None
        db.commit()
    try:
        dispatch_analysis(item.id, item.role_profile_id, allow_archived_profile=bool(item.role_profile_id))
    except QueueUnavailableError as exc:
        item.status = "failed"
        item.error_message = str(exc)
        db.commit()
        raise HTTPException(503, str(exc)) from exc
    db.expire_all()
    item = owned_analysis(item.id, user, db)
    return item


@router.get("/analyses/{analysis_id}/trace")
def analysis_trace(analysis_id: str, user: CurrentUser, db: DB):
    item = owned_analysis(analysis_id, user, db)
    run = db.query(AgentRun).filter_by(analysis_id=item.id).order_by(AgentRun.created_at.desc()).first()
    return {"analysis_id": item.id, "status": item.status, "trace": run.trace if run else []}


@router.get("/analyses/{analysis_id}/export")
def export_analysis(analysis_id: str, user: CurrentUser, db: DB):
    item = owned_analysis(analysis_id, user, db)
    if item.status not in {"completed", "needs_review"} or not item.report: raise HTTPException(409, "报告尚未生成")
    r = item.report
    lines = ["# JobPilot 岗位匹配报告", f"\n## 综合匹配度\n{r['total']} / 100", "\n## 维度评分"]
    lines += [f"- {k}：{v}" for k,v in r["dimensions"].items()]
    lines += ["\n## 技能缺口"] + [f"- {x}" for x in r.get("missing_keywords", [])]
    lines += ["\n## 优化建议"] + [f"- {x}" for x in r.get("improvements", [])]
    lines += ["\n## 面试问题"] + [f"- {x}" for x in r.get("interview_questions", [])]
    return Response("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="jobpilot-report.md"'})
