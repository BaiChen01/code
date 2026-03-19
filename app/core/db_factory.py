# -*- coding: utf-8 -*-
"""Database factory helpers."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.mysql_uri,
        future=True,
        pool_pre_ping=True,
    )
