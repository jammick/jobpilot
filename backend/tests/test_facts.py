from app.services.facts import extract_resume_facts, summarize_facts


ALIASES = {
    "langchain": "RAG",
    "llm": "大语言模型",
    "需求分析": "产品策略",
    "本科": "学历资格",
}


def test_structured_facts_are_exactly_traceable():
    text = (
        "2022.03-2025.06 在星云科技公司担任 AI 产品经理。\n"
        "负责需求分析，基于 LangChain 搭建知识库并设计 LLM 提示词。\n"
        "通过指标复盘使转化率提升 18%。\n"
        "本科学历，具有 3 年产品经验。"
    )
    facts = extract_resume_facts(text, ALIASES)
    assert facts
    assert all(text[fact.char_start:fact.char_end] == fact.quote for fact in facts)
    assert {fact.fact_type for fact in facts} >= {
        "skill", "role", "organization", "experience_years",
        "employment_period", "education", "quantified_outcome",
    }
    summary = summarize_facts(facts)
    assert summary["experience_years"] == 3
    assert summary["quantified_outcomes"]


def test_keyword_list_is_mentioned_not_demonstrated():
    facts = extract_resume_facts("技能清单：LangChain、LLM、需求分析。", ALIASES)
    assert {fact.strength for fact in facts if fact.fact_type == "skill"} == {"mentioned"}


def test_short_ascii_alias_does_not_match_inside_a_url_or_word():
    text = "项目地址：https://github.com/example/Ackermann-Mobile-Robot。"
    facts = extract_resume_facts(text, {"bi": "数据分析", "ai": "人工智能"})
    assert not [fact for fact in facts if fact.fact_type == "skill"]
    assert not [fact for fact in facts if fact.fact_type == "quantified_outcome"]


def test_dotted_technical_name_stays_whole_in_evidence_quote():
    text = "使用 Node.js 实现服务端接口。"
    facts = extract_resume_facts(text, {"node.js": "Node.js"})
    fact = next(item for item in facts if item.fact_type == "skill")
    assert "Node.js" in fact.quote
    assert text[fact.char_start:fact.char_end] == fact.quote
