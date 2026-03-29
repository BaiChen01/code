# -*- coding: utf-8 -*-
"""Session memory persistence and summary helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db_factory import get_engine
from app.core.llm_factory import get_llm
from app.core.model_config import (
    MEMORY_SUMMARY_MAX_TOKENS,
    MEMORY_SUMMARY_MODEL,
    MEMORY_SUMMARY_TEMPERATURE,
    MEMORY_SUMMARY_TOP_P,
)
from app.prompts.memory_prompt import get_memory_summary_prompt_template


def _clip_text(value: str, max_length: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


def _format_timestamp(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _render_message_line(message: Dict[str, Any]) -> str:
    role = str(message.get("role") or "unknown").lower()
    role_label = "User" if role == "user" else "Assistant" if role == "assistant" else role
    return f"{role_label}: {_clip_text(message.get('content', ''), 280)}"


class MemoryService:
    """Persists chat turns and produces a compact reusable session summary."""

    def __init__(self, engine: Optional[Engine] = None) -> None:
        settings = get_settings()
        self.engine = engine or get_engine()
        self.recent_message_limit = settings.memory_recent_message_limit
        self.summary_trigger_messages = settings.memory_summary_trigger_messages
        self.summary_refresh_stride = settings.memory_summary_refresh_stride
        self.summary_window_messages = settings.memory_summary_window_messages
        self.summary_llm = get_llm(
            model=MEMORY_SUMMARY_MODEL,
            temperature=MEMORY_SUMMARY_TEMPERATURE,
            max_tokens=MEMORY_SUMMARY_MAX_TOKENS,
            top_p=MEMORY_SUMMARY_TOP_P,
        )
        self.summary_prompt_template = get_memory_summary_prompt_template()
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return

        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS chat_session (
                session_id VARCHAR(80) PRIMARY KEY,
                session_summary TEXT NULL,
                summary_message_count INT NOT NULL DEFAULT 0,
                last_question TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
                summary_updated_at TIMESTAMP NULL DEFAULT NULL
            ) CHARACTER SET utf8mb4
            """.strip(),
            """
            CREATE TABLE IF NOT EXISTS chat_message (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(80) NOT NULL,
                role VARCHAR(20) NOT NULL,
                content TEXT NOT NULL,
                payload_json LONGTEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_chat_message_session_id (session_id, id),
                CONSTRAINT fk_chat_message_session
                    FOREIGN KEY (session_id) REFERENCES chat_session(session_id)
                    ON DELETE CASCADE
            ) CHARACTER SET utf8mb4
            """.strip(),
        ]

        with self.engine.begin() as connection:
            for statement in ddl_statements:
                connection.exec_driver_sql(statement)
        self._schema_ready = True

    def _ensure_session(self, session_id: str) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO chat_session (session_id)
                VALUES (%s)
                ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
                """.strip(),
                (session_id,),
            )

    def _serialize_payload(self, payload: Optional[Dict[str, Any]]) -> Optional[str]:
        if not payload:
            return None
        compact_payload = {
            "intent_type": payload.get("intent_type"),
            "error_message": payload.get("error_message"),
            "trace": payload.get("trace"),
            "sql_summary": (payload.get("sql_result") or {}).get("summary"),
            "chart_type": (payload.get("chart_result") or {}).get("chart_type"),
            "retrieved_doc_count": (payload.get("retrieved_docs") or {}).get("total_count", 0),
        }
        return json.dumps(compact_payload, ensure_ascii=False)

    def _fetch_session_row(self, session_id: str) -> Dict[str, Any]:
        with self.engine.connect() as connection:
            row = connection.exec_driver_sql(
                """
                SELECT
                    session_id,
                    session_summary,
                    summary_message_count,
                    created_at,
                    updated_at,
                    summary_updated_at
                FROM chat_session
                WHERE session_id = %s
                """.strip(),
                (session_id,),
            ).mappings().first()
        return dict(row) if row else {}

    def _fetch_recent_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        message_limit = limit or self.recent_message_limit
        with self.engine.connect() as connection:
            rows = connection.exec_driver_sql(
                """
                SELECT id, role, content, created_at
                FROM chat_message
                WHERE session_id = %s
                ORDER BY id DESC
                LIMIT %s
                """.strip(),
                (session_id, message_limit),
            ).mappings().all()

        messages = []
        for row in reversed(rows):
            messages.append(
                {
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "created_at": _format_timestamp(row["created_at"]),
                }
            )
        return messages

    def _count_messages(self, session_id: str) -> int:
        with self.engine.connect() as connection:
            value = connection.exec_driver_sql(
                "SELECT COUNT(*) AS message_count FROM chat_message WHERE session_id = %s",
                (session_id,),
            ).scalar_one()
        return int(value or 0)

    def _build_memory_context(
        self,
        *,
        session_summary: str,
        recent_messages: List[Dict[str, Any]],
    ) -> str:
        blocks: list[str] = []
        if session_summary:
            blocks.append(f"Session summary:\n{session_summary}")
        if recent_messages:
            rendered_messages = "\n".join(_render_message_line(message) for message in recent_messages)
            blocks.append(f"Recent conversation:\n{rendered_messages}")
        return "\n\n".join(blocks).strip()

    def _fallback_summary(
        self,
        *,
        existing_summary: str,
        messages: List[Dict[str, Any]],
    ) -> str:
        user_questions = [
            _clip_text(message.get("content", ""), 90)
            for message in messages
            if message.get("role") == "user"
        ]
        assistant_answers = [
            _clip_text(message.get("content", ""), 90)
            for message in messages
            if message.get("role") == "assistant"
        ]

        parts: list[str] = []
        if existing_summary:
            parts.append(f"Existing summary: {_clip_text(existing_summary, 180)}")
        if user_questions:
            parts.append("Recent user focus: " + " | ".join(user_questions[-3:]))
        if assistant_answers:
            parts.append("Latest assistant output: " + assistant_answers[-1])

        return "\n".join(parts).strip() or "Session started, but no durable summary is available yet."

    def _summarize_session(
        self,
        *,
        existing_summary: str,
        messages: List[Dict[str, Any]],
    ) -> str:
        rendered_messages = "\n".join(_render_message_line(message) for message in messages)
        try:
            payload = self.summary_llm.invoke_json(
                self.summary_prompt_template,
                {
                    "existing_summary": existing_summary or "N/A",
                    "recent_messages": rendered_messages or "N/A",
                },
            )
            summary = str(payload.get("summary") or "").strip()
            if summary:
                return summary
        except Exception:
            pass
        return self._fallback_summary(existing_summary=existing_summary, messages=messages)

    def load_session_memory(self, session_id: str) -> Dict[str, Any]:
        try:
            self._ensure_schema()
            self._ensure_session(session_id)
            session_row = self._fetch_session_row(session_id)
            recent_messages = self._fetch_recent_messages(session_id)
            session_summary = str(session_row.get("session_summary") or "").strip()
            return {
                "session_id": session_id,
                "recent_messages": recent_messages,
                "session_summary": session_summary,
                "memory_context": self._build_memory_context(
                    session_summary=session_summary,
                    recent_messages=recent_messages,
                ),
                "summary_updated_at": _format_timestamp(session_row.get("summary_updated_at")),
                "message_count": self._count_messages(session_id),
                "error": None,
            }
        except SQLAlchemyError as exc:
            return {
                "session_id": session_id,
                "recent_messages": [],
                "session_summary": "",
                "memory_context": "",
                "summary_updated_at": None,
                "message_count": 0,
                "error": str(exc),
            }

    def persist_turn(
        self,
        *,
        session_id: str,
        user_question: str,
        assistant_answer: str,
        assistant_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        summary_updated = False
        try:
            self._ensure_schema()
            self._ensure_session(session_id)
            serialized_payload = self._serialize_payload(assistant_payload)

            with self.engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    INSERT INTO chat_message (session_id, role, content, payload_json)
                    VALUES (%s, %s, %s, %s)
                    """.strip(),
                    (session_id, "user", user_question, None),
                )
                connection.exec_driver_sql(
                    """
                    INSERT INTO chat_message (session_id, role, content, payload_json)
                    VALUES (%s, %s, %s, %s)
                    """.strip(),
                    (session_id, "assistant", assistant_answer, serialized_payload),
                )
                connection.exec_driver_sql(
                    """
                    UPDATE chat_session
                    SET last_question = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s
                    """.strip(),
                    (user_question, session_id),
                )

            session_row = self._fetch_session_row(session_id)
            message_count = self._count_messages(session_id)
            summary_message_count = int(session_row.get("summary_message_count") or 0)
            should_refresh_summary = message_count >= self.summary_trigger_messages and (
                not str(session_row.get("session_summary") or "").strip()
                or message_count - summary_message_count >= self.summary_refresh_stride
            )

            if should_refresh_summary:
                summary_messages = self._fetch_recent_messages(
                    session_id,
                    limit=self.summary_window_messages,
                )
                new_summary = self._summarize_session(
                    existing_summary=str(session_row.get("session_summary") or "").strip(),
                    messages=summary_messages,
                )
                with self.engine.begin() as connection:
                    connection.exec_driver_sql(
                        """
                        UPDATE chat_session
                        SET
                            session_summary = %s,
                            summary_message_count = %s,
                            summary_updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s
                        """.strip(),
                        (new_summary, message_count, session_id),
                    )
                summary_updated = True

            bundle = self.load_session_memory(session_id)
            bundle["summary_updated"] = summary_updated
            return bundle
        except SQLAlchemyError as exc:
            return {
                "session_id": session_id,
                "recent_messages": [],
                "session_summary": "",
                "memory_context": "",
                "summary_updated_at": None,
                "message_count": 0,
                "summary_updated": False,
                "error": str(exc),
            }
