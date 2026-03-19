# -*- coding: utf-8 -*-
"""SQL validation helpers."""

from __future__ import annotations

import re
from typing import Iterable, Set


ALLOWED_TABLES: Set[str] = {"company", "job_post", "job_text", "vector_mapping"}
BANNED_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "replace",
}


class SQLGuardError(ValueError):
    """Raised when generated SQL fails validation."""


def _normalize_sql(sql: str) -> str:
    sql = (sql or "").strip()
    if not sql:
        raise SQLGuardError("SQL is empty.")
    sql = re.sub(r"\s+", " ", sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def _extract_table_names(sql: str) -> Set[str]:
    table_pattern = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", re.IGNORECASE)
    return {match.group(1).lower() for match in table_pattern.finditer(sql)}


def _has_limit(sql: str) -> bool:
    return bool(re.search(r"\blimit\s+\d+\b", sql, flags=re.IGNORECASE))


def validate_select_sql(
    sql: str,
    *,
    default_limit: int,
    allowed_tables: Iterable[str] = ALLOWED_TABLES,
) -> str:
    normalized = _normalize_sql(sql)
    lowered = normalized.lower()

    if not lowered.startswith("select "):
        raise SQLGuardError("Only SELECT statements are allowed.")

    if ";" in normalized:
        raise SQLGuardError("Multiple SQL statements are not allowed.")

    for keyword in BANNED_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            raise SQLGuardError(f"Forbidden SQL keyword detected: {keyword}")

    table_names = _extract_table_names(normalized)
    allowed = {table.lower() for table in allowed_tables}
    invalid_tables = sorted(table_names - allowed)
    if invalid_tables:
        raise SQLGuardError(
            f"SQL references tables outside the allow-list: {', '.join(invalid_tables)}"
        )

    if not _has_limit(normalized):
        normalized = f"{normalized} LIMIT {int(default_limit)}"

    return normalized
