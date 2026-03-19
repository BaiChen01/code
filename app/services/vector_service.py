# -*- coding: utf-8 -*-
"""Unified vector services for job and news knowledge stores."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.retriever_factory import get_job_collection, get_news_collection


def _distance_to_score(distance: Optional[float]) -> Optional[float]:
    if distance is None:
        return None
    return round(1.0 / (1.0 + float(distance)), 6)


COMPANY_ALIASES = {
    "腾讯游戏": ["腾讯游戏", "腾讯"],
    "网易游戏": ["网易游戏", "网易"],
    "米哈游": ["米哈游", "miHoYo", "HoYoverse"],
}


def _build_company_filter(company_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not company_name:
        return None

    aliases = COMPANY_ALIASES.get(company_name, [company_name])
    if len(aliases) == 1:
        return {"company_name": aliases[0]}
    return {"$or": [{"company_name": alias} for alias in aliases]}


class BaseVectorService:
    def __init__(self, collection) -> None:
        self.collection = collection

    def count(self) -> int:
        return self.collection.count()

    def _query_raw(
        self,
        *,
        query: str,
        top_k: int,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if where:
            return self.collection.query(query_texts=[query], n_results=top_k, where=where)
        return self.collection.query(query_texts=[query], n_results=top_k)


class JobVectorService(BaseVectorService):
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> None:
        super().__init__(get_job_collection())
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(
        self,
        text: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
    ) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []

        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.chunk_overlap

        chunks: List[str] = []
        start = 0
        size = len(text)
        while start < size:
            end = min(start + chunk_size, size)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == size:
                break
            start = max(0, end - overlap)
        return chunks

    def build_prefixed_text(self, row: Dict[str, Any], text_type: str, content: str) -> str:
        text_type_zh = "招聘要求" if text_type == "requirement" else "岗位职责"
        return (
            f"企业：{row.get('company_name', '')}\n"
            f"职位：{row.get('job_title', '')}\n"
            f"产品线：{row.get('product_line', '')}\n"
            f"地点：{row.get('job_location', '')}\n"
            f"文本类型：{text_type_zh}\n\n"
            f"内容：\n{content}"
        ).strip()

    def delete_job_vectors(self, job_post_id: int) -> None:
        self.collection.delete(where={"job_post_id": job_post_id})

    def _normalize_documents(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        documents = raw.get("documents", [[]])[0] if raw.get("documents") else []
        metadatas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
        distances = raw.get("distances", [[]])[0] if raw.get("distances") else []

        normalized: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            normalized.append(
                {
                    "source_type": "job",
                    "job_post_id": metadata.get("job_post_id"),
                    "company_name": metadata.get("company_name"),
                    "job_title": metadata.get("job_title"),
                    "product_line": metadata.get("product_line"),
                    "job_location": metadata.get("job_location"),
                    "text_type": metadata.get("text_type"),
                    "source_url": metadata.get("source_url"),
                    "snippet": document,
                    "score": _distance_to_score(distance),
                    "metadata": metadata,
                }
            )
        return normalized

    def search_docs(
        self,
        *,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
        product_line: Optional[str] = None,
        job_location: Optional[str] = None,
        text_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conditions: List[Dict[str, Any]] = []
        company_filter = _build_company_filter(company_name)
        if company_filter:
            conditions.append(company_filter)
        if product_line:
            conditions.append({"product_line": product_line})
        if job_location:
            conditions.append({"job_location": job_location})
        if text_type:
            conditions.append({"text_type": text_type})

        where = None
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        raw = self._query_raw(query=query, top_k=top_k, where=where)
        return self._normalize_documents(raw)

    def upsert_job(self, row: Dict[str, Any]) -> Dict[str, int]:
        self.delete_job_vectors(row["job_post_id"])
        requirement_chunks = self._upsert_one_text_type(
            row=row,
            text_type="requirement",
            raw_text=row.get("cleaned_requirement", ""),
        )
        responsibility_chunks = self._upsert_one_text_type(
            row=row,
            text_type="responsibility",
            raw_text=row.get("cleaned_responsibility", ""),
        )
        return {
            "job_post_id": row["job_post_id"],
            "requirement_chunks": requirement_chunks,
            "responsibility_chunks": responsibility_chunks,
            "total_chunks": requirement_chunks + responsibility_chunks,
        }

    def _upsert_one_text_type(self, row: Dict[str, Any], text_type: str, raw_text: str) -> int:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            return 0

        full_text = self.build_prefixed_text(row, text_type, raw_text)
        chunks = self.split_text(full_text)
        if not chunks:
            return 0

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for index, chunk in enumerate(chunks):
            ids.append(f"job_{row['job_post_id']}_{text_type}_chunk_{index}")
            documents.append(chunk)
            metadatas.append(
                {
                    "job_post_id": row["job_post_id"],
                    "company_name": row.get("company_name", "") or "",
                    "job_title": row.get("job_title", "") or "",
                    "product_line": row.get("product_line", "") or "",
                    "job_location": row.get("job_location", "") or "",
                    "source_url": row.get("source_url", "") or "",
                    "updated_at": str(row.get("updated_at", "")),
                    "text_type": text_type,
                }
            )

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)


class NewsVectorService(BaseVectorService):
    def __init__(self) -> None:
        super().__init__(get_news_collection())

    def _normalize_documents(self, raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        documents = raw.get("documents", [[]])[0] if raw.get("documents") else []
        metadatas = raw.get("metadatas", [[]])[0] if raw.get("metadatas") else []
        distances = raw.get("distances", [[]])[0] if raw.get("distances") else []

        normalized: List[Dict[str, Any]] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else None
            normalized.append(
                {
                    "source_type": "news",
                    "doc_id": metadata.get("doc_id"),
                    "title": metadata.get("title"),
                    "company_name": metadata.get("company_name"),
                    "publish_time": metadata.get("publish_time"),
                    "source_site": metadata.get("source_site"),
                    "author": metadata.get("author"),
                    "text_type": metadata.get("text_type"),
                    "source_url": metadata.get("source_url"),
                    "snippet": document,
                    "score": _distance_to_score(distance),
                    "metadata": metadata,
                }
            )
        return normalized

    def search_docs(
        self,
        *,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        where = _build_company_filter(company_name)
        raw = self._query_raw(query=query, top_k=top_k, where=where)
        return self._normalize_documents(raw)


class VectorService:
    """Unified vector service facade used by agents and scripts."""

    def __init__(self) -> None:
        self.job_service = JobVectorService()
        self.news_service = NewsVectorService()

        # Compatibility for existing scripts that expect a job collection.
        self.collection = self.job_service.collection

    def split_text(self, *args, **kwargs):
        return self.job_service.split_text(*args, **kwargs)

    def build_prefixed_text(self, *args, **kwargs):
        return self.job_service.build_prefixed_text(*args, **kwargs)

    def delete_job_vectors(self, *args, **kwargs):
        return self.job_service.delete_job_vectors(*args, **kwargs)

    def upsert_job(self, *args, **kwargs):
        return self.job_service.upsert_job(*args, **kwargs)

    def count(self) -> int:
        return self.job_service.count()

    def count_news(self) -> int:
        return self.news_service.count()

    def get_collection_stats(self) -> Dict[str, int]:
        return {
            "job_collection_count": self.job_service.count(),
            "news_collection_count": self.news_service.count(),
        }

    def search_job_docs(
        self,
        *,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
        product_line: Optional[str] = None,
        job_location: Optional[str] = None,
        text_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.job_service.search_docs(
            query=query,
            top_k=top_k,
            company_name=company_name,
            product_line=product_line,
            job_location=job_location,
            text_type=text_type,
        )

    def search_news_docs(
        self,
        *,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.news_service.search_docs(
            query=query,
            top_k=top_k,
            company_name=company_name,
        )

    def search_sources(
        self,
        *,
        query: str,
        source_scope: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
        product_line: Optional[str] = None,
        job_location: Optional[str] = None,
        text_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_docs: List[Dict[str, Any]] = []
        news_docs: List[Dict[str, Any]] = []

        if source_scope in {"job", "both"}:
            job_docs = self.search_job_docs(
                query=query,
                top_k=top_k,
                company_name=company_name,
                product_line=product_line,
                job_location=job_location,
                text_type=text_type,
            )

        if source_scope in {"news", "both"}:
            news_docs = self.search_news_docs(
                query=query,
                top_k=top_k,
                company_name=company_name,
            )

        return {
            "job_docs": job_docs,
            "news_docs": news_docs,
            "total_count": len(job_docs) + len(news_docs),
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
        text_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compatibility wrapper for the previous single-store job search."""
        where = None
        conditions: List[Dict[str, Any]] = []
        if company_name:
            conditions.append({"company_name": company_name})
        if text_type:
            conditions.append({"text_type": text_type})
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}
        return self.job_service._query_raw(query=query, top_k=top_k, where=where)
