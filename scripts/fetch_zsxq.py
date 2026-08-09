#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch zsxq (知识星球) topics using cookie from environment variable.

Usage:
    python3 fetch_zsxq.py [--output PATH]

Requires ZSXQ_COOKIE environment variable to be set.
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timezone, timedelta
from html import unescape
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "..", "data", "zsxq_latest.json")

ZSXQ_GROUP_ID = os.environ.get("ZSXQ_GROUP_ID", "28851441484121")
ZSXQ_API_URL = "https://api.zsxq.com/v2/groups/%s/topics?count=25" % ZSXQ_GROUP_ID

BJT = timezone(timedelta(hours=8))


def log(msg):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    print("[%s] %s" % (now, msg), flush=True)


def fetch_zsxq_topics(cookie_str):
    """Call the zsxq API and return parsed topics."""
    if not cookie_str:
        log("  No cookie available, skipping zsxq fetch")
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Cookie": cookie_str,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://wx.zsxq.com/group/%s" % ZSXQ_GROUP_ID,
    }

    req = Request(ZSXQ_API_URL, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        log("  HTTP Error %d: %s" % (e.code, e.reason))
        if e.code == 401:
            log("  Cookie expired! Please update ZSXQ_COOKIE secret.")
        return None
    except URLError as e:
        log("  Fetch error: %s" % e)
        return None
    except Exception as e:
        log("  Unexpected error: %s" % e)
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log("  Invalid JSON response")
        return None

    if not data.get("succeeded"):
        log("  API returned not succeeded: %s" % json.dumps(data.get("code", "")))
        return None

    topics = data.get("resp_data", {}).get("topics", [])

    result = []
    for t in topics:
        raw_text = ""
        if t.get("talk"):
            raw_text = t["talk"].get("text", "") or ""

        clean_text = re.sub(
            r'<e[^>]*title="([^"]*)"[^>]*\/>',
            lambda m: unescape(m.group(1)),
            raw_text,
        )
        clean_text = re.sub(r'<e[^>]*\/>', '', clean_text)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        clean_text = clean_text.strip()

        result.append({
            "title": t.get("title", "") or "",
            "time": t.get("create_time", ""),
            "text": clean_text,
            "author": (t.get("talk", {}) or {}).get("owner", {}).get("name", "") if t.get("talk") else "",
        })

    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch zsxq topics")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help="Output JSON path")
    args = parser.parse_args()

    cookie = os.environ.get("ZSXQ_COOKIE", "")
    if not cookie:
        log("ZSXQ_COOKIE environment variable not set!")
        sys.exit(1)

    log("Fetching zsxq topics...")
    topics = fetch_zsxq_topics(cookie)

    if topics:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(topics, f, ensure_ascii=False, indent=2)
        log("  Saved %d topics to %s" % (len(topics), args.output))
    else:
        log("  Failed to fetch topics")
        sys.exit(1)


if __name__ == "__main__":
    main()
