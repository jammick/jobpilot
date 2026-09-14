from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base
from app.models import AgentRun
from evals.generator import generate_cases
from evals.runner import _execute, _seed_knowledge


def test_agent_run_records_privacy_safe_metrics():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manifest = Path(__file__).parents[1] / "app" / "seed" / "ai-product-manager-v1.json"
    user, profile = _seed_knowledge(db, manifest)
    settings = get_settings()
    original_key = settings.openai_api_key
    settings.openai_api_key = None
    try:
        _execute(db, user, profile, generate_cases()[0], "observability")
        run = db.query(AgentRun).one()
        assert run.duration_ms is not None
        assert run.duration_ms >= 0
        assert run.metrics["model_calls"] == 0
        assert set(run.metrics["node_durations_ms"]) >= {
            "parsing", "normalizing", "retrieving", "verifying", "scoring", "advising"
        }
        serialized = str(run.metrics) + str(run.trace)
        assert "负责需求分析" not in serialized
        assert run.error_code is None
    finally:
        settings.openai_api_key = original_key
        db.close()
