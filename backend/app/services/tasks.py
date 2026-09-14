from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from redis import Redis
from rq import Queue
from sqlalchemy import update

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Analysis, EvaluationRun, Resume
from app.services.analysis import run_analysis

logger = logging.getLogger(__name__)


class QueueUnavailableError(RuntimeError):
    """Raised when the durable queue cannot accept a new analysis job."""


def dispatch_analysis(
    analysis_id: str,
    role_profile_id: str | None = None,
    *,
    allow_archived_profile: bool = False,
) -> None:
    """Dispatch an analysis without exposing queue implementation to API routes."""
    settings = get_settings()
    if settings.task_mode.lower() == "inline":
        run_analysis_job(analysis_id, role_profile_id, allow_archived_profile)
        return
    try:
        connection = Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
        connection.ping()
        queue = Queue("jobpilot", connection=connection, default_timeout=settings.analysis_job_timeout_seconds)
        queue.enqueue(
            run_analysis_job,
            analysis_id,
            role_profile_id,
            allow_archived_profile,
            job_id=f"analysis-{analysis_id}-{uuid.uuid4()}",
            result_ttl=3600,
            failure_ttl=86400,
        )
    except Exception as exc:
        logger.warning("analysis queue unavailable analysis_id=%s error_type=%s", analysis_id, type(exc).__name__)
        raise QueueUnavailableError("分析队列暂时不可用，请稍后重试") from exc


def run_analysis_job(
    analysis_id: str,
    role_profile_id: str | None = None,
    allow_archived_profile: bool = False,
) -> None:
    """Claim and execute one job. The atomic claim makes duplicate delivery safe."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        claimed = db.execute(
            update(Analysis)
            .where(Analysis.id == analysis_id, Analysis.status == "queued")
            .values(
                status="running",
                started_at=now,
                finished_at=None,
                attempt_count=Analysis.attempt_count + 1,
                error_message=None,
            )
        ).rowcount
        db.commit()
        if not claimed:
            logger.info("analysis job skipped because it was already claimed analysis_id=%s", analysis_id)
            return

        analysis = db.get(Analysis, analysis_id)
        if not analysis:
            return
        resume = (
            db.query(Resume)
            .filter_by(id=analysis.resume_id, user_id=analysis.user_id)
            .first()
        )
        if not resume:
            analysis.status = "failed"
            analysis.error_message = "关联简历不存在"
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()
            return
        run_analysis(
            db,
            analysis,
            resume,
            role_profile_id or analysis.role_profile_id,
            allow_archived_profile=allow_archived_profile,
        )
    except Exception:
        logger.exception("analysis worker failed analysis_id=%s", analysis_id)
        db.rollback()
        analysis = db.get(Analysis, analysis_id)
        if analysis:
            analysis.status = "failed"
            analysis.error_message = "分析任务执行失败，请稍后重试"
            analysis.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def dispatch_evaluation(evaluation_id: str) -> None:
    settings = get_settings()
    if settings.task_mode.lower() == "inline":
        run_evaluation_job(evaluation_id)
        return
    try:
        connection = Redis.from_url(settings.redis_url, socket_connect_timeout=3, socket_timeout=3)
        connection.ping()
        queue = Queue("jobpilot", connection=connection, default_timeout=max(600, settings.analysis_job_timeout_seconds))
        queue.enqueue(
            run_evaluation_job,
            evaluation_id,
            job_id=f"evaluation-{evaluation_id}-{uuid.uuid4()}",
            result_ttl=3600,
            failure_ttl=86400,
        )
    except Exception as exc:
        logger.warning("evaluation queue unavailable evaluation_id=%s error_type=%s", evaluation_id, type(exc).__name__)
        raise QueueUnavailableError("评测队列暂时不可用，请稍后重试") from exc


def run_evaluation_job(evaluation_id: str) -> None:
    db = SessionLocal()
    try:
        claimed = db.execute(
            update(EvaluationRun)
            .where(EvaluationRun.id == evaluation_id, EvaluationRun.status == "queued")
            .values(status="running", started_at=datetime.now(timezone.utc), error_code=None)
        ).rowcount
        db.commit()
        if not claimed:
            return
        from evals.runner import evaluate_dataset

        summary = evaluate_dataset()
        item = db.get(EvaluationRun, evaluation_id)
        if not item:
            return
        item.dataset_version = summary.dataset_version
        item.metrics = {
            "total_cases": summary.total_cases,
            "passed_cases": summary.passed_cases,
            "score_accuracy": summary.score_accuracy,
            "status_accuracy": summary.status_accuracy,
            "evidence_validity": summary.evidence_validity,
            "deterministic_rate": summary.deterministic_rate,
            "optimization_guard_accuracy": summary.optimization_guard_accuracy,
            "metamorphic_pass_rate": summary.metamorphic_pass_rate,
        }
        item.failures = [
            {"case_id": result.case_id, "errors": result.errors}
            for result in summary.results if not result.passed
        ] + [{"type": "optimization_guard", "error": error} for error in summary.optimization_guard_failures] + [
            {"type": "metamorphic", "error": error} for error in summary.metamorphic_failures
        ]
        item.status = "completed"
        item.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        logger.exception("evaluation worker failed evaluation_id=%s", evaluation_id)
        db.rollback()
        item = db.get(EvaluationRun, evaluation_id)
        if item:
            item.status = "failed"
            item.error_code = "EVALUATION_EXECUTION_FAILED"
            item.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
