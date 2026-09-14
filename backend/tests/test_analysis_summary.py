from app.models import Analysis


def test_analysis_total_score_is_derived_from_report():
    analysis = Analysis(
        user_id="user-1",
        resume_id="resume-1",
        job_description="test job description",
        report={"total": 25.4},
    )

    assert analysis.total_score == 25


def test_analysis_total_score_is_absent_without_valid_report():
    assert Analysis(report=None).total_score is None
    assert Analysis(report={"total": "25"}).total_score is None
