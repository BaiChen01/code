# -*- coding: utf-8 -*-
"""
腾讯招聘爬虫（入库版）
功能：
1. 抓取腾讯招聘岗位
2. 自动入 MySQL(company + job_post + job_text)
3. 自动去重 + 更新
"""

import random
import time
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import pymysql


# ================== 数据库配置 ==================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "game_intel_system",
    "charset": "utf8mb4"
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


# ================== 爬虫配置 ==================
SOURCE_PAGE = "https://careers.tencent.com/search.html"
LIST_API = "https://careers.tencent.com/tencentcareer/api/post/Query"
DETAIL_API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"

PAGE_SIZE = 10
TIMEOUT = 20

LIST_INTERVAL = 2.0
DETAIL_INTERVAL = 3.0
PAGE_INTERVAL = 5.0

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": SOURCE_PAGE,
}


# ================== 工具函数 ==================
def now_ms():
    return int(time.time() * 1000)


def sleep_with_jitter(base: float):
    time.sleep(base + random.uniform(0, 0.8))


def hash_text(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ================== 请求封装 ==================
def request_json(session, url, params, base_wait):
    sleep_with_jitter(base_wait)
    resp = session.get(url, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ================== API ==================
def fetch_list_page(session, page_index):
    params = {
        "timestamp": now_ms(),
        "pageIndex": page_index,
        "pageSize": PAGE_SIZE,
        "language": "zh-cn",
        "area": "cn",
        "keyword": "",
    }
    return request_json(session, LIST_API, params, LIST_INTERVAL)


def fetch_detail(session, post_id):
    params = {
        "timestamp": now_ms(),
        "postId": post_id,
        "language": "zh-cn",
    }
    return request_json(session, DETAIL_API, params, DETAIL_INTERVAL)


# ================== 数据解析 ==================
def extract_list(post):
    return {
        "post_id": post.get("PostId"),
        "job_title": post.get("RecruitPostName"),
        "product_line": post.get("ProductName"),
        "job_location": post.get("LocationName"),
        "source_url": post.get("PostURL"),
        "company_name": "腾讯游戏"
    }


def extract_detail(detail_json):
    data = detail_json.get("Data") or {}
    return {
        "job_requirement": data.get("Requirement", ""),
        "job_responsibility": data.get("Responsibility", "")
    }


# ================== 入库核心 ==================
def insert_job(row):
    conn = get_conn()
    cursor = conn.cursor()

    try:
        company_name = row["company_name"]

        # 1 获取 company_id
        cursor.execute("SELECT id FROM company WHERE company_name=%s", (company_name,))
        result = cursor.fetchone()

        if result:
            company_id = result[0]
        else:
            cursor.execute(
                "INSERT INTO company (company_name) VALUES (%s)",
                (company_name,)
            )
            company_id = cursor.lastrowid

        # 2 hash
        text_all = (
            row["job_title"] +
            (row["product_line"] or "") +
            (row["job_location"] or "") +
            row["job_requirement"] +
            row["job_responsibility"]
        )
        text_hash = hash_text(text_all)

        # 3 查是否存在
        cursor.execute(
            "SELECT id, raw_text_hash FROM job_post WHERE source_url=%s",
            (row["source_url"],)
        )
        exist = cursor.fetchone()

        if not exist:
            # 插入 job_post
            cursor.execute("""
                INSERT INTO job_post (
                    company_id, source_url, job_title,
                    product_line, job_location,
                    crawl_time, raw_text_hash
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                company_id,
                row["source_url"],
                row["job_title"],
                row["product_line"],
                row["job_location"],
                datetime.now(),
                text_hash
            ))

            job_id = cursor.lastrowid

            # 插入 job_text
            cursor.execute("""
                INSERT INTO job_text (
                    job_post_id,
                    job_requirement,
                    job_responsibility,
                    cleaned_requirement,
                    cleaned_responsibility
                ) VALUES (%s,%s,%s,%s,%s)
            """, (
                job_id,
                row["job_requirement"],
                row["job_responsibility"],
                row["job_requirement"],
                row["job_responsibility"]
            ))

        else:
            job_id, old_hash = exist

            if old_hash != text_hash:
                # 更新
                cursor.execute("""
                    UPDATE job_post
                    SET job_title=%s,
                        product_line=%s,
                        job_location=%s,
                        raw_text_hash=%s,
                        updated_at=NOW()
                    WHERE id=%s
                """, (
                    row["job_title"],
                    row["product_line"],
                    row["job_location"],
                    text_hash,
                    job_id
                ))

                cursor.execute("""
                    UPDATE job_text
                    SET job_requirement=%s,
                        job_responsibility=%s,
                        cleaned_requirement=%s,
                        cleaned_responsibility=%s
                    WHERE job_post_id=%s
                """, (
                    row["job_requirement"],
                    row["job_responsibility"],
                    row["job_requirement"],
                    row["job_responsibility"],
                    job_id
                ))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("数据库错误:", e)

    finally:
        cursor.close()
        conn.close()


# ================== 主流程 ==================
def crawl_incremental(max_pages=3):
    """
    增量抓取：只抓前 N 页
    """

    session = make_session()
    count = 0

    for page in range(1, max_pages + 1):
        print(f"\n[增量] 抓第 {page} 页")

        page_json = fetch_list_page(session, page)
        posts = (page_json.get("Data") or {}).get("Posts") or []

        for post in posts:
            base = extract_list(post)

            # ⭐ 关键：先查数据库是否存在
            conn = get_conn()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id, raw_text_hash FROM job_post WHERE source_url=%s",
                (base["source_url"],)
            )
            exist = cursor.fetchone()

            cursor.close()
            conn.close()

            # ===== 如果存在且不需要更新，可以跳过 =====
            if exist:
                job_id, old_hash = exist

                # 可选优化：不抓详情直接跳（更快）
                # 👉 如果你想更精确，可以继续抓详情再判断 hash
                print("跳过已有岗位:", base["job_title"])
                continue

            # ===== 新岗位才抓详情 =====
            detail = fetch_detail(session, base["post_id"])
            detail_fields = extract_detail(detail)

            row = {**base, **detail_fields}

            insert_job(row)

            count += 1
            print(f"[新增] {row['job_title']}")

    print(f"\n增量完成，共新增 {count} 条")

# ================== 启动 ==================
if __name__ == "__main__":
    crawl_incremental(max_pages=3)