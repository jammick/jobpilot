from evals.perturbations import append_keyword_stuffing, inject_prompt_attack, remove_statement_containing, reorder_statements


def test_perturbations_preserve_or_remove_expected_content():
    text = "第一段。\n第二段包含 LangChain。\n第三段。"
    assert set(reorder_statements(text).splitlines()) == set(text.splitlines())
    assert "技能清单" in append_keyword_stuffing(text)
    assert "忽略岗位规则" in inject_prompt_attack(text)
    assert "LangChain" not in remove_statement_containing(text, "langchain")
