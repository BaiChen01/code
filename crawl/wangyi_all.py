# -*- coding: utf-8 -*-
"""
网易招聘爬虫（入库版）
支持：
- 全量抓取
- 增量抓取
- 自动入库 MySQL
"""

import time
import hashlib
from datetime import datetime
from typing import Any, Dict, List

import requests
import pymysql


# ================== 数据库 ==================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "database": "game_intel_system",
    "charset": "utf8mb4"
}


def get_conn():
    return pymysql.connect(**DB_CONFIG)


# ================== API ==================
SOURCE_PAGE = "https://hr.163.com/job-list.html"
LIST_API = "https://hr.163.com/api/hr163/position/queryPage"

PAGE_SIZE = 20
TIMEOUT = 20
REQUEST_INTERVAL = 1.0


HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": SOURCE_PAGE,
    "Content-Type": "application/json;charset=UTF-8",
}


def make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ================== 工具 ==================
def hash_text(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def join_list(value):
    if isinstance(value, list):
        return "、".join(str(x) for x in value if x)
    return ""


# ================== API请求 ==================
def fetch_page(session, page):
    payload = {
        "currentPage": page,
        "pageSize": PAGE_SIZE,
        "keyword": ""
    }

    resp = session.post(LIST_API, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 200:
        raise RuntimeError("接口异常")

    return data


# ================== 数据解析 ==================
def extract(item):
    return {
        "job_title": item.get("name"),
        "product_line": item.get("productName"),
        "job_location": join_list(item.get("workPlaceNameList")),
        "job_requirement": item.get("requirement", ""),
        "job_responsibility": item.get("description", ""),
        "source_url": f"https://hr.163.com/job-detail.html?id={item.get('id')}",
        "company_name": "网易游戏"
    }


# ================== 入库 ==================
def insert_job(row):
    conn = get_conn()
    cursor = conn.cursor()

    try:
        # company
        cursor.execute("SELECT id FROM company WHERE company_name=%s", (row["company_name"],))
        r = cursor.fetchone()

        if r:
            company_id = r[0]
        else:
            cursor.execute("INSERT INTO company (company_name) VALUES (%s)", (row["company_name"],))
            company_id = cursor.lastrowid

        # hash
        text_all = (
            row["job_title"] +
            (row["product_line"] or "") +
            (row["job_location"] or "") +
            row["job_requirement"] +
            row["job_responsibility"]
        )
        text_hash = hash_text(text_all)

        # 判断是否存在
        cursor.execute(
            "SELECT id, raw_text_hash FROM job_post WHERE source_url=%s",
            (row["source_url"],)
        )
        exist = cursor.fetchone()

        if not exist:
            # 插入
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


# ================== 全量 ==================
def crawl_full():
    session = make_session()

    first = fetch_page(session, 1)
    data = first.get("data") or {}

    total_pages = int(data.get("pages") or 1)
    count = 0

    for page in range(1, total_pages + 1):
        print(f"\n[全量] 第 {page} 页")

        if page > 1:
            time.sleep(REQUEST_INTERVAL)
            page_json = fetch_page(session, page)
            items = (page_json.get("data") or {}).get("list") or []
        else:
            items = data.get("list") or []

        for item in items:
            row = extract(item)
            insert_job(row)

            count += 1
            print(f"已入库 {count}: {row['job_title']}")

    print("全量完成")




# ================== 启动 ==================
if __name__ == "__main__":

    crawl_full()
