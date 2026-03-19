# -*- coding: utf-8 -*-
"""
向量索引构建脚本

职责：
1. 从 MySQL 读取招聘文本
2. 调用 VectorService 进行切块与入向量库
3. 写入 vector_mapping 映射表

运行方式：
python scripts/build_vector_index.py
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import Dict, List, Optional

import pymysql
from pymysql.cursors import DictCursor


# 让脚本可以从项目根目录导入 app
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.services.vector_service import VectorService


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "game_intel_system",
    "charset": "utf8mb4",
}


def get_mysql_conn():
    return pymysql.connect(**DB_CONFIG)


def fetch_jobs_from_mysql(limit: Optional[int] = None) -> List[Dict]:
    """
    从数据库读取招聘数据，组织为统一 record
    """
    conn = get_mysql_conn()
    cursor = conn.cursor(DictCursor)

    try:
        sql = """
        SELECT
            jp.id AS job_post_id,
            c.company_name,
            jp.job_title,
            jp.product_line,
            jp.job_location,
            jp.source_url,
            jp.crawl_time,
            jt.cleaned_requirement,
            jt.cleaned_responsibility
        FROM job_post jp
        JOIN company c ON jp.company_id = c.id
        JOIN job_text jt ON jp.id = jt.job_post_id
        WHERE jp.status = 'active'
        ORDER BY jp.id ASC
        """

        if limit is not None:
            sql += " LIMIT %s"
            cursor.execute(sql, (limit,))
        else:
            cursor.execute(sql)

        rows = cursor.fetchall()
        return list(rows)

    finally:
        cursor.close()
        conn.close()


def clear_vector_mapping(job_post_id: int) -> None:
    """
    清理某岗位已有的映射关系
    """
    conn = get_mysql_conn()
    cursor = conn.cursor()

    try:
        sql = "DELETE FROM vector_mapping WHERE job_post_id = %s"
        cursor.execute(sql, (job_post_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def save_vector_mapping(
    job_post_id: int,
    vector_doc_id: str,
    text_type: str,
    chunk_count: int,
) -> None:
    """
    写入 vector_mapping 映射表
    """
    conn = get_mysql_conn()
    cursor = conn.cursor()

    try:
        sql = """
        INSERT INTO vector_mapping (
            job_post_id,
            vector_doc_id,
            text_type,
            chunk_count
        ) VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (job_post_id, vector_doc_id, text_type, chunk_count))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def build_chunks_for_job(vector_service: VectorService, record: Dict) -> List[Dict]:
    """
    对单条岗位构造 requirement / responsibility 的全部 chunk 信息
    返回统一 chunk 描述，供后续写入向量库与映射表
    """
    results: List[Dict] = []

    text_fields = [
        ("requirement", record.get("cleaned_requirement", "")),
        ("responsibility", record.get("cleaned_responsibility", "")),
    ]

    for text_type, raw_text in text_fields:
        raw_text = (raw_text or "").strip()
        if not raw_text:
            continue

        full_text = vector_service.build_prefixed_text(record, text_type, raw_text)
        chunks = vector_service.split_text(full_text)

        if not chunks:
            continue

        vector_doc_prefix = f"job_{record['job_post_id']}_{text_type}"

        results.append(
            {
                "job_post_id": record["job_post_id"],
                "text_type": text_type,
                "vector_doc_id": vector_doc_prefix,
                "chunk_count": len(chunks),
                "chunks": chunks,
                "metadata_base": {
                    "job_post_id": record["job_post_id"],
                    "company_name": record.get("company_name", "") or "",
                    "job_title": record.get("job_title", "") or "",
                    "product_line": record.get("product_line", "") or "",
                    "job_location": record.get("job_location", "") or "",
                    "source_url": record.get("source_url", "") or "",
                    "crawl_time": str(record.get("crawl_time", "") or ""),
                    "text_type": text_type,
                },
            }
        )

    return results


def upsert_chunks_to_vector_db(
    vector_service: VectorService,
    chunk_records: List[Dict],
) -> Dict[str, int]:
    """
    将 build_chunks_for_job 生成的 chunk 统一写入向量库
    """
    requirement_chunks = 0
    responsibility_chunks = 0

    for item in chunk_records:
        ids = []
        documents = []
        metadatas = []

        for idx, chunk in enumerate(item["chunks"]):
            ids.append(f"{item['vector_doc_id']}_chunk_{idx}")
            documents.append(chunk)

            metadata = dict(item["metadata_base"])
            metadata["chunk_index"] = idx
            metadatas.append(metadata)

        vector_service.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        if item["text_type"] == "requirement":
            requirement_chunks += item["chunk_count"]
        elif item["text_type"] == "responsibility":
            responsibility_chunks += item["chunk_count"]

    return {
        "requirement_chunks": requirement_chunks,
        "responsibility_chunks": responsibility_chunks,
    }


def process_one_job(vector_service: VectorService, record: Dict) -> Dict:
    """
    处理单条岗位：
    1. 删除旧向量
    2. 删除旧 mapping
    3. 构造 chunks
    4. 写入向量库
    5. 写入 vector_mapping
    """
    job_post_id = record["job_post_id"]

    vector_service.delete_job_vectors(job_post_id)
    clear_vector_mapping(job_post_id)

    chunk_records = build_chunks_for_job(vector_service, record)

    if not chunk_records:
        return {
            "job_post_id": job_post_id,
            "requirement_chunks": 0,
            "responsibility_chunks": 0,
            "total_chunks": 0,
        }

    chunk_stats = upsert_chunks_to_vector_db(vector_service, chunk_records)

    for item in chunk_records:
        save_vector_mapping(
            job_post_id=item["job_post_id"],
            vector_doc_id=item["vector_doc_id"],
            text_type=item["text_type"],
            chunk_count=item["chunk_count"],
        )

    total_chunks = (
        chunk_stats["requirement_chunks"] +
        chunk_stats["responsibility_chunks"]
    )

    return {
        "job_post_id": job_post_id,
        "requirement_chunks": chunk_stats["requirement_chunks"],
        "responsibility_chunks": chunk_stats["responsibility_chunks"],
        "total_chunks": total_chunks,
    }


def main():
    limit: Optional[int] = None
    # 示例：limit = 100

    vector_service = VectorService()
    records = fetch_jobs_from_mysql(limit=limit)

    total_jobs = 0
    success_jobs = 0
    failed_jobs = 0
    total_requirement_chunks = 0
    total_responsibility_chunks = 0

    print("=" * 60)
    print("开始构建向量索引")
    print(f"待处理岗位数: {len(records)}")
    print(f"limit: {limit}")
    print("=" * 60)

    for idx, record in enumerate(records, start=1):
        try:
            result = process_one_job(vector_service, record)

            total_jobs += 1
            success_jobs += 1
            total_requirement_chunks += result["requirement_chunks"]
            total_responsibility_chunks += result["responsibility_chunks"]

            print(
                f"[{idx}/{len(records)}] 成功 "
                f"job_post_id={result['job_post_id']} "
                f"| req={result['requirement_chunks']} "
                f"| resp={result['responsibility_chunks']} "
                f"| total={result['total_chunks']} "
                f"| {record.get('company_name', '')} - {record.get('job_title', '')}"
            )

        except Exception as e:
            total_jobs += 1
            failed_jobs += 1

            print(
                f"[{idx}/{len(records)}] 失败 "
                f"job_post_id={record.get('job_post_id')} "
                f"| {record.get('company_name', '')} - {record.get('job_title', '')}"
            )
            print(f"错误信息: {e}")
            print(traceback.format_exc())

    print("\n" + "=" * 60)
    print("向量索引构建完成")
    print(f"总岗位数: {total_jobs}")
    print(f"成功岗位数: {success_jobs}")
    print(f"失败岗位数: {failed_jobs}")
    print(f"requirement chunks: {total_requirement_chunks}")
    print(f"responsibility chunks: {total_responsibility_chunks}")
    print(f"向量库当前总数: {vector_service.count()}")
    print("=" * 60)


if __name__ == "__main__":
    main()