# -*- coding: utf-8 -*-
"""
腾讯社招岗位抓取（低频稳定版）
来源页：
https://careers.tencent.com/search.html

输出文件：
- tencent_social.xlsx
- tencent_social.csv
- tencent_social_checkpoint.csv  （中途检查点）
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


SOURCE_PAGE = "https://careers.tencent.com/search.html"
LIST_API = "https://careers.tencent.com/tencentcareer/api/post/Query"
DETAIL_API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"

OUTPUT_XLSX = "tencent_social.xlsx"
OUTPUT_CSV = "tencent_social.csv"
CHECKPOINT_CSV = "tencent_social_checkpoint.csv"

PAGE_SIZE = 10
TIMEOUT = 20

# 低频稳定参数
LIST_INTERVAL = 2.0
DETAIL_INTERVAL = 3.0
PAGE_INTERVAL = 5.0
SAVE_EVERY = 50
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": SOURCE_PAGE,
    "Accept": "application/json, text/plain, */*",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def sleep_with_jitter(base: float, jitter: float = 0.8) -> None:
    time.sleep(base + random.uniform(0, jitter))


def request_json_with_retry(
    session: requests.Session,
    url: str,
    params: Dict[str, Any],
    base_wait: float,
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    last_err = None

    for attempt in range(max_retries):
        try:
            sleep_with_jitter(base_wait, 0.8)
            resp = session.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            backoff = 5 * (attempt + 1) + random.uniform(0, 2)
            print(f"[重试] {url} 第 {attempt + 1}/{max_retries} 次失败：{e}，{backoff:.1f}s 后重试")
            time.sleep(backoff)

    raise RuntimeError(f"请求失败: {url}, error={last_err}")


def fetch_list_page(
    session: requests.Session,
    page_index: int,
    page_size: int = PAGE_SIZE,
    keyword: str = "",
) -> Dict[str, Any]:
    params = {
        "timestamp": now_ms(),
        "pageIndex": page_index,
        "pageSize": page_size,
        "language": "zh-cn",
        "area": "cn",
        "countryId": "",
        "cityId": "",
        "bgIds": "",
        "productId": "",
        "categoryId": "",
        "parentCategoryId": "",
        "attrId": "",
        "keyword": keyword,
    }

    data = request_json_with_retry(session, LIST_API, params, base_wait=LIST_INTERVAL)
    if data.get("Code") != 200:
        raise RuntimeError(f"列表接口返回异常: {data}")
    return data


def fetch_job_detail(session: requests.Session, post_id: str) -> Dict[str, Any]:
    params = {
        "timestamp": now_ms(),
        "postId": post_id,
        "language": "zh-cn",
    }

    data = request_json_with_retry(session, DETAIL_API, params, base_wait=DETAIL_INTERVAL)
    if data.get("Code") != 200:
        raise RuntimeError(f"详情接口返回异常 post_id={post_id}: {data}")
    return data


def extract_list_record(post: Dict[str, Any]) -> Dict[str, Any]:
    post_id = post.get("PostId") or post.get("postId") or ""

    return {
        "post_id": post_id,
        "职位名称": post.get("RecruitPostName", ""),
        "职位类别": post.get("CategoryName", ""),
        "工作地点": post.get("LocationName", ""),
        "事业群/部门": post.get("BGName", ""),
        "产品线": post.get("ProductName", ""),
        "工作年限": post.get("RequireWorkYearsName", ""),
        "更新时间": post.get("LastUpdateTime", ""),
        "详情链接": post.get("PostURL", ""),
        "国家": post.get("CountryName", ""),
        "公司代码": post.get("ComCode", ""),
        "公司名称": post.get("ComName", ""),
        "来源页": SOURCE_PAGE,
    }


def extract_detail_fields(detail_json: Dict[str, Any]) -> Dict[str, Any]:
    data = detail_json.get("Data") or detail_json.get("data") or {}

    return {
        "职责描述": data.get("Responsibility", ""),
        "岗位要求": data.get("Requirement", ""),
        "招聘类型": data.get("AttrName", ""),
        "学历要求": data.get("RequireEduBackgroundName", ""),
        "岗位状态": data.get("IsValid", ""),
        "英文职位名": data.get("RecruitPostNameEn", ""),
        "邮箱投递": data.get("Email", ""),
    }


def save_checkpoint(rows: List[Dict[str, Any]], filename: str) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    if "post_id" in df.columns:
        df = df.drop_duplicates(subset=["post_id"])
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"[检查点] 已保存 {len(df)} 条到 {filename}")


def crawl_all_jobs(
    max_pages: Optional[int] = None,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    session = make_session()

    first = fetch_list_page(session, page_index=1, keyword=keyword)
    data = first.get("Data") or first.get("data") or {}
    total_count = int(data.get("Count") or data.get("count") or 0)
    posts = data.get("Posts") or data.get("posts") or []

    print(f"接口返回总数: {total_count}")

    all_rows: List[Dict[str, Any]] = []

    def process_posts(post_list: List[Dict[str, Any]]) -> None:
        for i, post in enumerate(post_list, 1):
            base = extract_list_record(post)
            post_id = base["post_id"]

            detail_fields = {}
            if post_id:
                try:
                    detail_json = fetch_job_detail(session, post_id)
                    detail_fields = extract_detail_fields(detail_json)
                except Exception as e:
                    detail_fields = {
                        "职责描述": "",
                        "岗位要求": f"详情抓取失败: {e}",
                        "招聘类型": "",
                        "学历要求": "",
                        "岗位状态": "",
                        "英文职位名": "",
                        "邮箱投递": "",
                    }

            row = {**base, **detail_fields}
            all_rows.append(row)

            print(f"已抓取 {len(all_rows)} 条：{base['职位名称']}")

            if len(all_rows) % SAVE_EVERY == 0:
                save_checkpoint(all_rows, CHECKPOINT_CSV)

    process_posts(posts)

    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE if total_count else 1
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    for page_index in range(2, total_pages + 1):
        print(f"\n抓取第 {page_index}/{total_pages} 页")
        sleep_with_jitter(PAGE_INTERVAL, 1.5)

        page_json = fetch_list_page(session, page_index=page_index, keyword=keyword)
        page_posts = (
            (page_json.get("Data") or page_json.get("data") or {}).get("Posts")
            or (page_json.get("Data") or page_json.get("data") or {}).get("posts")
            or []
        )
        process_posts(page_posts)

    return all_rows


def save_results(rows: List[Dict[str, Any]]) -> None:
    df = pd.DataFrame(rows)

    if df.empty:
        print("没有抓到数据。")
        return

    if "post_id" in df.columns:
        df = df.drop_duplicates(subset=["post_id"])
    else:
        df = df.drop_duplicates()

    preferred_order = [
        "post_id",
        "职位名称",
        "英文职位名",
        "职位类别",
        "工作地点",
        "事业群/部门",
        "产品线",
        "工作年限",
        "学历要求",
        "招聘类型",
        "更新时间",
        "公司名称",
        "国家",
        "公司代码",
        "详情链接",
        "邮箱投递",
        "职责描述",
        "岗位要求",
        "岗位状态",
        "来源页",
    ]

    existing_cols = [c for c in preferred_order if c in df.columns]
    other_cols = [c for c in df.columns if c not in existing_cols]
    df = df[existing_cols + other_cols]

    df.to_excel(OUTPUT_XLSX, index=False)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"\n已保存 Excel: {OUTPUT_XLSX}")
    print(f"已保存 CSV:   {OUTPUT_CSV}")
    print(f"共保存 {len(df)} 条记录")


if __name__ == "__main__":
    # 测试可设 max_pages=2；全量改成 None
    rows = crawl_all_jobs(max_pages=None, keyword="游戏")
    save_results(rows)