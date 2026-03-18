import re
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


START_URL = "https://app.mokahr.com/social-recruitment/pwrd/142341#/jobs?285895%5B0%5D=%E5%AE%8C%E7%BE%8E%E4%B8%96%E7%95%8C%E6%B8%B8%E6%88%8F&page=1&anchorName=jobsList"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_job_id(url: str) -> str:
    if not url:
        return ""
    # 常见：/job/123456 或 ?jobId=123456
    m = re.search(r"/job[s]?/(\d+)", url)
    if m:
        return m.group(1)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    for key in ("jobId", "id", "positionId"):
        if key in qs and qs[key]:
            return qs[key][0]
    return ""


def safe_inner_text(locator):
    try:
        return clean_text(locator.inner_text(timeout=1500))
    except Exception:
        return ""


def safe_get_attr(locator, name):
    try:
        return locator.get_attribute(name, timeout=1500) or ""
    except Exception:
        return ""


def collect_network_log(page, network_log):
    def on_response(resp):
        try:
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if any(k in url.lower() for k in ["job", "position", "recruit", "list", "search"]):
                item = {
                    "time": now_str(),
                    "url": url,
                    "status": resp.status,
                    "content_type": ct,
                }
                # 只尝试记录 JSON
                if "application/json" in ct:
                    try:
                        item["json_preview"] = resp.json()
                    except Exception:
                        item["json_preview"] = None
                network_log.append(item)
        except Exception:
            pass

    page.on("response", on_response)


def wait_for_job_cards(page):
    """
    不同 Moka 模板 class 名可能不同，所以用一组候选选择器兜底。
    """
    candidate_selectors = [
        "a[href*='job']",
        "a[href*='position']",
        "[class*='job']",
        "[class*='position']",
        "[class*='list'] a",
        "text=查看详情",
        "text=职位详情",
    ]

    for sel in candidate_selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            return True
        except Exception:
            continue
    return False


def get_job_cards(page):
    """
    优先找带 job/position 链接的 a 标签，再回退到可能的卡片容器。
    """
    selectors = [
        "a[href*='job']",
        "a[href*='position']",
        "[class*='job-card']",
        "[class*='position-card']",
        "[class*='jobItem']",
        "[class*='positionItem']",
        "[class*='card']",
    ]
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                return loc
        except Exception:
            pass
    return page.locator("a")


def parse_card(card, page_num):
    text = clean_text(card.inner_text(timeout=2000))
    href = safe_get_attr(card, "href")

    # 岗位名：优先看卡片第一行/标题样式
    title = ""
    title_selectors = [
        "[class*='title']",
        "h3",
        "h4",
        "[class*='name']",
        "[class*='position']",
        "[class*='job']",
    ]
    for sel in title_selectors:
        try:
            sub = card.locator(sel).first
            if sub.count() > 0:
                title = safe_inner_text(sub)
                if title:
                    break
        except Exception:
            pass

    if not title:
        # 回退：取首行
        title = clean_text(text.split(" ")[0] if text else "")

    # 地点 / 类别 / 时间：先粗抽，再留给后续调优
    location = ""
    job_type = ""
    publish_time = ""

    # 常见中文模式
    m_loc = re.search(r"(北京|上海|广州|深圳|杭州|成都|重庆|武汉|苏州|西安|长沙|厦门|天津|南京|海外|远程)", text)
    if m_loc:
        location = m_loc.group(1)

    m_time = re.search(r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}|刚刚|今天|昨天)", text)
    if m_time:
        publish_time = m_time.group(1)

    # 猜测类别：标题或文本里的高频职能词
    type_keywords = ["研发", "测试", "策划", "运营", "设计", "市场", "产品", "美术", "职能", "销售", "数据"]
    for kw in type_keywords:
        if kw in text:
            job_type = kw
            break

    return {
        "job_title": title,
        "job_url": href,
        "location": location,
        "job_type": job_type,
        "business_unit": "完美世界游戏",
        "publish_time": publish_time,
        "page": page_num,
        "job_id": extract_job_id(href),
        "card_text": text,
        "snapshot_time": now_str(),
    }


def parse_detail(context, url):
    detail = {
        "department": "",
        "experience": "",
        "education": "",
        "responsibilities": "",
        "requirements": "",
        "tags": "",
        "full_text": "",
    }
    if not url:
        return detail

    page = context.new_page()
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        full_text = clean_text(page.locator("body").inner_text(timeout=5000))
        detail["full_text"] = full_text

        # 常见中文字段提取
        for line in full_text.split("。"):
            if "部门" in line and not detail["department"]:
                detail["department"] = clean_text(line)
            if ("经验" in line or "工作年限" in line) and not detail["experience"]:
                detail["experience"] = clean_text(line)
            if "学历" in line and not detail["education"]:
                detail["education"] = clean_text(line)

        # 职责 / 要求分段
        resp_patterns = [
            r"(岗位职责[:：].*?)(任职要求[:：]|岗位要求[:：]|职位要求[:：]|$)",
            r"(工作职责[:：].*?)(任职要求[:：]|岗位要求[:：]|职位要求[:：]|$)",
        ]
        req_patterns = [
            r"(任职要求[:：].*?)($)",
            r"(岗位要求[:：].*?)($)",
            r"(职位要求[:：].*?)($)",
        ]

        for p in resp_patterns:
            m = re.search(p, full_text, re.S)
            if m:
                detail["responsibilities"] = clean_text(m.group(1))
                break

        for p in req_patterns:
            m = re.search(p, full_text, re.S)
            if m:
                detail["requirements"] = clean_text(m.group(1))
                break

        # tags
        tags = []
        for kw in ["本科", "硕士", "英语", "C++", "Python", "Java", "Unity", "UE", "策划", "测试"]:
            if kw in full_text:
                tags.append(kw)
        detail["tags"] = ",".join(tags)

    except Exception as e:
        detail["full_text"] = f"[detail_parse_error] {e}"
    finally:
        page.close()

    return detail


def click_next_page(page):
    next_selectors = [
        "text=下一页",
        "text=Next",
        "[aria-label='next page']",
        "[class*='next']",
        "button:has-text('下一页')",
    ]

    for sel in next_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() == 0:
                continue

            cls = (btn.get_attribute("class") or "").lower()
            disabled = btn.get_attribute("disabled")
            text = clean_text(btn.inner_text() or "")

            if disabled is not None or "disabled" in cls:
                return False

            btn.click(timeout=5000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.wait_for_timeout(1500)
            return True
        except Exception:
            continue
    return False


def deduplicate_jobs(rows):
    seen = set()
    result = []
    for r in rows:
        key = (r.get("job_id"), r.get("job_title"), r.get("job_url"))
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


def main():
    all_rows = []
    network_log = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        collect_network_log(page, network_log)

        page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not wait_for_job_cards(page):
            print("未能识别到职位列表，请手动检查选择器或页面是否有反爬。")
            browser.close()
            return

        max_pages = 50
        page_num = 1

        while page_num <= max_pages:
            print(f"正在抓取第 {page_num} 页")
            page.wait_for_timeout(1500)

            cards = get_job_cards(page)
            count = cards.count()

            page_rows = []
            for i in range(count):
                try:
                    card = cards.nth(i)
                    row = parse_card(card, page_num)

                    # 过滤无效项
                    if not row["job_title"] and not row["job_url"]:
                        continue

                    # 补全相对链接
                    if row["job_url"] and row["job_url"].startswith("/"):
                        row["job_url"] = urljoin(page.url, row["job_url"])

                    page_rows.append(row)
                except Exception:
                    continue

            # 去重后再抓详情
            page_rows = deduplicate_jobs(page_rows)

            # 抓详情（可注释掉，先只跑列表）
            for row in page_rows:
                if row.get("job_url"):
                    detail = parse_detail(context, row["job_url"])
                    row.update(detail)

            all_rows.extend(page_rows)

            has_next = click_next_page(page)
            if not has_next:
                break

            page_num += 1

        browser.close()

    all_rows = deduplicate_jobs(all_rows)

    df = pd.DataFrame(all_rows)
    df.to_csv("jobs.csv", index=False, encoding="utf-8-sig")
    df.to_json("jobs.json", orient="records", force_ascii=False, indent=2)

    with open("network_log.json", "w", encoding="utf-8") as f:
        json.dump(network_log, f, ensure_ascii=False, indent=2)

    print(f"完成，共抓到 {len(df)} 条岗位")
    print("输出文件：jobs.csv / jobs.json / network_log.json")


if __name__ == "__main__":
    main()