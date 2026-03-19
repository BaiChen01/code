# -*- coding: utf-8 -*-
"""Chart agent for deterministic chart recommendations."""

from __future__ import annotations

from typing import Any, Dict, Optional


def _is_numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class ChartAgent:
    def infer_fields(self, rows: list[dict]) -> tuple[Optional[str], Optional[str]]:
        if not rows:
            return None, None

        sample = rows[0]
        x_field = None
        y_field = None
        for key, value in sample.items():
            if y_field is None and _is_numeric(value):
                y_field = key
            elif x_field is None:
                x_field = key
        return x_field, y_field

    def run(
        self,
        *,
        question: str,
        sql_result: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not sql_result or not sql_result.get("rows"):
            return {
                "chart_needed": False,
                "chart_type": "none",
                "title": None,
                "x_field": None,
                "y_field": None,
                "series_name": None,
                "chart_option": {},
                "chart_summary": "当前没有足够的结构化结果用于绘图。",
            }

        rows = sql_result["rows"]
        x_field, y_field = self.infer_fields(rows)
        if not x_field or not y_field:
            return {
                "chart_needed": False,
                "chart_type": "none",
                "title": None,
                "x_field": None,
                "y_field": None,
                "series_name": None,
                "chart_option": {},
                "chart_summary": "当前结果字段不适合自动生成图表。",
            }

        lowered = question.lower()
        if "占比" in question or "比例" in question:
            chart_type = "pie"
        elif "时间" in question or "趋势" in question or "time" in lowered:
            chart_type = "line"
        else:
            chart_type = "bar"

        series_name = y_field
        title = question if len(question) <= 40 else question[:40]

        if chart_type == "pie":
            chart_option = {
                "series": [
                    {
                        "type": "pie",
                        "data": [
                            {"name": row.get(x_field), "value": row.get(y_field)}
                            for row in rows
                        ],
                    }
                ]
            }
        else:
            chart_option = {
                "xAxis": {"type": "category", "data": [row.get(x_field) for row in rows]},
                "yAxis": {"type": "value"},
                "series": [
                    {
                        "type": chart_type,
                        "name": series_name,
                        "data": [row.get(y_field) for row in rows],
                    }
                ],
            }

        return {
            "chart_needed": True,
            "chart_type": chart_type,
            "title": title,
            "x_field": x_field,
            "y_field": y_field,
            "series_name": series_name,
            "chart_option": chart_option,
            "chart_summary": f"使用 {chart_type} 图展示字段 {x_field} 与 {y_field} 的关系。",
        }
