# -*- coding: utf-8 -*-
"""Check both vector store collections."""

from __future__ import annotations

import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


from app.services.vector_service import VectorService


def main() -> None:
    vector_service = VectorService()
    stats = vector_service.get_collection_stats()
    print("Vector store health check")
    print(f"- job collection count: {stats['job_collection_count']}")
    print(f"- news collection count: {stats['news_collection_count']}")


if __name__ == "__main__":
    main()
