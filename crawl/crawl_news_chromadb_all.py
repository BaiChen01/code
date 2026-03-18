# -*- coding: utf-8 -*-
"""
游戏日报资讯爬虫 + 向量入库（带已存在/新增标注）
功能：
1. 爬取游戏日报资讯栏目
2. 只保留标题包含：腾讯 / 网易 / 米哈游 的文章
3. 在爬取时判断文章是否已存在于向量库
4. 标注 [已存在] / [新增]
5. 新文章抓取正文、分块并写入 Chroma 向量数据库

说明：
- page=1 使用 https://news.yxrb.net/info/
- page>=2 使用 https://news.yxrb.net/info/{page}.html
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.utils import embedding_functions


# =========================
# 基础配置
# =========================
BASE_INFO_URL = "https://news.yxrb.net/info/"
PAGE_URL_TEMPLATE = "https://news.yxrb.net/info/{page}.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": "https://news.yxrb.net/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

REQUEST_TIMEOUT = 20
REQUEST_INTERVAL = 1.0

# 只抓标题中包含这些企业名的文章
TARGET_COMPANIES = ["腾讯", "网易", "米哈游"]

# 向量库目录
CHROMA_DIR = "./chroma_yxrb"

# 集合名
COLLECTION_NAME = "game_news_yxrb"

# 分块参数
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


# =========================
# 数据结构
# =========================
@dataclass
class Article:
    doc_id: str
    title: str
    source_url: str
    source_site: str
    author: str
    publish_time: str
    company_name: str
    content: str


# =========================
# 网络请求
# =========================
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def fetch_html(session: requests.Session, url: str) -> str:
    time.sleep(REQUEST_INTERVAL)
    resp = session.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


# =========================
# 工具函数
# =========================
def detect_company_from_title(title: str) -> Optional[str]:
    for company in TARGET_COMPANIES:
        if company in title:
            return company
    return None


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def make_doc_id(url: str) -> str:
    # 用 URL 做稳定ID
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url))


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = normalize_text(text)
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


# =========================
# 解析列表页
# =========================
def get_info_page_url(page: int) -> str:
    if page == 1:
        return BASE_INFO_URL
    return PAGE_URL_TEMPLATE.format(page=page)


def parse_article_links_from_list(html: str) -> List[Tuple[str, str]]:
    """
    返回 [(title, url), ...]
    只保留标题包含腾讯/网易/米哈游的文章
    """
    soup = BeautifulSoup(html, "lxml")
    results: List[Tuple[str, str]] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        title = a.get_text(strip=True)

        if not title:
            continue

        company = detect_company_from_title(title)
        if not company:
            continue

        # 文章详情页通常是 /2026/0318/6652.html 这种格式
        if not re.search(r"/\d{4}/\d{4}/\d+\.html$", href):
            continue

        if href.startswith("/"):
            href = "https://news.yxrb.net" + href

        key = (title, href)
        if key in seen:
            continue
        seen.add(key)

        results.append((title, href))

    return results


# =========================
# 解析详情页
# =========================
def parse_article_detail(html: str, url: str, fallback_title: str = "") -> Article:
    soup = BeautifulSoup(html, "lxml")

    # 标题
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True).split(" - ")[0]
    if not title:
        title = fallback_title

    # 作者
    author = ""
    text_all = soup.get_text("\n", strip=True)

    m_author = re.search(r"作者\s*[:：]\s*([^\n]+)", text_all)
    if m_author:
        author = m_author.group(1).strip()

    # 发布时间
    publish_time = ""
    m_time = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", text_all)
    if m_time:
        publish_time = m_time.group(1)

    # 正文：优先抽正文段落
    paragraphs = []

    for p in soup.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if txt and len(txt) > 10:
            paragraphs.append(txt)

    if len(paragraphs) < 3:
        candidates = soup.find_all(["div", "article"])
        blocks = []
        for node in candidates:
            txt = node.get_text("\n", strip=True)
            if txt and len(txt) > 200:
                blocks.append(txt)
        if blocks:
            body = max(blocks, key=len)
            paragraphs = [line.strip() for line in body.splitlines() if len(line.strip()) > 10]

    content = normalize_text("\n".join(paragraphs))

    return Article(
        doc_id=make_doc_id(url),
        title=title,
        source_url=url,
        source_site="游戏日报",
        author=author,
        publish_time=publish_time,
        company_name=detect_company_from_title(title) or "",
        content=content,
    )


# =========================
# 向量库
# =========================
def get_chroma_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5"
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "游戏日报资讯文章向量库"}
    )
    return collection


def article_exists_in_vector_db(collection, doc_id: str) -> bool:
    """
    通过检查第一块 chunk 是否存在，判断文章是否已入向量库
    """
    chunk0_id = f"{doc_id}_chunk_0"
    try:
        result = collection.get(ids=[chunk0_id])
        ids = result.get("ids", [])
        return len(ids) > 0
    except Exception:
        return False


def upsert_article_to_vector_db(collection, article: Article):
    chunks = split_text(article.content)

    if not chunks:
        print(f"[跳过] 正文为空: {article.title}")
        return

    ids = []
    documents = []
    metadatas = []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{article.doc_id}_chunk_{idx}"
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "doc_id": article.doc_id,
            "chunk_id": idx,
            "title": article.title,
            "source_url": article.source_url,
            "source_site": article.source_site,
            "author": article.author,
            "publish_time": article.publish_time,
            "company_name": article.company_name,
            "text_type": "news_content",
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    print(f"[UPSERT] 完成: {article.title}")


# =========================
# 主流程
# =========================
def crawl_all_info_articles(max_pages: Optional[int] = None):
    session = make_session()
    collection = get_chroma_collection()

    page = 1
    total_articles = 0
    inserted_articles = 0
    existing_articles = 0

    while True:
        if max_pages is not None and page > max_pages:
            break

        list_url = get_info_page_url(page)
        print(f"\n[列表页] 第 {page} 页: {list_url}")

        try:
            html = fetch_html(session, list_url)
        except Exception as e:
            print(f"[停止] 列表页抓取失败: page={page}, error={e}")
            break

        article_links = parse_article_links_from_list(html)

        if not article_links:
            print(f"[停止] 第 {page} 页未发现目标文章")
            break

        for title, url in article_links:
            total_articles += 1

            doc_id = make_doc_id(url)
            exists = article_exists_in_vector_db(collection, doc_id)

            if exists:
                existing_articles += 1
                print(f"[已存在] {title}")
                continue

            print(f"[新增] {title}")

            try:
                detail_html = fetch_html(session, url)
                article = parse_article_detail(detail_html, url, fallback_title=title)

                if not article.content:
                    print(f"[跳过] 正文为空: {article.title}")
                    continue

                upsert_article_to_vector_db(collection, article)
                inserted_articles += 1
                print(f"[入库] {article.title}")

            except Exception as e:
                print(f"[失败] 文章抓取失败: {url}, error={e}")

        page += 1

    print("\n===== 完成 =====")
    print(f"命中标题文章数: {total_articles}")
    print(f"已存在文章数: {existing_articles}")
    print(f"新增入库文章数: {inserted_articles}")


# =========================
# 查询示例
# =========================
def search_news(query: str, company_name: Optional[str] = None, top_k: int = 5):
    collection = get_chroma_collection()

    where = None
    if company_name:
        where = {"company_name": company_name}

    result = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where
    )

    return result


if __name__ == "__main__":
    # 初次建议先测试较小页数
    crawl_all_info_articles(max_pages=50)

    # 查询示例
    # res = search_news("腾讯 游戏 AI 布局", company_name="腾讯", top_k=3)
    # print(res)