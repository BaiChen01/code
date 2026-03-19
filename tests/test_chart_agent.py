from __future__ import annotations

from app.agents.chart_agent import ChartAgent


def test_chart_agent_returns_none_when_rows_are_missing() -> None:
    agent = ChartAgent()

    result = agent.run(question="生成图表", sql_result={"rows": []})

    assert result["chart_needed"] is False
    assert result["chart_type"] == "none"
    assert result["chart_option"] == {}


def test_chart_agent_builds_bar_chart_for_comparison_question() -> None:
    agent = ChartAgent()
    sql_result = {
        "rows": [
            {"company_name": "腾讯游戏", "job_count": 10},
            {"company_name": "网易游戏", "job_count": 8},
        ]
    }

    result = agent.run(question="画出各企业岗位数量对比图", sql_result=sql_result)

    assert result["chart_needed"] is True
    assert result["chart_type"] == "bar"
    assert result["x_field"] == "company_name"
    assert result["y_field"] == "job_count"
    assert result["chart_option"]["series"][0]["data"] == [10, 8]
