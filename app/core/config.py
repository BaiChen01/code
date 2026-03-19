# -*- coding: utf-8 -*-
"""Application configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict


BASE_DIR = Path(__file__).resolve().parents[2]
DOTENV_CANDIDATES = (BASE_DIR / ".env.local", BASE_DIR / ".env")


@dataclass(frozen=True)
class AppConfig:
    llm_api_key: str
    llm_base_url: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_charset: str
    default_sql_limit: int
    default_top_k: int
    embedding_model_name: str
    chroma_jobs_dir: str
    chroma_news_dir: str
    job_collection_name: str
    news_collection_name: str

    @property
    def mysql_uri(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )


@lru_cache(maxsize=1)
def _read_dotenv_values() -> Dict[str, str]:
    values: Dict[str, str] = {}
    for path in DOTENV_CANDIDATES:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def get_env_value(name: str, default: str = "") -> str:
    raw_env = os.getenv(name)
    if raw_env is not None and raw_env.strip():
        return raw_env.strip()
    dotenv_value = _read_dotenv_values().get(name)
    if dotenv_value is not None and dotenv_value.strip():
        return dotenv_value.strip()
    return default


def get_env_source(name: str) -> str:
    raw_env = os.getenv(name)
    if raw_env is not None and raw_env.strip():
        return "process_env"
    dotenv_value = _read_dotenv_values().get(name)
    if dotenv_value is not None and dotenv_value.strip():
        return ".env"
    return "missing"


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    return AppConfig(
        llm_api_key=get_env_value("LLM_API_KEY"),
        llm_base_url=get_env_value("LLM_BASE_URL"),
        mysql_host=get_env_value("MYSQL_HOST", "localhost"),
        mysql_port=int(get_env_value("MYSQL_PORT", "3306")),
        mysql_user=get_env_value("MYSQL_USER", "root"),
        mysql_password=get_env_value("MYSQL_PASSWORD", "123456"),
        mysql_database=get_env_value("MYSQL_DATABASE", "game_intel_system"),
        mysql_charset=get_env_value("MYSQL_CHARSET", "utf8mb4"),
        default_sql_limit=int(get_env_value("DEFAULT_SQL_LIMIT", "200")),
        default_top_k=int(get_env_value("DEFAULT_TOP_K", "5")),
        embedding_model_name=get_env_value(
            "EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"
        ),
        chroma_jobs_dir=get_env_value(
            "CHROMA_JOBS_DIR", str(BASE_DIR / "chroma_jobs")
        ),
        chroma_news_dir=get_env_value(
            "CHROMA_NEWS_DIR", str(BASE_DIR / "chroma_yxrb")
        ),
        job_collection_name=get_env_value("JOB_COLLECTION_NAME", "job_embeddings"),
        news_collection_name=get_env_value(
            "NEWS_COLLECTION_NAME", "game_news_yxrb"
        ),
    )
