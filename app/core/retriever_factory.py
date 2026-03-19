# -*- coding: utf-8 -*-
"""Factory helpers for Chroma-backed retrievers."""

from __future__ import annotations

from functools import lru_cache

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

from app.core.config import get_settings
from app.core.logger import get_logger


logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_function():
    settings = get_settings()
    try:
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model_name,
            local_files_only=True,
        )
    except Exception as exc:
        logger.warning(
            "Falling back to DefaultEmbeddingFunction because the local sentence-transformer model is unavailable: %s",
            exc,
        )
        return embedding_functions.DefaultEmbeddingFunction()


@lru_cache(maxsize=1)
def get_job_client():
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_jobs_dir)


@lru_cache(maxsize=1)
def get_news_client():
    settings = get_settings()
    return chromadb.PersistentClient(path=settings.chroma_news_dir)


@lru_cache(maxsize=1)
def get_job_collection() -> Collection:
    settings = get_settings()
    client = get_job_client()
    embedding_function = get_embedding_function()
    try:
        return client.get_collection(
            name=settings.job_collection_name,
            embedding_function=embedding_function,
        )
    except Exception:
        return client.get_or_create_collection(
            name=settings.job_collection_name,
            embedding_function=embedding_function,
            metadata={"description": "Job posting vector store"},
        )


@lru_cache(maxsize=1)
def get_news_collection() -> Collection:
    settings = get_settings()
    client = get_news_client()
    embedding_function = get_embedding_function()
    try:
        return client.get_collection(
            name=settings.news_collection_name,
            embedding_function=embedding_function,
        )
    except Exception:
        return client.get_or_create_collection(
            name=settings.news_collection_name,
            embedding_function=embedding_function,
            metadata={"description": "Game news vector store"},
        )
