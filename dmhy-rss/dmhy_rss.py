# -*- coding: utf-8 -*-
"""
DMHY (动漫花园) RSS 生成器
功能：抓取动漫花园资源列表页 -> 解析条目 -> 增量去重 -> 生成标准 RSS 2.0 feed
用法：
  python dmhy_rss.py                 # 抓取并更新 feed（增量，已见过的条目不会重复）
  python dmhy_rss.py --force         # 忽略去重状态，重新生成全部条目
  python dmhy_rss.py --out <path>    # 指定输出文件
依赖：requests beautifulsoup4 feedgen  (pip install requests beautifulsoup4 feedgen)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# ---------------------------------------------------------------------------
# 配置（可按需修改）
# ---------------------------------------------------------------------------
BASE_URL = "https://share.dmhy.org"
# 默认抓取 VCB-Studio(581) 的最新发布；想换其他字幕组/关键词，改这一行即可
LIST_URL = (
    "https://share.dmhy.org/topics/list?"
    "keyword=&sort_id=0&team_id=581&order=date-desc"
)
FEED_TITLE = "VCB-Studio - 动漫花园资源网"
FEED_DESC = "VCB-Studio 字幕组在动漫花园的最新发布（本地自建 RSS）"
FEED_LINK = LIST_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dmhy_feed.xml")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dmhy_state.json")

TZ_CST = timezone(timedelta(hours=8), "CST")
DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2})")


def fetch_page(url: str) -> str:
    """抓取列表页，返回 HTML 文本。"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def parse_topics(html: str) -> list[dict]:
    """解析 #topic_list 表格中的资源条目。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="topic_list")
    if table is None:
        return []
    rows = table.select("tbody tr")
    topics = []
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        # --- 日期：优先取隐藏 span 里的标准时间 ---
        pub_dt = None
        hidden = tds[0].find("span", style=lambda v: v and "display" in v)
        if hidden:
            m = DATE_RE.search(hidden.get_text())
            if m:
                y, mo, d, h, mi = map(int, m.groups())
                pub_dt = datetime(y, mo, d, h, mi, tzinfo=TZ_CST)

        # --- 标题与详情链接 ---
        title_a = tds[2].find("a", href=re.compile(r"/topics/view/"))
        if title_a is None:
            continue
        title = title_a.get_text(strip=True)
        href = title_a.get("href", "")
        topic_url = href if href.startswith("http") else BASE_URL + href
        topic_id = re.search(r"/topics/view/(\d+)", href)
        topic_id = topic_id.group(1) if topic_id else topic_url

        # --- 分类 ---
        cat = tds[1].get_text(strip=True) if len(tds) > 1 else ""

        # --- 磁链 ---
        magnet = ""
        m_a = tr.find("a", class_="arrow-magnet")
        if m_a is not None:
            magnet = m_a.get("href", "")

        # --- 大小 ---
        size = tds[4].get_text(strip=True) if len(tds) > 4 else ""

        # --- 发布人 ---
        publisher = tds[-1].get_text(strip=True) if len(tds) > 6 else ""

        topics.append({
            "id": topic_id,
            "title": title,
            "link": topic_url,
            "pub_date": pub_dt,
            "category": cat,
            "magnet": magnet,
            "size": size,
            "publisher": publisher,
        })
    return topics


def load_state(path: str) -> set:
    """读取已见条目 id 集合。"""
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: str, seen: set) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, ensure_ascii=False, indent=2)


def to_rfc822(dt: datetime) -> str:
    """转成 RSS 要求的 RFC822 时间格式。"""
    if dt is None:
        return datetime.now(TZ_CST).strftime("%a, %d %b %Y %H:%M:%S %z")
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")


def build_feed(topics: list[dict], out_path: str, feed_url: str = "") -> None:
    """把条目写入标准 RSS 2.0 XML 文件。feed_url 为公开订阅地址（self link）。"""
    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=FEED_LINK, rel="alternate")
    self_url = feed_url or "file:///" + out_path.replace("\\", "/")
    fg.link(href=self_url, rel="self")
    fg.description(FEED_DESC)
    fg.language("zh-cn")

    # 按发布时间倒序
    topics_sorted = sorted(
        topics,
        key=lambda t: t["pub_date"] or datetime.min.replace(tzinfo=TZ_CST),
        reverse=True,
    )
    for t in topics_sorted:
        fe = fg.add_entry()
        fe.title(t["title"])
        fe.link(href=t["link"])
        fe.guid(t["link"], permalink=True)
        fe.pubDate(to_rfc822(t["pub_date"]))
        fe.category({"term": t["category"]})
        # 描述里带上大小、发布人和磁链，方便阅读器直接使用
        desc_lines = []
        if t["size"]:
            desc_lines.append(f"大小：{t['size']}")
        if t["category"]:
            desc_lines.append(f"分类：{t['category']}")
        if t["publisher"]:
            desc_lines.append(f"发布人：{t['publisher']}")
        if t["magnet"]:
            desc_lines.append(f'<p>磁力链接：<a href="{t["magnet"]}">magnet</a></p>')
        fe.description("<br/>".join(desc_lines) if desc_lines else t["title"])

    fg.rss_file(out_path, pretty=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="DMHY RSS 生成器")
    ap.add_argument("--force", action="store_true", help="忽略去重状态，重新生成全部")
    ap.add_argument("--out", default=DEFAULT_OUT, help="输出 XML 文件路径")
    ap.add_argument("--url", default=LIST_URL, help="要抓取的列表页 URL")
    ap.add_argument("--feed-url", default="", help="feed 的公开订阅地址（self link）")
    args = ap.parse_args()

    print(f"[1/3] 抓取页面: {args.url}")
    html = fetch_page(args.url)
    topics = parse_topics(html)
    if not topics:
        print("!! 未解析到任何条目，可能页面结构变化或请求被拦截")
        return 1
    print(f"    解析到 {len(topics)} 条资源")

    seen = load_state(STATE_FILE)
    if args.force:
        fresh = topics
    else:
        fresh = [t for t in topics if t["id"] not in seen]
    print(f"[2/3] 新增条目: {len(fresh)} 条（去重库已有 {len(seen)} 条）")

    # 增量模式下：新条目 + 历史全部条目，保证 feed 始终包含完整记录
    all_topics = list(fresh)
    if not args.force:
        all_topics += [t for t in topics if t["id"] in seen]

    build_feed(all_topics, args.out, args.feed_url)
    print(f"[3/3] 已生成 feed: {args.out}")

    # 更新去重状态：把本次见过的 id 全部并入
    seen.update(t["id"] for t in topics)
    save_state(STATE_FILE, seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
