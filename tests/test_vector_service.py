from __future__ import annotations

from app.services import vector_service as vector_module
from app.services.vector_service import VectorService


class FakeCollection:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.last_where = None

    def count(self) -> int:
        return 3 if self.kind == "job" else 2

    def query(self, query_texts, n_results, where=None):  # noqa: ANN001
        self.last_where = where
        if self.kind == "job":
            return {
                "documents": [["Unity requirement snippet"]],
                "metadatas": [[
                    {
                        "job_post_id": 101,
                        "company_name": "腾讯游戏",
                        "job_title": "Unity 客户端开发",
                        "product_line": "射击游戏",
                        "job_location": "上海",
                        "text_type": "requirement",
                        "source_url": "https://example.com/job/101",
                    }
                ]],
                "distances": [[0.25]],
            }
        return {
            "documents": [["News snippet"]],
            "metadatas": [[
                {
                    "doc_id": "n-1",
                    "title": "腾讯游戏研发动态",
                    "company_name": "腾讯",
                    "publish_time": "2026-03-19",
                    "source_site": "游戏日报",
                    "author": "tester",
                    "text_type": "news_content",
                    "source_url": "https://example.com/news/1",
                }
            ]],
            "distances": [[0.5]],
        }


def test_vector_service_search_sources_normalizes_dual_results(monkeypatch) -> None:
    job_collection = FakeCollection("job")
    news_collection = FakeCollection("news")

    monkeypatch.setattr(vector_module, "get_job_collection", lambda: job_collection)
    monkeypatch.setattr(vector_module, "get_news_collection", lambda: news_collection)

    service = VectorService()
    result = service.search_sources(
        query="腾讯游戏 动态",
        source_scope="both",
        company_name="腾讯游戏",
        job_location="上海",
        top_k=3,
    )

    assert result["total_count"] == 2
    assert result["job_docs"][0]["source_type"] == "job"
    assert result["news_docs"][0]["source_type"] == "news"
    assert result["job_docs"][0]["company_name"] == "腾讯游戏"
    assert result["news_docs"][0]["title"] == "腾讯游戏研发动态"
    assert news_collection.last_where is not None


def test_vector_service_collection_stats(monkeypatch) -> None:
    monkeypatch.setattr(vector_module, "get_job_collection", lambda: FakeCollection("job"))
    monkeypatch.setattr(vector_module, "get_news_collection", lambda: FakeCollection("news"))

    service = VectorService()

    assert service.get_collection_stats() == {
        "job_collection_count": 3,
        "news_collection_count": 2,
    }
