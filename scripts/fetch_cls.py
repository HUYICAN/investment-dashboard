#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch CLS (财联社) telegraph news and save to JSON.

Uses the public CLS web API. No authentication required.

Usage:
    python3 fetch_cls.py [--pages N] [--output PATH]
"""

import json
import os
import sys
import re
import argparse
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "cls_telegraph.json")

CLS_API_URL = "https://www.cls.cn/api/cache"
CLS_PARAMS = {
    "app": "CailianpressWeb",
    "name": "telegraphList",
    "os": "web",
    "sv": "8.7.9",
    "sign": "aaaab95cde63a0d31364caece7be4027",
}
CLS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.cls.cn/telegraph",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def fetch_page(last_time=0):
    params = dict(CLS_PARAMS)
    params["lastTime"] = str(last_time)
    query = "&".join("%s=%s" % (k, v) for k, v in params.items())
    url = "%s?%s" % (CLS_API_URL, query)

    req = Request(url, headers=CLS_HEADERS)
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print("  Fetch error: %s" % e, file=sys.stderr)
        return []
    except Exception as e:
        print("  Parse error: %s" % e, file=sys.stderr)
        return []

    roll_data = data.get("data", {}).get("roll_data", [])
    return roll_data


def clean_content(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_time(ctime):
    if not ctime:
        return ""
    try:
        dt = datetime.fromtimestamp(int(ctime), tz=timezone(timedelta(hours=8)))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ""


def fetch_all(pages=1):
    all_items = []
    last_time = 0
    seen_ctimes = set()

    for page in range(pages):
        items = fetch_page(last_time)
        if not items:
            print("  Page %d: no items, stopping" % (page + 1))
            break

        new_count = 0
        for item in items:
            ctime = item.get("ctime", 0)
            if ctime in seen_ctimes:
                continue
            seen_ctimes.add(ctime)

            content = clean_content(item.get("content", ""))
            title = clean_content(item.get("title", ""))

            if not content and not title:
                continue

            all_items.append({
                "ctime": ctime,
                "time": parse_time(ctime),
                "title": title,
                "content": content,
                "level": item.get("level", "C"),
                "is_red": item.get("is_red", False),
                "stock_list": item.get("stock_list", []),
            })
            new_count += 1

        print("  Page %d: %d items (total: %d)" % (page + 1, new_count, len(all_items)))
        break

    all_items.sort(key=lambda x: x["ctime"], reverse=True)
    return all_items


def main():
    parser = argparse.ArgumentParser(description="Fetch CLS telegraph news")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages (default: 1)")
    parser.add_argument("--output", type=str, default=OUTPUT_PATH, help="Output JSON path")
    args = parser.parse_args()

    print("Fetching CLS telegraph (%d pages)..." % args.pages)
    items = fetch_all(args.pages)
    print("Total: %d items" % len(items))

    if not items:
        print("No items fetched, keeping existing data")
        sys.exit(1)

    output = {
        "fetch_time": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(items),
        "items": items,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Saved to %s" % args.output)

    beijing_now = datetime.now(timezone(timedelta(hours=8)))
    today_str = beijing_now.strftime("%Y-%m-%d")
    today_items = [i for i in items if i["time"].startswith(today_str)]
    red_items = [i for i in items if i["is_red"] or i["level"] in ("A", "B")]
    print("  Today: %d items | Red/Important: %d items" % (len(today_items), len(red_items)))


if __name__ == "__main__":
    main()
