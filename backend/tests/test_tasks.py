from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Analysis, EvaluationRun, Resume, User
from app.services import tasks


def test_dispatched_job_ids_are_compatible_with_rq(monkeypatch):
    from types import SimpleNamespace

    captured: list[str] = []

    class FakeRedis:
        def ping(self):
            return True

    class FakeQueue:
        def __init__(self, *_args, **_kwargs):
            pass

        def enqueue(self, *_args, **kwargs):
            captured.append(kwargs["job_id"])

    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: SimpleNamespace(
            task_mode="queue",
            redis_url="redis://redis:6379/0",
            analysis_job_timeout_seconds=300,
        ),
    )
    monkeypatch.setattr(tasks.Redis, "from_url", lambda *_args, **_kwargs: FakeRedis())
    monkeypatch.setattr(tasks, "Queue", FakeQueue)

    tasks.dispatch_analysis("analysis-id")
    tasks.dispatch_evaluation("evaluation-id")

    assert len(captured) == 2
    assert all(":" not in job_id for job_id in captured)
    assert captured[0].startswith("analysis-analysis-id-")
    assert captured[1].startswith("evaluation-evaluation-id-")


def test_analysis_job_is_claimed_only_once(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    user = User(email="queue@example.com", password_hash="test")
    db.add(user)
    db.flush()
    resume = Resume(
        user_id=user.id,
        original_name="resume.pdf",
        storage_name="queue-resume.pdf",
        content="负责 AI 产品需求、RAG 知识库与跨团队交付。",
    )
    db.add(resume)
    db.flush()
    analysis = Analysis(
        user_id=user.id,
        resume_id=resume.id,
        job_description="招聘 AI 产品经理，负责 RAG 产品策略和跨团队交付。",
    )
    db.add(analysis)
    db.commit()
    analysis_id = analysis.id
    calls: list[str] = []

    def fake_run(db_session, item, _resume, *_args, **_kwargs):
        calls.append(item.id)
        item.status = "completed"
        item.report = {"total": 80}
        db_session.commit()

    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(tasks, "run_analysis", fake_run)

    tasks.run_analysis_job(analysis_id)
    tasks.run_analysis_job(analysis_id)

    db.expire_all()
    completed = db.get(Analysis, analysis_id)
    assert completed.status == "completed"
    assert completed.attempt_count == 1
    assert completed.started_at is not None
    assert calls == [analysis_id]


def test_evaluation_job_is_claimed_only_once(monkeypatch):
    from types import SimpleNamespace
    from evals import runner

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    evaluation = EvaluationRun()
    db.add(evaluation)
    db.commit()
    evaluation_id = evaluation.id
    calls: list[str] = []
    summary = SimpleNamespace(
        dataset_version="1.0.0",
        total_cases=20,
        passed_cases=20,
        score_accuracy=1.0,
        status_accuracy=1.0,
        evidence_validity=1.0,
        deterministic_rate=1.0,
        optimization_guard_accuracy=1.0,
        metamorphic_pass_rate=1.0,
        results=[],
        optimization_guard_failures=[],
        metamorphic_failures=[],
    )

    def fake_evaluate():
        calls.append(evaluation_id)
        return summary

    monkeypatch.setattr(tasks, "SessionLocal", factory)
    monkeypatch.setattr(runner, "evaluate_dataset", fake_evaluate)
    tasks.run_evaluation_job(evaluation_id)
    tasks.run_evaluation_job(evaluation_id)

    db.expire_all()
    completed = db.get(EvaluationRun, evaluation_id)
    assert completed.status == "completed"
    assert completed.metrics["passed_cases"] == 20
    assert completed.finished_at is not None
    assert calls == [evaluation_id]
