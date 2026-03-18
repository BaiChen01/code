# -*- coding: utf-8 -*-
"""
网易招聘职位抓取
目标页：
https://hr.163.com/job-list.html

输出文件：
- wangyi.xlsx
- wangyi.csv
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


SOURCE_PAGE = "https://hr.163.com/job-list.html"
LIST_API = "https://hr.163.com/api/hr163/position/queryPage"

OUTPUT_XLSX = "F:\pachong\data\wangyi.xlsx"
OUTPUT_CSV = "F:\pachong\data\wangyi.csv"

PAGE_SIZE = 20
TIMEOUT = 20
REQUEST_INTERVAL = 1.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": SOURCE_PAGE,
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json, text/plain, */*",
}


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
    payload = {
        "currentPage": page_index,
        "pageSize": page_size,
        "keyword": keyword,
    }

    resp = session.post(LIST_API, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != 200:
        raise RuntimeError(f"列表接口返回异常: {data}")

    return data


def join_list(value) -> str:
    if isinstance(value, list):
        return "、".join(str(x) for x in value if x is not None)
    return "" if value is None else str(value)


def fmt_time(ts) -> str:
    try:
        if ts in (None, ""):
            return ""
        ts = int(ts)
        # 网易这里通常是毫秒时间戳
        if ts > 10**11:
            ts = ts / 1000
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return str(ts)


def extract_record(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "post_id": item.get("id", ""),
        "职位名称": item.get("name", ""),
        "职位类别": item.get("firstPostTypeName", ""),
        "招聘人数": item.get("recruitNum", ""),
        "学历要求": item.get("reqEducationName", ""),
        "工作年限": item.get("reqWorkYearsName", ""),
        "部门": item.get("firstDepName", ""),
        "产品线": item.get("productName", ""),
        "工作地点": join_list(item.get("workPlaceNameList")),
        "更新时间": fmt_time(item.get("updateTime")),
        "岗位描述": item.get("description", ""),
        "岗位要求": item.get("requirement", ""),
        "工作类型": item.get("workType", ""),
        "产品代码": item.get("product", ""),
        "来源页": SOURCE_PAGE,
    }


def crawl_all_jobs(
    max_pages: Optional[int] = None,
    keyword: str = "",
) -> List[Dict[str, Any]]:
    session = make_session()

    first = fetch_list_page(session, page_index=1, keyword=keyword)
    data = first.get("data") or {}
    total_count = int(data.get("total") or 0)
    total_pages = int(data.get("pages") or 0)
    job_list = data.get("list") or []

    print(f"接口返回总数: {total_count}")
    print(f"接口返回页数: {total_pages}")

    all_rows: List[Dict[str, Any]] = []
    for item in job_list:
        all_rows.append(extract_record(item))

    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    for page_index in range(2, total_pages + 1):
        print(f"抓取第 {page_index}/{total_pages} 页")
        time.sleep(REQUEST_INTERVAL)

        page_json = fetch_list_page(session, page_index=page_index, keyword=keyword)
        page_items = (page_json.get("data") or {}).get("list") or []

        for item in page_items:
            all_rows.append(extract_record(item))

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
        "职位类别",
        "招聘人数",
        "学历要求",
        "工作年限",
        "部门",
        "产品线",
        "工作地点",
        "更新时间",
        "岗位描述",
        "岗位要求",
        "工作类型",
        "产品代码",
        "来源页",
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
    # 先测试可设 max_pages=2；抓全量改成 None
    rows = crawl_all_jobs(max_pages=None, keyword="游戏")
    save_results(rows)