import re
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin

import pandas as pd
from playwright.sync_api import sync_playwright


START_URL = "https://app.mokahr.com/social-recruitment/pwrd/142341#/jobs?285895%5B0%5D=%E5%AE%8C%E7%BE%8E%E4%B8%96%E7%95%8C%E6%B8%B8%E6%88%8F&page=1&anchorName=jobsList"

MAX_PAGES = 100
HEADLESS = True
LIST_WAIT_MS = 2000
DETAIL_WAIT_MS = 1200
OUTPUT_FILE = r"F:\\pachong\\data\\完美.xlsx"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_job_id(url: str) -> str:
    if not url:
        return ""
    patterns = [
        r"/job/(\d+)",
        r"/jobs/(\d+)",
        r"/position/(\d+)",
        r"[?&](?:jobId|positionId|id)=(\d+)",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


def update_hash_page(url: str, page_num: int) -> str:
    if "#/jobs?" not in url:
        return url

    base, hash_part = url.split("#", 1)
    if "?" not in hash_part:
        return url

    path_part, query_str = hash_part.split("?", 1)
    qs = parse_qs(query_str, keep_blank_values=True)
    qs["page"] = [str(page_num)]

    new_query = urlencode(qs, doseq=True)
    return f"{base}#{path_part}?{new_query}"


def guess_location(text: str) -> str:
    cities = [
        "北京", "上海", "深圳", "广州", "杭州", "成都", "重庆", "武汉", "南京",
        "苏州", "西安", "长沙", "天津", "厦门", "珠海", "青岛", "沈阳", "大连",
        "海外", "远程"
    ]
    for c in cities:
        if c in text:
            return c
    return ""


def safe_inner_text(locator) -> str:
    try:
        return clean_text(locator.inner_text(timeout=1500))
    except Exception:
        return ""


def safe_attr(locator, name: str) -> str:
    try:
        return locator.get_attribute(name, timeout=1500) or ""
    except Exception:
        return ""


def wait_for_jobs_loaded(page):
    candidate_selectors = [
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a[href*='/position/']",
        "a[href*='jobId=']",
        "a[href*='positionId=']",
        "text=职位",
        "text=岗位",
    ]
    for sel in candidate_selectors:
        try:
            page.wait_for_selector(sel, timeout=8000)
            page.wait_for_timeout(LIST_WAIT_MS)
            return True
        except Exception:
            continue
    return False


def get_job_link_locator(page):
    selectors = [
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a[href*='/position/']",
        "a[href*='jobId=']",
        "a[href*='positionId=']",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            pass
    return page.locator("a")


def parse_list_item(link_locator, page_num: int, current_url: str):
    href = safe_attr(link_locator, "href")
    text = safe_inner_text(link_locator)

    if not href and not text:
        return None

    if href.startswith("/"):
        href = urljoin(current_url, href)

    title = ""
    for sel in ["h1", "h2", "h3", "h4", "[class*='title']", "[class*='name']"]:
        try:
            sub = link_locator.locator(sel).first
            if sub.count() > 0:
                title = safe_inner_text(sub)
                if title:
                    break
        except Exception:
            pass

    if not title:
        lines = [x for x in re.split(r"\s{2,}|[\r\n]+", text) if clean_text(x)]
        if lines:
            title = clean_text(lines[0])

    if not title:
        return None

    job_type = ""
    type_keywords = [
        "研发", "测试", "策划", "运营", "设计", "市场", "产品",
        "美术", "职能", "销售", "数据", "算法", "客户端", "服务端"
    ]
    for kw in type_keywords:
        if kw in text or kw in title:
            job_type = kw
            break

    row = {
        "job_id": extract_job_id(href),
        "job_title": title,
        "job_url": href,
        "location": guess_location(text),
        "job_type": job_type,
        "card_text": text,
        "page": page_num,
        "snapshot_time": now_str(),
    }
    return row


def parse_detail_page(context, url: str):
    result = {
        "department": "",
        "responsibilities": "",
        "full_text": "",
    }

    if not url:
        return result

    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(DETAIL_WAIT_MS)

        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        body_text = clean_text(page.locator("body").inner_text(timeout=5000))
        result["full_text"] = body_text

        dept_patterns = [
            r"(部门[:：]\s*[^。；;]+)",
            r"(所属部门[:：]\s*[^。；;]+)",
        ]
        for p in dept_patterns:
            m = re.search(p, body_text, re.I)
            if m:
                result["department"] = clean_text(m.group(1))
                break

        resp_patterns = [
            r"(岗位职责[:：].*?)(任职要求[:：]|岗位要求[:：]|职位要求[:：]|任职资格[:：]|$)",
            r"(工作职责[:：].*?)(任职要求[:：]|岗位要求[:：]|职位要求[:：]|任职资格[:：]|$)",
            r"(职责描述[:：].*?)(任职要求[:：]|岗位要求[:：]|职位要求[:：]|任职资格[:：]|$)",
        ]
        for p in resp_patterns:
            m = re.search(p, body_text, re.S)
            if m:
                result["responsibilities"] = clean_text(m.group(1))
                break

    except Exception as e:
        result["full_text"] = f"[detail_parse_error] {e}"
    finally:
        page.close()

    return result


def deduplicate(rows):
    seen = set()
    out = []
    for r in rows:
        key = (r.get("job_id", ""), r.get("job_title", ""), r.get("job_url", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def page_signature(rows):
    return tuple(sorted((r.get("job_title", ""), r.get("job_url", "")) for r in rows))


def save_xlsx(rows, output_file):
    export_rows = []
    for r in rows:
        export_rows.append({
            "职位名称": r.get("job_title", "") or "",
            "职位类别": r.get("job_type", "") or "",
            "部门": r.get("department", "") or "",
            "工作地点": r.get("location", "") or "",
            "职责描述": r.get("responsibilities", "") or "",
            "岗位要求": r.get("card_text", "") or "",   # 这里改成 card_text
            "产品线": "完美世界游戏",                  # 若要置空，改成 ""
        })

    df = pd.DataFrame(export_rows, columns=[
        "职位名称", "职位类别", "部门", "工作地点", "职责描述", "岗位要求", "产品线"
    ])

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="岗位列表")
        ws = writer.book["岗位列表"]
        ws.freeze_panes = "A2"

        widths = {
            "A": 28,
            "B": 16,
            "C": 18,
            "D": 18,
            "E": 60,
            "F": 60,
            "G": 18,
        }
        for col, width in widths.items():
            ws.column_dimensions[col].width = width

    print(f"[SAVE] {output_file}")


def spider():
    all_rows = []
    prev_sig = None
    repeat_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        for page_num in range(1, MAX_PAGES + 1):
            current_url = update_hash_page(START_URL, page_num)
            print(f"[INFO] 打开第 {page_num} 页: {current_url}")

            page.goto(current_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)

            if not wait_for_jobs_loaded(page):
                print(f"[STOP] 第 {page_num} 页未识别到职位列表，停止")
                break

            links = get_job_link_locator(page)
            count = links.count()

            rows_this_page = []
            for i in range(count):
                try:
                    row = parse_list_item(links.nth(i), page_num, page.url)
                    if not row:
                        continue
                    if not row["job_title"]:
                        continue
                    if len(row["job_title"]) > 80:
                        continue
                    rows_this_page.append(row)
                except Exception:
                    continue

            rows_this_page = deduplicate(rows_this_page)

            if not rows_this_page:
                print(f"[STOP] 第 {page_num} 页没有抓到岗位，停止")
                break

            sig = page_signature(rows_this_page)
            if sig == prev_sig:
                repeat_count += 1
                print(f"[WARN] 第 {page_num} 页与上一页重复，重复次数={repeat_count}")
            else:
                repeat_count = 0

            if repeat_count >= 1:
                print("[STOP] 检测到重复页，认为已无法继续翻页")
                break

            prev_sig = sig

            for row in rows_this_page:
                if row.get("job_url"):
                    try:
                        detail = parse_detail_page(context, row["job_url"])
                        row.update(detail)
                    except Exception as e:
                        row["full_text"] = f"[detail_error] {e}"

            all_rows.extend(rows_this_page)
            all_rows = deduplicate(all_rows)

            print(f"[INFO] 第 {page_num} 页抓到 {len(rows_this_page)} 条，累计 {len(all_rows)} 条")
            save_xlsx(all_rows, OUTPUT_FILE)

        browser.close()

    all_rows = deduplicate(all_rows)
    save_xlsx(all_rows, OUTPUT_FILE)
    print(f"[DONE] 共抓取 {len(all_rows)} 条岗位")


if __name__ == "__main__":
    spider()