import pytest
from pydantic import ValidationError

from app.schemas.contracts import OptimizationDraftCreate
from app.services.model_config import masked_api_key


def test_api_key_hint_is_non_reusable():
    secret = "sk-example-secret-1234"

    hint = masked_api_key(secret)

    assert hint == "••••••••1234"
    assert secret not in hint


def test_optimization_draft_requires_analysis():
    with pytest.raises(ValidationError):
        OptimizationDraftCreate.model_validate({})

    payload = OptimizationDraftCreate.model_validate({"analysis_id": "analysis-1"})
    assert payload.analysis_id == "analysis-1"
