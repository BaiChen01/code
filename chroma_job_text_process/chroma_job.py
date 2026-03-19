# -*- coding: utf-8 -*-
"""
招聘数据向量化脚本（正式版）
支持：
1. 全量向量化
2. 增量向量化
3. 向量检索
4. requirement / responsibility 分开入库
5. 回写 vector_mapping
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

import pymysql
import chromadb
from chromadb.utils import embedding_functions


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "game_intel_system",
    "charset": "utf8mb4"
}

CHROMA_DIR = "./chroma_jobs"
COLLECTION_NAME = "job_embeddings"
STATE_FILE = "./data/vector_state.json"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def get_mysql_conn():
    return pymysql.connect(**DB_CONFIG)


def get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5"
    )

    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "招聘岗位文本向量库"}
    )


def ensure_state_dir():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)


def load_last_vectorize_time() -> str:
    ensure_state_dir()
    if not os.path.exists(STATE_FILE):
        return "1970-01-01 00:00:00"

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("last_vectorize_time", "1970-01-01 00:00:00")


def save_last_vectorize_time(ts: str):
    ensure_state_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_vectorize_time": ts}, f, ensure_ascii=False, indent=2)


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunks = []
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


def build_prefixed_text(row: Dict, text_type: str, content: str) -> str:
    text_type_zh = "招聘要求" if text_type == "requirement" else "岗位职责"
    return f"""企业：{row.get('company_name', '')}
职位：{row.get('job_title', '')}
产品线：{row.get('product_line', '')}
地点：{row.get('job_location', '')}
文本类型：{text_type_zh}

内容：
{content}
""".strip()


def fetch_all_jobs() -> List[Dict]:
    conn = get_mysql_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    sql = """
    SELECT
        jp.id AS job_post_id,
        c.company_name,
        jp.job_title,
        jp.product_line,
        jp.job_location,
        jp.source_url,
        jp.updated_at,
        jt.cleaned_requirement,
        jt.cleaned_responsibility
    FROM job_post jp
    JOIN company c ON jp.company_id = c.id
    JOIN job_text jt ON jp.id = jt.job_post_id
    WHERE jp.status = 'active'
    ORDER BY jp.id ASC
    """
    cursor.execute(sql)
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows


def fetch_incremental_jobs(last_time: str) -> List[Dict]:
    conn = get_mysql_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    sql = """
    SELECT
        jp.id AS job_post_id,
        c.company_name,
        jp.job_title,
        jp.product_line,
        jp.job_location,
        jp.source_url,
        jp.updated_at,
        jt.cleaned_requirement,
        jt.cleaned_responsibility
    FROM job_post jp
    JOIN company c ON jp.company_id = c.id
    JOIN job_text jt ON jp.id = jt.job_post_id
    WHERE jp.status = 'active'
      AND jp.updated_at > %s
    ORDER BY jp.updated_at ASC
    """
    cursor.execute(sql, (last_time,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return rows


def delete_old_vectors(collection, job_post_id: int):
    try:
        collection.delete(where={"job_post_id": job_post_id})
    except Exception as e:
        print(f"[警告] 删除旧向量失败 job_post_id={job_post_id}, error={e}")


def clear_vector_mapping(job_post_id: int):
    conn = get_mysql_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM vector_mapping WHERE job_post_id = %s", (job_post_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def insert_vector_mapping(job_post_id: int, vector_doc_id: str, text_type: str, chunk_count: int):
    conn = get_mysql_conn()
    cursor = conn.cursor()
    try:
        sql = """
        INSERT INTO vector_mapping (job_post_id, vector_doc_id, text_type, chunk_count)
        VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (job_post_id, vector_doc_id, text_type, chunk_count))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def upsert_one_text_type(collection, row: Dict, text_type: str, raw_text: str) -> int:
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return 0

    full_text = build_prefixed_text(row, text_type, raw_text)
    chunks = split_text(full_text)

    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        vector_doc_id = f"job_{row['job_post_id']}_{text_type}_chunk_{i}"
        ids.append(vector_doc_id)
        documents.append(chunk)
        metadatas.append({
            "job_post_id": row["job_post_id"],
            "company_name": row["company_name"] or "",
            "job_title": row["job_title"] or "",
            "product_line": row["product_line"] or "",
            "job_location": row["job_location"] or "",
            "source_url": row["source_url"] or "",
            "updated_at": str(row["updated_at"]),
            "text_type": text_type
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    insert_vector_mapping(
        job_post_id=row["job_post_id"],
        vector_doc_id=f"job_{row['job_post_id']}_{text_type}",
        text_type=text_type,
        chunk_count=len(chunks)
    )

    return len(chunks)


def upsert_job_vectors(collection, row: Dict) -> int:
    clear_vector_mapping(row["job_post_id"])

    total_chunks = 0
    total_chunks += upsert_one_text_type(
        collection, row, "requirement", row.get("cleaned_requirement", "")
    )
    total_chunks += upsert_one_text_type(
        collection, row, "responsibility", row.get("cleaned_responsibility", "")
    )
    return total_chunks


def vectorize_full():
    collection = get_collection()
    rows = fetch_all_jobs()

    total_jobs = 0
    total_chunks = 0

    print(f"[全量] 待向量化岗位数: {len(rows)}")

    for row in rows:
        delete_old_vectors(collection, row["job_post_id"])
        chunk_num = upsert_job_vectors(collection, row)

        total_jobs += 1
        total_chunks += chunk_num
        print(f"[全量] job_post_id={row['job_post_id']} | chunks={chunk_num} | {row['job_title']}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_last_vectorize_time(now_str)

    print("\n===== 全量向量化完成 =====")
    print(f"岗位数: {total_jobs}")
    print(f"切块数: {total_chunks}")
    print(f"状态时间已更新: {now_str}")


def vectorize_incremental():
    collection = get_collection()
    last_time = load_last_vectorize_time()
    rows = fetch_incremental_jobs(last_time)

    total_jobs = 0
    total_chunks = 0

    print(f"[增量] 上次向量化时间: {last_time}")
    print(f"[增量] 待处理岗位数: {len(rows)}")

    for row in rows:
        delete_old_vectors(collection, row["job_post_id"])
        chunk_num = upsert_job_vectors(collection, row)

        total_jobs += 1
        total_chunks += chunk_num
        print(f"[增量] job_post_id={row['job_post_id']} | chunks={chunk_num} | {row['job_title']}")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_last_vectorize_time(now_str)

    print("\n===== 增量向量化完成 =====")
    print(f"岗位数: {total_jobs}")
    print(f"切块数: {total_chunks}")
    print(f"状态时间已更新: {now_str}")


def search_jobs(
    query: str,
    top_k: int = 5,
    company_name: Optional[str] = None,
    text_type: Optional[str] = None
):
    collection = get_collection()

    where = {}
    if company_name:
        where["company_name"] = company_name
    if text_type:
        where["text_type"] = text_type

    if where:
        result = collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where
        )
    else:
        result = collection.query(
            query_texts=[query],
            n_results=top_k
        )
    return result


if __name__ == "__main__":
    mode = "full"   # full / incremental / search

    if mode == "full":
        vectorize_full()
    elif mode == "incremental":
        vectorize_incremental()
    else:
        res = search_jobs("哪些岗位要求 Unity 开发经验", top_k=5, text_type="requirement")
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))