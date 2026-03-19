# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List, Optional

import chromadb
from chromadb.utils import embedding_functions


class VectorService:
    def __init__(
        self,
        chroma_dir: str = "./chroma_jobs",
        collection_name: str = "job_embeddings",
        model_name: str = "BAAI/bge-small-zh-v1.5",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        client = chromadb.PersistentClient(path=self.chroma_dir)
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.model_name
        )

        self.collection = client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=embedding_fn,
            metadata={"description": "招聘岗位文本向量库"},
        )

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
        n = len(text)

        while start < n:
            end = min(start + chunk_size, n)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end == n:
                break
            start = max(0, end - overlap)

        return chunks

    def build_prefixed_text(self, row: Dict, text_type: str, content: str) -> str:
        text_type_zh = "招聘要求" if text_type == "requirement" else "岗位职责"
        return f"""企业：{row.get('company_name', '')}
职位：{row.get('job_title', '')}
产品线：{row.get('product_line', '')}
地点：{row.get('job_location', '')}
文本类型：{text_type_zh}

内容：
{content}
""".strip()

    def delete_job_vectors(self, job_post_id: int) -> None:
        try:
            self.collection.delete(where={"job_post_id": job_post_id})
        except Exception as e:
            print(f"[警告] 删除旧向量失败 job_post_id={job_post_id}, error={e}")

    def _upsert_one_text_type(self, row: Dict, text_type: str, raw_text: str) -> int:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            return 0

        full_text = self.build_prefixed_text(row, text_type, raw_text)
        chunks = self.split_text(full_text)

        if not chunks:
            return 0

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict] = []

        for i, chunk in enumerate(chunks):
            vector_doc_id = f"job_{row['job_post_id']}_{text_type}_chunk_{i}"
            ids.append(vector_doc_id)
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

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        return len(chunks)

    def upsert_job(self, row: Dict) -> Dict:
        self.delete_job_vectors(row["job_post_id"])

        req_chunks = self._upsert_one_text_type(
            row=row,
            text_type="requirement",
            raw_text=row.get("cleaned_requirement", ""),
        )

        resp_chunks = self._upsert_one_text_type(
            row=row,
            text_type="responsibility",
            raw_text=row.get("cleaned_responsibility", ""),
        )

        return {
            "job_post_id": row["job_post_id"],
            "requirement_chunks": req_chunks,
            "responsibility_chunks": resp_chunks,
            "total_chunks": req_chunks + resp_chunks,
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        company_name: Optional[str] = None,
        text_type: Optional[str] = None,
    ) -> Dict:
        where = {}
        if company_name:
            where["company_name"] = company_name
        if text_type:
            where["text_type"] = text_type

        if where:
            result = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where,
            )
        else:
            result = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        return result

    def count(self) -> int:
        return self.collection.count()