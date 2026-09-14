from app.services.scoring import score


def test_score_is_explainable_and_bounded():
    report = score("需要 Python、FastAPI 和 3 年经验", "具备 Python FastAPI 开发经验，已有 3 年后端经验")
    assert 0 <= report["total"] <= 100
    assert "Python" in {x.capitalize() for x in report["matched_keywords"]}
    assert set(report["dimensions"]) == {"技能匹配", "经验相关性", "学历与资格", "关键词覆盖"}
