# -*- coding: utf-8 -*-
"""
抓取腾讯招聘页面对应的职位信息
目标页：
https://careers.tencent.com/search.html?query=ot_40003001,ot_40003002,ot_40003003,ot_40003004,at_1

已知可用接口：
- 列表: https://careers.tencent.com/tencentcareer/api/post/Query
- 详情: https://careers.tencent.com/tencentcareer/api/post/ByPostId
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


SEARCH_PAGE = (
    "https://careers.tencent.com/search.html?"
    "query=ot_40003001,ot_40003002,ot_40003003,ot_40003004,at_1"
)

LIST_API = "https://careers.tencent.com/tencentcareer/api/post/Query"
DETAIL_API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"

OUTPUT_XLSX = "tencent_jobs.xlsx"
OUTPUT_CSV = "tencent_jobs.csv"

PAGE_SIZE = 10
REQUEST_INTERVAL = 0.3
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": SEARCH_PAGE,
    "Accept": "application/json, text/plain, */*",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_list_page(
    session: requests.Session,
    page_index: int,
    page_size: int = PAGE_SIZE,
    keyword: str = "",
) -> Dict[str, Any]:
    """
    抓职位列表页。
    如需按关键词过滤，可给 keyword 传值，例如 '算法'。
    目前先按中国区 + 中文抓取。
    """
    params = {
        "timestamp": now_ms(),
        "pageIndex": page_index,
        "pageSize": page_size,
        "language": "zh-cn",
        "area": "cn",
        "countryId": "1",
        "cityId": "",
        "bgIds": "",
        "productId": "",
        "categoryId": "",
        "parentCategoryId": "",
        "attrId": "",
        "keyword": keyword,
    }

    resp = session.get(LIST_API, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("Code") != 200:
        raise RuntimeError(f"列表接口返回异常: {data}")

    return data


def fetch_job_detail(session: requests.Session, post_id: str) -> Dict[str, Any]:
    params = {
        "timestamp": now_ms(),
        "postId": post_id,
        "language": "zh-cn",
    }

    resp = session.get(DETAIL_API, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("Code") != 200:
        raise RuntimeError(f"详情接口返回异常 post_id={post_id}: {data}")

    return data


def extract_list_record(post: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "post_id": post.get("PostId", ""),
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
        "source_search_page": SEARCH_PAGE,
    }


def extract_detail_fields(detail_json: Dict[str, Any]) -> Dict[str, Any]:
    data = detail_json.get("Data") or {}
    return {
        "职责描述": data.get("Responsibility", ""),
        "岗位要求": data.get("Requirement", ""),
        "招聘类型": data.get("AttrName", ""),
        "学历要求": data.get("RequireEduBackgroundName", ""),
        "是否有效": data.get("IsValid", ""),
    }


def crawl_all_jobs(
    max_pages: Optional[int] = None,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    session = make_session()

    first = fetch_list_page(session, page_index=1, keyword=keyword)
    data = first.get("Data") or {}
    total_count = int(data.get("Count") or 0)
    posts = data.get("Posts") or []

    print(f"接口返回总数: {total_count}")
    all_rows: List[Dict[str, Any]] = []

    def process_posts(post_list: List[Dict[str, Any]]) -> None:
        for post in post_list:
            base = extract_list_record(post)
            post_id = base["post_id"]

            detail_fields = {}
            if post_id:
                try:
                    time.sleep(REQUEST_INTERVAL)
                    detail_json = fetch_job_detail(session, post_id)
                    detail_fields = extract_detail_fields(detail_json)
                except Exception as e:
                    detail_fields = {
                        "职责描述": "",
                        "岗位要求": f"详情抓取失败: {e}",
                        "招聘类型": "",
                        "学历要求": "",
                        "是否有效": "",
                    }

            row = {**base, **detail_fields}
            all_rows.append(row)

    process_posts(posts)

    total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    for page_index in range(2, total_pages + 1):
        print(f"抓取第 {page_index}/{total_pages} 页")
        time.sleep(REQUEST_INTERVAL)
        page_json = fetch_list_page(session, page_index=page_index, keyword=keyword)
        page_posts = (page_json.get("Data") or {}).get("Posts") or []
        process_posts(page_posts)

    return all_rows


def save_results(rows: List[Dict[str, Any]]) -> None:
    df = pd.DataFrame(rows)

    if "post_id" in df.columns:
        df = df.drop_duplicates(subset=["post_id"])
    else:
        df = df.drop_duplicates()

    preferred_order = [
        "post_id",
        "职位名称",
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
        "职责描述",
        "岗位要求",
        "是否有效",
        "source_search_page",
    ]

    existing_cols = [c for c in preferred_order if c in df.columns]
    other_cols = [c for c in df.columns if c not in existing_cols]
    df = df[existing_cols + other_cols]

    df.to_excel(OUTPUT_XLSX, index=False)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"已保存 Excel: {OUTPUT_XLSX}")
    print(f"已保存 CSV:   {OUTPUT_CSV}")
    print(f"共保存 {len(df)} 条记录")


if __name__ == "__main__":
    # max_pages=None 表示抓全量
    # 若想先测试，可改成 max_pages=2
    rows = crawl_all_jobs(max_pages=2, keyword="")
    save_results(rows)