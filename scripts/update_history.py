#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Update feed history JSON with new zsxq data.
Usage: python3 update_history.py <input_json>
Input JSON: array of {"text": "...", "time": "ISO8601", "title": "..."}
The script reads existing feed_history.json, adds/updates today's data, and saves.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "feed_history.json")

def clean(text):
    if not text:
        return ""
    try:
        from urllib.parse import unquote
        if '%' in text:
            text = unquote(text)
    except:
        pass
    text = re.sub(r'#\w+#$', '', text).strip()
    if text in ('#文字纪要#', '#音频#', '#外资研报#', '#文字观点#'):
        return ""
    return text

def is_valid(text):
    if not text or len(text.strip()) < 10:
        return False
    return True

def parse_date(time_str):
    """Parse ISO8601 time string, handling +0800 format (without colon)."""
    if not time_str:
        return None
    try:
        fixed = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', time_str)
        dt = datetime.fromisoformat(fixed)
        return dt.strftime("%Y-%m-%d")
    except:
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 update_history.py <input_json>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    
    with open(input_path, 'r', encoding='utf-8') as f:
        posts = json.load(f)
    
    clean_posts = []
    for p in posts:
        text = clean(p.get("text", ""))
        if not is_valid(text):
            continue
        clean_posts.append({
            "time": p.get("time", ""),
            "text": text,
            "title": p.get("title", "")
        })
    
    if not clean_posts:
        print("No valid posts to add")
        sys.exit(0)
    
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except:
        history = {}
    
    posts_by_date = {}
    for p in clean_posts:
        date_key = parse_date(p.get("time", ""))
        if not date_key:
            today = datetime.now(timezone(timedelta(hours=8)))
            date_key = today.strftime("%Y-%m-%d")
        if date_key not in posts_by_date:
            posts_by_date[date_key] = []
        posts_by_date[date_key].append(p)
    
    total_added = 0
    for date_key, date_posts in posts_by_date.items():
        existing_posts = history.get(date_key, [])
        existing_texts = set(p.get("text", "")[:200] for p in existing_posts)
        
        merged_posts = list(existing_posts)
        added = 0
        for p in date_posts:
            text_key = p.get("text", "")[:200]
            if text_key not in existing_texts:
                merged_posts.append(p)
                existing_texts.add(text_key)
                added += 1
        
        merged_posts.sort(key=lambda x: x.get("time", ""), reverse=True)
        history[date_key] = merged_posts
        total_added += added
        print("  %s: %d new posts (total %d)" % (date_key, added, len(merged_posts)))
    
    sorted_keys = sorted(history.keys(), reverse=True)
    if len(sorted_keys) > 90:
        for k in sorted_keys[90:]:
            del history[k]
    
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print("OK: %d new posts added (total %d days)" % (total_added, len(history)))

if __name__ == "__main__":
    main()
