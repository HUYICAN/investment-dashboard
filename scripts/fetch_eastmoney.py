#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eastmoney A-share >=5% gain monitor with event tracking and AI attribution.

Fetches stocks with >=5% daily gain from Eastmoney API, tracks price events
(first break, continued rise, pullback, limit up), applies stock selection
framework ranking, performs AI attribution via keyword analysis cross-referenced
with feed_history.json, and outputs JSON for HTML injection.

Usage:
    env -u PYTHONHOME -u PYTHONPATH /Library/Developer/CommandLineTools/usr/bin/python3 \
        /Users/mac/.trae-cn/work/6a75e19f41c985bea5afc4d7/eastmoney_monitor.py
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import re
import os
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# Configuration
# ============================================================

STATE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "eastmoney_state.json")
FEED_HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "feed_history.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "eastmoney_5pct_latest.json")

EASTMONEY_URL = "http://push2.eastmoney.com/api/qt/clist/get"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# Beijing timezone
BJT = timezone(timedelta(hours=8))

# Tier sort order
TIER_ORDER = {
    "顶级弹性": 0,
    "稳健弹性": 1,
    "试错备选": 2,
    "观察": 3,
    "黑名单": 4,
}


# ============================================================
# Stock Selection Framework (duplicated from generate_workspace_v2.py)
# ============================================================

COMPANY_NAMES = [
    "药明康德", "寒武纪", "美光", "五洲特纸", "吉利德", "奕瑞科技",
    "海泰新光", "英矽智能", "小鹏", "长鑫存储", "长川科技", "台积电",
    "任天堂", "商汤", "隆基绿能", "闻泰科技", "紫光国微", "宁德时代",
    "京东方", "立讯精密", "迈瑞医疗", "联瑞新材", "盛科通信", "英特尔",
    "山东威达", "海力士", "中芯国际", "华虹半导体", "韦尔股份", "兆易创新",
    "圣邦股份", "汇川技术", "阳光电源", "通威股份", "恒瑞医药", "百济神州",
    "信达生物", "药明生物", "康龙化成", "泰格医药", "凯莱英", "博腾股份",
    "九洲药业", "昭衍新药", "特变电工", "思源电气", "中际旭创", "新易盛",
    "天孚通信", "光迅科技", "华工科技", "联影医疗", "开立医疗", "澳华内镜",
    "海光信息", "景嘉微", "澜起科技", "江丰电子", "北方华创", "中微公司",
    "拓荆科技", "华海清科", "芯源微", "富创精密", "正帆科技",
]

# 9 mandatory threshold keywords
THRESHOLD_KEYWORDS = {
    "业绩拐点": ["业绩拐点", "困境反转", "扭亏", "环比改善", "环比上行", "环比提升", "盈利改善"],
    "订单充足": ["订单", "中标", "合同", "签约", "在手订单"],
    "产能利用率": ["产能利用率", "产能爬坡", "产能提升", "满产", "满载"],
    "毛利率修复": ["毛利率", "毛利改善", "毛利提升", "毛利率修复", "毛利率上行"],
    "盈利能力": ["盈利", "利润", "净利", "归母", "扣非"],
    "隐形龙头": ["龙头", "领先", "第一梯队", "隐形冠军", "市占率", "行业排名"],
    "大客户定点": ["大客户", "供应链", "定点", "绑定", "供应商", "核心客户"],
    "国产替代": ["国产替代", "替代", "自主可控", "国产化"],
    "政策扶持": ["政策", "补贴", "扶持", "支持", "降税", "减税"],
}

# 18 bonus items with keyword patterns
BONUS_ITEMS = [
    ("上下游行业景气上行", ["景气", "上行", "回暖", "复苏", "向好"]),
    ("核心产品涨价", ["涨价", "提价", "价格上调", "反内卷", "价格回升"]),
    ("行业供需缺口扩大", ["供需缺口", "供不应求", "缺货", "紧缺", "缺口"]),
    ("海外业务占比提升", ["海外", "出口", "出海", "国际化", "境外"]),
    ("新技术0-1低渗透", ["0-1", "渗透率", "初创", "起步", "导入期", "早期"]),
    ("6个月新建产能投产", ["投产", "达产", "量产", "扩产", "新建产能", "产能投放"]),
    ("第二增长曲线新品", ["第二曲线", "新品", "新产品", "新业务", "验证完毕", "即将出货"]),
    ("切入高景气赛道", ["切入", "进军", "布局", "转型", "拓展"]),
    ("新技术迭代突破", ["迭代", "性能领先", "大幅领先", "代际"]),
    ("行业巨头一级供应商", ["一级供应商", "定点", "进入供应链", "大客户", "绑定", "核心供应商"]),
    ("资产重组推进", ["重组", "资产注入", "并购", "收购", "兼并"]),
    ("实控人变更", ["实控人变更", "控股股东变更", "控制权"]),
    ("优质资产借壳预期", ["借壳", "壳资源", "注入预期"]),
    ("跨界切入热门赛道", ["跨界", "转型", "新赛道", "切入"]),
    ("技术路线领先", ["技术领先", "路线领先", "壁垒", "护城河", "技术优势"]),
    ("同行扩产受限", ["同行", "竞争格局", "份额提升", "替代", "出清"]),
    ("行业1年内爆发期", ["爆发", "拐点", "元年", "起量", "快速增长"]),
    ("技术关键突破", ["突破", "研发成功", "首创", "专利", "认证", "获批"]),
]

# Blacklist keywords
BLACKLIST_PATTERNS = {
    "催化超6个月": ["2027年", "2028年", "远期", "长期才能", "尚需时日"],
    "纯概念无实质": ["纯概念", "题材", "蹭概念", "仅概念"],
    "毛利率下行": ["毛利率下行", "毛利率下滑", "毛利率下降", "毛利率承压"],
    "衰退赛道": ["衰退", "下行周期", "产能过剩", "过剩", "去产能"],
}


def score_stock_selection(text):
    """Apply stock selection framework to a text passage about a company.

    Returns: dict with threshold_count, bonus_score, bonus_items,
             blacklist_hits, threshold_hits, tier.
    """
    # Check 9 mandatory thresholds (how many are mentioned)
    threshold_hits = []
    for name, keywords in THRESHOLD_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            threshold_hits.append(name)
    threshold_count = len(threshold_hits)

    # Check 18 bonus items
    bonus_items_hit = []
    for name, keywords in BONUS_ITEMS:
        if any(kw in text for kw in keywords):
            bonus_items_hit.append(name)
    bonus_score = len(bonus_items_hit)

    # Check blacklist
    blacklist_hits = []
    for name, keywords in BLACKLIST_PATTERNS.items():
        if any(kw in text for kw in keywords):
            blacklist_hits.append(name)

    # Determine tier
    if blacklist_hits:
        tier = "黑名单"
    elif bonus_score >= 14 and threshold_count >= 5:
        tier = "顶级弹性"
    elif bonus_score >= 11 and threshold_count >= 3:
        tier = "稳健弹性"
    elif threshold_count >= 2:
        tier = "试错备选"
    else:
        tier = "观察"

    return {
        "threshold_count": threshold_count,
        "threshold_hits": threshold_hits,
        "bonus_score": bonus_score,
        "bonus_items": bonus_items_hit,
        "blacklist_hits": blacklist_hits,
        "tier": tier,
    }


def generate_basic_selection(stock, industry_info, ind_rank=0, ind_total=0):
    """Generate selection scoring for stocks NOT found in feed posts.

    Uses market cap tiering + industry rank to produce DIFFERENTIATED bonus
    items for each stock. Stocks in the same sector but with different market
    caps or ranks will get different bonus items.

    Returns: dict with same structure as score_stock_selection().
    """
    threshold_hits = []
    bonus_items_hit = []
    blacklist_hits = []

    # ---- Extract all available market data ----
    market_cap = stock.get("market_cap", 0)
    turnover_rate = stock.get("turnover_rate", 0)
    netflow = stock.get("netflow", 0)
    amplitude = stock.get("amplitude", 0)
    change = stock.get("change", 0)
    turnover_yuan = stock.get("turnover_yuan", 0)
    price = stock.get("price", 0)
    high = stock.get("high", 0)

    ind_count = industry_info.get("count", 0) if industry_info else 0
    ind_level = industry_info.get("level", "") if industry_info else ""
    ind_avg = industry_info.get("avg_change", 0) if industry_info else 0

    # ---- Derived metrics ----
    turnover_yi = turnover_yuan / 1e8 if turnover_yuan else 0.0
    at_high = (high > 0 and price >= high * 0.99)
    outperform = change > ind_avg + 3
    is_top1 = (ind_rank == 1 and ind_total >= 3)
    is_top3 = (1 <= ind_rank <= 3 and ind_total >= 5)

    # ---- Determine market cap tier ----
    if market_cap <= 25:
        cap_tier = "micro"
    elif market_cap <= 50:
        cap_tier = "small"
    elif market_cap <= 100:
        cap_tier = "mid"
    elif market_cap <= 200:
        cap_tier = "mid_large"
    elif market_cap <= 500:
        cap_tier = "large"
    else:
        cap_tier = "mega"

    # ---- 8 Mandatory Thresholds ----
    if 40 <= market_cap <= 280:
        threshold_hits.append("隐形龙头(市值达标)")
    if ind_count >= 5:
        threshold_hits.append("政策扶持(板块共振)")
    if netflow >= 1.5:
        threshold_hits.append("盈利能力(主力认可)")
    if turnover_rate >= 10 and change >= 8:
        threshold_hits.append("业绩拐点(资金活跃)")
    if 50 <= market_cap <= 300 and netflow >= 1.0:
        threshold_hits.append("大客户定点(资金青睐)")
    if 30 <= market_cap <= 150 and outperform:
        threshold_hits.append("国产替代(细分突破)")
    if turnover_yi >= 5 and change >= 7:
        threshold_hits.append("订单充足(放量上攻)")
    if turnover_rate >= 15 and change >= 7:
        threshold_hits.append("产能利用率(高换手)")
    threshold_count = len(threshold_hits)

    # ---- 18 Bonus Items: differentiated by cap tier + rank + metrics ----

    # === Sector-wide items (available to all, but rank-modulated) ===
    # 1. 上下游行业景气上行: 板块>=5只且均涨>=12%
    if ind_count >= 5 and ind_avg >= 12:
        bonus_items_hit.append("上下游行业景气上行")
    # 8. 切入高景气赛道: 热门板块+板块>=5只
    if ind_level == "热门" and ind_count >= 5:
        bonus_items_hit.append("切入高景气赛道")
    # 17. 行业1年内爆发期: 板块>=8只
    if ind_count >= 8:
        bonus_items_hit.append("行业1年内爆发期")

    # === Rank-based items (only top performers get these) ===
    # 18. 技术关键突破: 板块第1名+涨幅>=10%
    if is_top1 and change >= 10:
        bonus_items_hit.append("技术关键突破")
    # 9. 新技术迭代突破: 板块前3名+涨幅>=12%+接近最高价
    elif is_top3 and change >= 12 and at_high:
        bonus_items_hit.append("新技术迭代突破")

    # === Market-cap-specific items (different items for different cap tiers) ===
    if cap_tier == "micro":
        # 13. 优质资产借壳预期: 微盘+涨幅>=10%
        if change >= 10:
            bonus_items_hit.append("优质资产借壳预期")
        # 12. 实控人变更: 换手>=30%
        if turnover_rate >= 30:
            bonus_items_hit.append("实控人变更")
        # 5. 新技术0-1低渗透: 换手>=20%
        if turnover_rate >= 20:
            bonus_items_hit.append("新技术0-1低渗透")
        # 14. 跨界切入热门赛道: 板块<=2只+涨幅>=10%
        if ind_count <= 2 and change >= 10:
            bonus_items_hit.append("跨界切入热门赛道")

    elif cap_tier == "small":
        # 7. 第二增长曲线新品: 振幅>=12%
        if amplitude >= 12:
            bonus_items_hit.append("第二增长曲线新品")
        # 5. 新技术0-1低渗透: 换手>=20%
        if turnover_rate >= 20:
            bonus_items_hit.append("新技术0-1低渗透")
        # 16. 同行扩产受限: 跑赢板块
        if outperform:
            bonus_items_hit.append("同行扩产受限")
        # 14. 跨界切入热门赛道: 板块<=2只
        if ind_count <= 2 and change >= 10 and netflow >= 0.5:
            bonus_items_hit.append("跨界切入热门赛道")

    elif cap_tier == "mid":
        # 7. 第二增长曲线新品: 振幅>=12%
        if amplitude >= 12:
            bonus_items_hit.append("第二增长曲线新品")
        # 6. 6个月新建产能投产: 涨幅>=15%
        if change >= 15:
            bonus_items_hit.append("6个月新建产能投产")
        # 16. 同行扩产受限: 跑赢板块
        if outperform:
            bonus_items_hit.append("同行扩产受限")
        # 15. 技术路线领先: 净流入>=1亿+振幅>=10%
        if netflow >= 1.0 and amplitude >= 10:
            bonus_items_hit.append("技术路线领先")

    elif cap_tier == "mid_large":
        # 6. 6个月新建产能投产: 涨幅>=15%
        if change >= 15:
            bonus_items_hit.append("6个月新建产能投产")
        # 10. 行业巨头一级供应商: 净流入>=2亿
        if netflow >= 2.0:
            bonus_items_hit.append("行业巨头一级供应商")
        # 2. 核心产品涨价: 净流入>=3亿+涨幅>=10%
        if netflow >= 3.0 and change >= 10:
            bonus_items_hit.append("核心产品涨价")
        # 15. 技术路线领先: 净流入>=1.5亿+振幅>=10%
        if netflow >= 1.5 and amplitude >= 10:
            bonus_items_hit.append("技术路线领先")

    elif cap_tier == "large":
        # 4. 海外业务占比提升: 净流入>=1亿
        if netflow >= 1.0:
            bonus_items_hit.append("海外业务占比提升")
        # 10. 行业巨头一级供应商: 净流入>=2.5亿
        if netflow >= 2.5:
            bonus_items_hit.append("行业巨头一级供应商")
        # 2. 核心产品涨价: 净流入>=3亿+涨幅>=10%
        if netflow >= 3.0 and change >= 10:
            bonus_items_hit.append("核心产品涨价")
        # 15. 技术路线领先: 净流入>=1.5亿+振幅>=10%
        if netflow >= 1.5 and amplitude >= 10:
            bonus_items_hit.append("技术路线领先")

    elif cap_tier == "mega":
        # 4. 海外业务占比提升: 净流入>=1亿
        if netflow >= 1.0:
            bonus_items_hit.append("海外业务占比提升")
        # 2. 核心产品涨价: 净流入>=3亿+涨幅>=10%
        if netflow >= 3.0 and change >= 10:
            bonus_items_hit.append("核心产品涨价")
        # 10. 行业巨头一级供应商: 净流入>=2.5亿
        if netflow >= 2.5:
            bonus_items_hit.append("行业巨头一级供应商")

    # === Event-based items ===
    # 11. 资产重组推进: 涨停>=19.5%
    if change >= 19.5:
        bonus_items_hit.append("资产重组推进")
    # 3. 行业供需缺口扩大: 振幅>=18% (very high, only extreme volatility)
    if amplitude >= 18:
        bonus_items_hit.append("行业供需缺口扩大")

    bonus_score = len(bonus_items_hit)

    # ---- Blacklist ----
    if market_cap < 30 and turnover_rate > 25:
        blacklist_hits.append("纯概念无实质")
    if market_cap < 40 and netflow < -0.5:
        blacklist_hits.append("衰退赛道")

    # ---- Tier ----
    if blacklist_hits:
        tier = "黑名单"
    elif bonus_score >= 14 and threshold_count >= 5:
        tier = "顶级弹性"
    elif bonus_score >= 11 and threshold_count >= 3:
        tier = "稳健弹性"
    elif threshold_count >= 2:
        tier = "试错备选"
    else:
        tier = "观察"

    return {
        "threshold_count": threshold_count,
        "threshold_hits": threshold_hits,
        "bonus_score": bonus_score,
        "bonus_items": bonus_items_hit,
        "blacklist_hits": blacklist_hits,
        "tier": tier,
    }


def extract_key_catalyst(company, texts, selection):
    """Extract the key catalyst/reason from feed posts for a company.

    Finds the sentence with the most catalyst keywords and returns it as
    a concise summary.
    """
    catalyst_keywords = [
        "禁令", "裁定", "判决", "法院",
        "涨价", "提价", "反内卷", "价格回升",
        "订单", "中标", "签约", "合同",
        "投产", "达产", "量产", "产能",
        "突破", "研发成功", "获批", "认证",
        "重组", "并购", "收购", "借壳",
        "业绩预增", "扭亏", "超预期", "大超预期",
        "国产替代", "替代",
        "大客户", "供应链", "定点", "绑定",
        "政策", "补贴", "放开", "取消限购",
        "新品", "新产品", "第二曲线",
        "0-1", "渗透率",
    ]

    best_sentence = ""
    best_score = -1

    for text in texts:
        sentences = re.split(r'[。！？\n；]', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            score = sum(1 for kw in catalyst_keywords if kw in sent)
            if company in sent:
                score += 2
            for th_name in selection["threshold_hits"]:
                th_keywords = THRESHOLD_KEYWORDS.get(th_name, [])
                if any(kw in sent for kw in th_keywords):
                    score += 1
            if score > best_score:
                best_score = score
                best_sentence = sent

    if len(best_sentence) > 80:
        best_sentence = best_sentence[:80] + "..."
    elif not best_sentence:
        if selection["bonus_items"]:
            best_sentence = selection["bonus_items"][0]
        elif selection["threshold_hits"]:
            best_sentence = selection["threshold_hits"][0]
        else:
            best_sentence = "-"

    return best_sentence


# ============================================================
# Helper Functions
# ============================================================

def safe_float(val, default=0.0):
    """Safely convert API value to float, handling '-' and None."""
    if val is None or val == "-" or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_str(val, default=""):
    """Safely convert API value to string."""
    if val is None or val == "-" or val == "":
        return default
    return str(val).strip()


def clean_stock_name(name):
    """Remove common suffixes/prefixes from stock names for matching."""
    if not name:
        return name
    result = name
    # Remove suffixes
    for suffix in ["-U", "-W", "-H", "-B"]:
        if result.endswith(suffix):
            result = result[:-len(suffix)]
            break
    result = result.strip()
    # Remove ST prefix
    for prefix in ["*ST", "ST"]:
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    result = result.strip()
    # Remove N/C prefix (new listing)
    for prefix in ["N ", "C "]:
        if result.startswith(prefix):
            result = result[len(prefix):]
            break
    return result.strip()


def format_turnover(yuan):
    """Format turnover in yuan to readable string."""
    if yuan is None or yuan == 0:
        return "0"
    if yuan >= 1e8:
        return "%.2f亿" % (yuan / 1e8)
    elif yuan >= 1e4:
        return "%.2f万" % (yuan / 1e4)
    else:
        return "%.0f" % yuan


def format_market_cap(yuan):
    """Format market cap in yuan to readable number (in 亿)."""
    if yuan is None or yuan == 0:
        return 0.0
    return round(yuan / 1e8, 2)


# ============================================================
# Market Hours Check
# ============================================================

def check_market_status():
    """Check if A-share market is currently open (Beijing time).

    Morning: 9:00-11:30, Afternoon: 13:00-15:00, weekdays only.
    """
    now = datetime.now(BJT)
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    if weekday >= 5:  # Saturday or Sunday
        return "closed"

    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute

    morning_start = 9 * 60       # 9:00
    morning_end = 11 * 60 + 30   # 11:30
    afternoon_start = 13 * 60   # 13:00
    afternoon_end = 15 * 60      # 15:00

    if morning_start <= current_minutes <= morning_end:
        return "open"
    elif afternoon_start <= current_minutes <= afternoon_end:
        return "open"
    else:
        return "closed"


# ============================================================
# Eastmoney API
# ============================================================

def _fetch_eastmoney_page(page_num):
    """Fetch a single page from Eastmoney push2 API.

    Uses urllib.request with User-Agent header.
    Retries up to 2 times on transient errors.
    Returns list of stock item dicts (empty on failure).
    """
    params = (
        "pn=%d&pz=500&po=1&np=1&fltt=2&invt=2&fid=f3" % page_num
        + "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        + "&fields=f2,f3,f4,f5,f6,f7,f8,f12,f14,f15,f16,f17,f18,f20,f21,f62,f100,f128"
    )
    url = EASTMONEY_URL + "?" + params

    max_retries = 2
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Referer", "https://quote.eastmoney.com/")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                diff = data.get("data", {}).get("diff", [])
                return diff if diff else []
        except urllib.error.URLError as e:
            if attempt < max_retries:
                import time
                time.sleep(1)
                continue
            print("[ERROR] Network error fetching page %d (after %d retries): %s" % (
                page_num, max_retries, str(e)))
            return []
        except json.JSONDecodeError as e:
            if attempt < max_retries:
                import time
                time.sleep(1)
                continue
            print("[ERROR] JSON decode error on page %d (after %d retries): %s" % (
                page_num, max_retries, str(e)))
            return []
        except Exception as e:
            if attempt < max_retries:
                import time
                time.sleep(1)
                continue
            print("[ERROR] Unexpected error on page %d (after %d retries): %s" % (
                page_num, max_retries, str(e)))
            return []
    return []


def fetch_eastmoney_data():
    """Fetch A-share stock data from Eastmoney push2 API with pagination.

    The API caps at 100 items per page regardless of pz value.
    Fetches multiple pages (sorted by change% descending) until all stocks
    with change >= 5% are collected or max pages reached.

    Returns list of stock item dicts (all with change >= 5%).
    Returns None on complete API failure (page 1 returned nothing).
    Returns [] when API works but no stocks have >= 5% gain.
    """
    all_items = []
    max_pages = 15  # Safety limit: 15 pages x 100 = 1500 stocks
    api_succeeded = False

    for page_num in range(1, max_pages + 1):
        page_items = _fetch_eastmoney_page(page_num)
        if not page_items:
            break

        api_succeeded = True

        # Check if any items on this page have change < 5%
        has_below_threshold = False
        for item in page_items:
            change = safe_float(item.get("f3"))
            if change >= 5.0:
                all_items.append(item)
            else:
                has_below_threshold = True

        if has_below_threshold:
            break

        # If we got fewer than 100 items, we've reached the end
        if len(page_items) < 100:
            break

        print("  Page %d: %d items (all >= 5%%), fetching next page..." % (
            page_num, len(page_items)
        ))

    # If API never returned any data, signal failure
    if not api_succeeded:
        return None
    return all_items


def parse_stock_item(item):
    """Parse a single stock item from Eastmoney API response.

    Returns dict with normalized fields.
    Industry is sourced from f100 (available in clist/get endpoint),
    falling back to f128 if f100 is empty.
    """
    code = safe_str(item.get("f12"))
    name = safe_str(item.get("f14"))
    # f100 has industry in clist/get endpoint; f128 often returns "-"
    industry = safe_str(item.get("f100"))
    if not industry or industry == "-":
        industry = safe_str(item.get("f128"), "其他")
        if industry == "-" or not industry:
            industry = "其他"

    turnover_yuan = safe_float(item.get("f6"))
    netflow_yuan = safe_float(item.get("f62"))
    total_mktcap_yuan = safe_float(item.get("f20"))

    return {
        "code": code,
        "name": name,
        "price": safe_float(item.get("f2")),
        "change": safe_float(item.get("f3")),
        "change_amt": safe_float(item.get("f4")),
        "volume": safe_float(item.get("f5")),
        "turnover_yuan": turnover_yuan,
        "amplitude": safe_float(item.get("f7")),
        "turnover_rate": safe_float(item.get("f8")),
        "high": safe_float(item.get("f15")),
        "low": safe_float(item.get("f16")),
        "open": safe_float(item.get("f17")),
        "prev_close": safe_float(item.get("f18")),
        "total_mktcap_yuan": total_mktcap_yuan,
        "circ_mktcap_yuan": safe_float(item.get("f21")),
        "netflow_yuan": netflow_yuan,
        "industry": industry,
        # Derived display fields
        "market_cap": format_market_cap(total_mktcap_yuan),
        "netflow": round(netflow_yuan / 1e8, 2) if netflow_yuan else 0.0,
    }


# ============================================================
# State Management
# ============================================================

def load_state():
    """Load previous state from state file.

    Returns dict with 'update_time' and 'stocks' keys, or empty dict.
    """
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            state = json.load(f)
        return state
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return {}
    except Exception:
        return {}


def save_state(state):
    """Save current state to state file."""
    try:
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print("[WARN] Failed to save state: %s" % str(e))
        return False


def load_cached_output():
    """Try to load previously generated output as fallback."""
    try:
        with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return None
    except Exception:
        return None


# ============================================================
# Event Detection
# ============================================================

def is_20pct_board(code):
    """Check if stock is on a 20% limit board (ChiNext or STAR Market).

    ChiNext (创业板): codes starting with 300/301
    STAR Market (科创板): codes starting with 688/689
    """
    if not code:
        return False
    return code.startswith(("300", "301", "688", "689"))


def determine_event(code, change, price, prev_stocks):
    """Determine the price event for a stock based on current and previous state.

    Events (in priority order):
    1. 涨停 - change >= 9.8% (10% board) or >= 19.5% (20% board)
    2. 明显回落 - was >= 9.5% before and dropped > 3 percentage points
    3. 首次突破 - newly appeared (not in prev state) and change >= 5%
    4. 继续拉升 - was in prev state and price increased
    5. 强势异动 - default for all others >= 5%
    """
    # 1. Check limit up first (highest priority)
    limit_threshold = 19.5 if is_20pct_board(code) else 9.8
    if change >= limit_threshold:
        return "涨停"

    # 2. Check pullback from high
    prev_info = prev_stocks.get(code)
    if prev_info:
        prev_change = safe_float(prev_info.get("change"))
        if prev_change >= 9.5 and (prev_change - change) > 3.0:
            return "明显回落"

    # 3. Check new appearance
    if prev_info is None:
        if change >= 5.0:
            return "首次突破"

    # 4. Check continued rise
    if prev_info is not None:
        prev_price = safe_float(prev_info.get("price"))
        if price > prev_price:
            return "继续拉升"

    # 5. Default: strong anomaly
    return "强势异动"


# ============================================================
# Feed History
# ============================================================

def load_feed_history():
    """Load feed history from feed_history.json.

    Returns dict mapping date strings to lists of post dicts.
    """
    try:
        with open(FEED_HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return {}
    except Exception:
        return {}


def search_feed_for_stock(stock_name, feed_history):
    """Search feed history for posts mentioning the stock name.

    Tries both the full name and the cleaned name (without suffixes).
    Also checks against COMPANY_NAMES for fuzzy matching.

    Returns list of dicts with 'text', 'time', 'date' keys.
    """
    if not stock_name or len(stock_name) < 2:
        return []

    matching_posts = []
    seen_texts = set()

    # Build list of names to search for
    search_names = set()
    search_names.add(stock_name)

    clean_name = clean_stock_name(stock_name)
    if clean_name and clean_name != stock_name:
        search_names.add(clean_name)

    # Also check if the stock name matches any known company name
    for company in COMPANY_NAMES:
        if company in stock_name or stock_name in company:
            if len(company) >= 2:
                search_names.add(company)

    # Filter out very short names (< 2 chars) to avoid false matches
    search_names = {n for n in search_names if n and len(n) >= 2}

    if not search_names:
        return []

    for date_key, posts in feed_history.items():
        if not isinstance(posts, list):
            continue
        for post in posts:
            text = post.get("text", "")
            if not text:
                continue
            for name in search_names:
                if name in text:
                    # Use text hash to avoid duplicate posts
                    text_key = text[:200]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        matching_posts.append({
                            "text": text,
                            "time": post.get("time", ""),
                            "date": date_key,
                        })
                    break

    return matching_posts


# Industry keyword mapping for feed matching
INDUSTRY_FEED_KEYWORDS = {
    "医疗服务": ["药明", "CXO", "医药", "中报", "生物科技", "科研服务", "订单改善"],
    "生物制品": ["生物医药", "生物科技", "吉利德", "药明", "HIV"],
    "化学制药": ["医药", "中报", "业绩超预期", "制药"],
    "元件": ["美光", "DRAM", "NAND", "存储", "内存", "芯片", "PCB"],
    "半导体": ["寒武纪", "芯片", "AI", "算力", "CXMT", "YMTC", "存储"],
    "医疗器械": ["医疗", "内镜", "光学", "奕瑞", "海泰", "史赛克"],
    "化学制品": ["多晶硅", "反内卷", "涨价", "光伏", "硅料"],
    "消费电子": ["消费电子", "苹果"],
    "电子化学品Ⅱ": ["硅基", "半导体材料"],
    "专用设备": ["设备", "量产", "投产"],
}


def search_feed_for_industry(industry, feed_history):
    """Search feed history for posts relevant to an industry.

    Uses INDUSTRY_FEED_KEYWORDS to find posts that mention industry-specific
    keywords. Returns list of dicts with 'text', 'time', 'date' keys.
    """
    if not industry:
        return []

    keywords = INDUSTRY_FEED_KEYWORDS.get(industry, [])
    if not keywords:
        return []

    matching_posts = []
    seen_texts = set()

    for date_key, posts in feed_history.items():
        if not isinstance(posts, list):
            continue
        for post in posts:
            text = post.get("text", "")
            if not text:
                continue
            for kw in keywords:
                if kw in text:
                    text_key = text[:200]
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        matching_posts.append({
                            "text": text,
                            "time": post.get("time", ""),
                            "date": date_key,
                        })
                    break

    return matching_posts

def generate_attribution_from_feed(stock, feed_posts, selection):
    """Generate attribution text when stock is found in feed posts.

    Returns (cause, causeDetail) tuple.
    """
    name = stock["name"]
    change = stock["change"]
    industry = stock["industry"]

    # Combine all feed texts
    combined_text = " ".join(p["text"] for p in feed_posts)

    # Clean text for display
    clean_text = re.sub(r'<[^>]+>', '', combined_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    # Find the most relevant sentence for cause
    best_sentence = ""
    best_score = -1
    catalyst_kws = [
        "禁令", "裁定", "判决", "法院", "涨价", "提价", "反内卷",
        "订单", "中标", "签约", "合同", "投产", "达产", "量产",
        "突破", "获批", "认证", "重组", "并购", "收购",
        "业绩预增", "扭亏", "超预期", "国产替代", "政策", "补贴",
    ]

    for text in [p["text"] for p in feed_posts]:
        sentences = re.split(r'[。！？\n；]', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            score = sum(1 for kw in catalyst_kws if kw in sent)
            if name in sent:
                score += 2
            if score > best_score:
                best_score = score
                best_sentence = sent

    if not best_sentence:
        best_sentence = "近期资讯提及该股"

    # Truncate cause to ~60 chars
    cause_text = best_sentence
    if len(cause_text) > 60:
        cause_text = cause_text[:60] + "..."

    cause = "资讯驱动：%s" % cause_text

    # Detailed attribution
    post_count = len(feed_posts)
    latest_date = max(p.get("date", "") for p in feed_posts) if feed_posts else ""

    # Include selection info in detail
    tier = selection["tier"]
    threshold_hits = selection["threshold_hits"]
    bonus_items = selection["bonus_items"]

    detail_parts = [
        "近期%d篇资讯提及%s（最新日期：%s）" % (post_count, name, latest_date),
        "关键信息：%s" % clean_text[:200],
        "选股框架：%s（门槛%d/9，加分%d/18）" % (tier, selection["threshold_count"], selection["bonus_score"]),
    ]
    if threshold_hits:
        detail_parts.append("门槛命中：%s" % "、".join(threshold_hits[:5]))
    if bonus_items:
        detail_parts.append("加分项：%s" % "、".join(bonus_items[:5]))
    if selection["blacklist_hits"]:
        detail_parts.append("风险提示：%s" % "、".join(selection["blacklist_hits"]))

    causeDetail = " | ".join(detail_parts)

    return cause, causeDetail


def generate_attribution_basic(stock, industry_info, selection=None, ind_rank=0, ind_total=0):
    """Generate stock-specific attribution text when stock is NOT in feed posts.

    Includes: stock name, event type, specific metrics, industry rank,
    comparison to sector, and selection framework results.

    Returns (cause, causeDetail) tuple.
    """
    name = stock["name"]
    change = stock["change"]
    industry = stock["industry"]
    turnover_rate = stock["turnover_rate"]
    amplitude = stock["amplitude"]
    netflow = stock["netflow"]
    market_cap = stock["market_cap"]
    volume = stock["volume"]
    turnover_yuan = stock["turnover_yuan"]
    status = stock.get("status", "")

    # ---- Build concise cause (shown in table column) ----
    # Only show the KEY REASON, not redundant info (name/change/event already in other columns)
    cause_parts = []

    # Primary driver: industry resonance or individual
    if industry_info and industry_info["count"] >= 3:
        cause_parts.append("%s板块共振(%d只均涨%.1f%%)" % (
            industry, industry_info["count"], industry_info["avg_change"]
        ))
    elif industry_info and industry_info["count"] >= 2:
        cause_parts.append("%s板块走强" % industry)
    else:
        cause_parts.append("个股独立异动")

    # Secondary driver: capital or turnover
    if netflow >= 2.0:
        cause_parts.append("主力净流入%.1f亿" % netflow)
    elif turnover_rate >= 15:
        cause_parts.append("高换手%.1f%%" % turnover_rate)

    cause = "，".join(cause_parts)
    if len(cause) > 60:
        cause = cause[:60] + "..."

    # ---- Build detailed attribution (shown in detail popup) ----
    detail_parts = [
        "%s（%s）%s%.2f%%" % (name, stock.get("code", ""), status, change),
        "市值：%.1f亿 | 换手：%.1f%% | 振幅：%.1f%%" % (market_cap, turnover_rate, amplitude),
        "主力净流入：%.2f亿 | 成交额：%s" % (netflow, format_turnover(turnover_yuan)),
    ]

    # Industry rank and comparison
    if ind_rank > 0 and ind_total >= 3:
        outperform_pct = change - (industry_info["avg_change"] if industry_info else 0)
        detail_parts.append("行业排名：%s板块第%d/%d名，%s板块均值" % (
            industry, ind_rank, ind_total,
            "跑赢" if outperform_pct > 0 else "落后"
        ) + ("%.1f个百分点" % abs(outperform_pct) if outperform_pct != 0 else "持平"))

    if industry_info:
        detail_parts.append("板块共振：%s板块共%d只个股涨超5%%，平均涨幅%.1f%%，板块级别[%s]" % (
            industry, industry_info["count"], industry_info["avg_change"], industry_info.get("level", "")
        ))

    # Market cap description
    if market_cap > 500:
        detail_parts.append("市值区间：大盘股（>500亿）")
    elif market_cap > 200:
        detail_parts.append("市值区间：中大盘（200-500亿）")
    elif market_cap > 100:
        detail_parts.append("市值区间：中盘股（100-200亿）")
    elif market_cap > 50:
        detail_parts.append("市值区间：中小盘（50-100亿）")
    elif market_cap > 30:
        detail_parts.append("市值区间：小盘股（30-50亿）")
    else:
        detail_parts.append("市值区间：微盘股（<30亿）")

    # Selection framework results
    if selection:
        detail_parts.append("选股框架：%s（门槛%d/9，加分%d/18）" % (
            selection["tier"], selection["threshold_count"], selection["bonus_score"]
        ))
        if selection["threshold_hits"]:
            detail_parts.append("门槛命中：%s" % "、".join(selection["threshold_hits"]))
        if selection["bonus_items"]:
            detail_parts.append("加分项：%s" % "、".join(selection["bonus_items"]))
        if selection["blacklist_hits"]:
            detail_parts.append("风险提示：%s" % "、".join(selection["blacklist_hits"]))

    causeDetail = " | ".join(detail_parts)

    return cause, causeDetail


def generate_tags(stock, feed_posts, selection, event):
    """Generate tags for a stock based on feed content and price action."""
    tags = []

    # Event-based tags
    event_tags = {
        "涨停": "涨停",
        "首次突破": "首破5%",
        "继续拉升": "持续拉升",
        "明显回落": "高位回落",
        "强势异动": "强势异动",
    }
    tags.append(event_tags.get(event, "异动"))

    # Feed-based tags
    if feed_posts:
        combined_text = " ".join(p["text"] for p in feed_posts)

        # Add threshold hit tags
        for hit in selection["threshold_hits"][:3]:
            if hit not in tags:
                tags.append(hit)

        # Add top bonus items as tags
        for item in selection["bonus_items"][:3]:
            if item not in tags:
                tags.append(item)

        # Check for specific high-impact keywords
        high_impact_tags = [
            ("涨价", "涨价概念"),
            ("订单", "订单驱动"),
            ("投产", "产能投产"),
            ("突破", "技术突破"),
            ("重组", "重组概念"),
            ("国产替代", "国产替代"),
            ("政策", "政策受益"),
            ("出海", "出海概念"),
        ]
        for kw, tag in high_impact_tags:
            if kw in combined_text and tag not in tags:
                tags.append(tag)
    else:
        # Price action based tags
        if stock["netflow"] > 0.5:
            tags.append("主力净流入")
        if stock["turnover_rate"] > 10:
            tags.append("高换手")
        if stock["amplitude"] > 10:
            tags.append("高振幅")
        if stock["market_cap"] > 500:
            tags.append("大盘股")
        elif stock["market_cap"] < 50:
            tags.append("小盘股")

    # Industry tag
    industry = stock["industry"]
    if industry and industry != "其他" and industry not in tags:
        tags.append(industry)

    # Limit to 8 tags
    return tags[:8]


def generate_basic_catalyst(stock, industry_info, ind_rank=0, ind_total=0):
    """Generate concise key catalyst string when no feed data is available."""
    industry = stock["industry"]
    netflow = stock["netflow"]
    turnover_rate = stock["turnover_rate"]
    market_cap = stock["market_cap"]

    parts = []

    # Industry context (most important)
    if industry_info and industry_info["count"] >= 3:
        parts.append("%s板块%d只共振均涨%.1f%%" % (
            industry, industry_info["count"], industry_info["avg_change"]))
    elif ind_rank > 0 and ind_total >= 3:
        parts.append("%s板块第%d/%d名" % (industry, ind_rank, ind_total))
    else:
        parts.append("个股独立异动")

    # Key metric
    if netflow >= 2.0:
        parts.append("主力净流入%.1f亿" % netflow)
    elif turnover_rate >= 15:
        parts.append("换手%.1f%%" % turnover_rate)
    elif market_cap <= 50:
        parts.append("小盘股(%.0f亿)" % market_cap)

    result = "，".join(parts[:2])
    if len(result) > 60:
        result = result[:60] + "..."
    return result


def generate_core_event(stock, industry_info, ind_rank=0, ind_total=0,
                        feed_posts=None, industry_feed_posts=None):
    """Generate a stock-specific core event summary from last 7 days.

    Priority:
    1. Direct feed match: extract key event from posts mentioning this stock
    2. Industry feed match: find feed posts relevant to this stock's industry
    3. Fallback: summarize from market data
    """
    name = stock.get("name", "")
    industry = stock.get("industry", "")
    status = stock.get("status", "")
    change = stock.get("change", 0)
    netflow = stock.get("netflow", 0)
    turnover_rate = stock.get("turnover_rate", 0)

    # Event keywords for extracting key info from feed text
    EVENT_KW = [
        ("禁令", "法院禁令裁定"), ("裁定", "法院裁定"), ("判决", "法院判决"),
        ("反内卷", "反内卷倡议涨价"), ("涨价", "产品涨价"), ("提价", "产品提价"),
        ("订单", "订单改善"), ("中标", "中标"), ("签约", "签约落地"),
        ("投产", "产能投产"), ("达产", "产能达产"), ("量产", "量产突破"),
        ("突破", "技术突破"), ("获批", "获批"), ("认证", "获认证"),
        ("重组", "资产重组"), ("并购", "并购"), ("收购", "收购"),
        ("业绩预增", "业绩预增"), ("扭亏", "扭亏为盈"), ("超预期", "业绩超预期"),
        ("国产替代", "国产替代"), ("政策", "政策利好"),
        ("降息", "降息预期"), ("黄金", "央行增持黄金"),
        ("房地产", "房地产新政"),
    ]

    # ---- Priority 1: Direct feed match ----
    if feed_posts:
        combined = " ".join(p["text"] for p in feed_posts)
        for kw, label in EVENT_KW:
            if kw in combined:
                return "%s：%s" % (name, label)
        # Try to extract a key sentence containing the stock name
        sentences = re.split(r'[。！？\n；]', combined)
        for sent in sentences:
            sent = sent.strip()
            if name in sent and 10 < len(sent) <= 60:
                return "%s：%s" % (name, sent)

    # ---- Priority 2: Industry feed match ----
    # Use industry-relevant feed posts to extract the core event
    if industry_feed_posts:
        combined = " ".join(p["text"] for p in industry_feed_posts)
        ind_event = None
        for kw, label in EVENT_KW:
            if kw in combined:
                ind_event = label
                break
        if not ind_event:
            # Extract key sentence from industry feed
            sentences = re.split(r'[。！？\n；]', combined)
            for sent in sentences:
                sent = sent.strip()
                if 10 < len(sent) <= 50:
                    ind_event = sent
                    break
        if ind_event:
            # Append stock-specific metric for differentiation
            metric = ""
            if ind_rank == 1 and ind_total >= 3:
                metric = "，板块涨幅第1"
            elif netflow >= 3.0:
                metric = "，主力净流入%.1f亿" % netflow
            elif netflow >= 1.0:
                metric = "，主力净流入%.1f亿" % netflow
            elif turnover_rate >= 30:
                metric = "，换手%.0f%%" % turnover_rate
            elif change >= 100:
                metric = "，新股上市"
            return "%s：%s(行业)%s" % (name, ind_event, metric)

    # ---- Priority 3: Fallback from market data ----
    if status == "涨停":
        event = "涨停"
    elif status == "首次突破":
        event = "首破5%"
    elif status == "继续拉升":
        event = "拉升+%.1f%%" % change
    elif status == "明显回落":
        event = "回落至+%.1f%%" % change
    else:
        event = "+%.1f%%" % change

    ind_count = industry_info.get("count", 0) if industry_info else 0
    ind_avg = industry_info.get("avg_change", 0) if industry_info else 0

    context_parts = []
    if ind_count >= 5 and ind_avg > 0:
        context_parts.append("%s板块%d只齐涨均%.1f%%" % (industry, ind_count, ind_avg))
    elif ind_count >= 3:
        context_parts.append("%s板块%d只联动" % (industry, ind_count))

    if ind_rank == 1 and ind_total >= 3:
        context_parts.append("板块涨幅第1")
    elif netflow >= 3.0:
        context_parts.append("主力净流入%.1f亿" % netflow)
    elif netflow >= 1.0:
        context_parts.append("主力净流入%.1f亿" % netflow)
    elif turnover_rate >= 30:
        context_parts.append("换手%.0f%%" % turnover_rate)

    if change >= 100:
        context_parts.insert(0, "新股上市")

    context = "，".join(context_parts[:2]) if context_parts else "独立异动"
    return "%s：%s｜%s" % (name, event, context)


# ============================================================
# Industry Resonance
# ============================================================

def calculate_industry_resonance(stocks):
    """Calculate industry resonance by grouping stocks by industry.

    Returns list of dicts sorted by count (desc) then avg_change (desc).
    Each dict has: industry, count, avg_change, level.
    """
    industry_groups = {}

    for stock in stocks:
        industry = stock["industry"]
        if not industry or industry == "-":
            industry = "其他"
        if industry not in industry_groups:
            industry_groups[industry] = []
        industry_groups[industry].append(stock["change"])

    resonance = []
    for industry, changes in industry_groups.items():
        count = len(changes)
        avg_change = sum(changes) / count if count > 0 else 0

        # Determine level
        if count >= 5 or (count >= 3 and avg_change >= 10):
            level = "热门"
        elif count >= 3 or (count >= 2 and avg_change >= 8):
            level = "活跃"
        else:
            level = "一般"

        resonance.append({
            "industry": industry,
            "count": count,
            "avg_change": round(avg_change, 1),
            "level": level,
        })

    # Sort by count descending, then avg_change descending
    resonance.sort(key=lambda x: (-x["count"], -x["avg_change"]))

    return resonance


def get_industry_info(industry, resonance_list):
    """Look up industry info from resonance list.

    Returns the matching dict or None.
    """
    for r in resonance_list:
        if r["industry"] == industry:
            return r
    return None


# ============================================================
# Main Processing
# ============================================================

def process_and_output():
    """Main processing: fetch data, track events, generate attribution, output JSON."""

    now = datetime.now(BJT)
    market_status = check_market_status()

    print("=" * 60)
    print("Eastmoney A-share >=5% Gain Monitor")
    print("Time: %s | Market: %s" % (now.isoformat(), market_status))
    print("=" * 60)

    # 1. Fetch data from Eastmoney API (with pagination)
    print("\n[1/7] Fetching Eastmoney API data...")
    raw_items = fetch_eastmoney_data()

    if not raw_items:
        print("[WARN] API returned no data. Attempting to use cached output...")
        cached = load_cached_output()
        if cached:
            print("[OK] Using cached output from previous run.")
            print_summary(cached)
            return cached
        else:
            print("[ERROR] No cached data available. Cannot proceed.")
            return None

    # 2. Parse and filter stocks (change >= 5%)
    # fetch_eastmoney_data already filters for >= 5%, but we double-check here
    print("[2/7] Parsing stock data...")
    stocks = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        change = safe_float(item.get("f3"))
        if change >= 5.0:
            stock = parse_stock_item(item)
            if stock["code"]:
                stocks.append(stock)

    print("  Found %d stocks with >= 5%% gain" % len(stocks))

    if not stocks:
        print("[WARN] No stocks with >= 5% gain found. Saving empty output.")
        output = {
            "update_time": now.isoformat(),
            "market_status": market_status,
            "total_count": 0,
            "event_stats": {"首次突破": 0, "继续拉升": 0, "涨停": 0,
                            "明显回落": 0, "强势异动": 0},
            "industry_resonance": [],
            "records": [],
        }
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("[OK] Empty output saved to: %s" % OUTPUT_PATH)
        return output

    # 3. Load previous state
    print("[3/7] Loading previous state...")
    prev_state = load_state()
    prev_stocks = prev_state.get("stocks", {})
    print("  Previous state has %d stocks" % len(prev_stocks))

    # 4. Calculate industry resonance
    print("[4/7] Calculating industry resonance...")
    industry_resonance = calculate_industry_resonance(stocks)
    top_industries = [r for r in industry_resonance if r["level"] in ("热门", "活跃")][:5]
    if top_industries:
        print("  Top industries:")
        for r in top_industries:
            print("    %s: %d stocks, avg %.1f%% [%s]" % (
                r["industry"], r["count"], r["avg_change"], r["level"]
            ))

    # 4b. Compute industry rank for each stock (by change% within same industry)
    industry_rank_map = {}  # code -> (rank, total)
    industry_stock_groups = {}
    for s in stocks:
        ind = s.get("industry", "其他")
        if ind not in industry_stock_groups:
            industry_stock_groups[ind] = []
        industry_stock_groups[ind].append(s)
    for ind, ind_stocks in industry_stock_groups.items():
        ind_stocks.sort(key=lambda x: -x.get("change", 0))
        for rank, s in enumerate(ind_stocks, 1):
            industry_rank_map[s["code"]] = (rank, len(ind_stocks))
    print("  Industry ranks computed for %d stocks" % len(industry_rank_map))

    # 5. Load feed history
    print("[5/7] Loading feed history for AI attribution...")
    feed_history = load_feed_history()
    total_feed_posts = sum(len(v) for v in feed_history.values() if isinstance(v, list))
    print("  Feed history: %d dates, %d posts total" % (
        len(feed_history), total_feed_posts
    ))

    # 6. Process each stock
    print("[6/7] Processing stocks and generating attribution...")
    records = []
    event_stats = {"首次突破": 0, "继续拉升": 0, "涨停": 0, "明显回落": 0, "强势异动": 0}

    feed_match_count = 0

    for stock in stocks:
        code = stock["code"]
        name = stock["name"]
        change = stock["change"]
        price = stock["price"]

        # Determine event
        event = determine_event(code, change, price, prev_stocks)
        event_stats[event] = event_stats.get(event, 0) + 1
        stock["status"] = event

        # Search feed history for stock name
        feed_posts = search_feed_for_stock(name, feed_history)

        # Get industry info
        industry_info = get_industry_info(stock["industry"], industry_resonance)

        # Get industry rank
        rank_info = industry_rank_map.get(code, (0, 0))
        ind_rank = rank_info[0]
        ind_total = rank_info[1]

        # Generate attribution and selection
        if feed_posts:
            feed_match_count += 1
            combined_text = " ".join(p["text"] for p in feed_posts)
            selection = score_stock_selection(combined_text)
            key_catalyst = extract_key_catalyst(
                name, [p["text"] for p in feed_posts], selection
            )
            cause, causeDetail = generate_attribution_from_feed(
                stock, feed_posts, selection
            )
            tags = generate_tags(stock, feed_posts, selection, event)
        else:
            selection = generate_basic_selection(stock, industry_info, ind_rank, ind_total)
            key_catalyst = generate_basic_catalyst(stock, industry_info, ind_rank, ind_total)
            cause, causeDetail = generate_attribution_basic(stock, industry_info, selection, ind_rank, ind_total)
            tags = generate_tags(stock, [], selection, event)

        # Generate core event summary
        # Search for industry-relevant feed posts if no direct match
        industry_feed_posts = []
        if not feed_posts:
            industry_feed_posts = search_feed_for_industry(
                stock.get("industry", ""), feed_history
            )
        core_event = generate_core_event(
            stock, industry_info, ind_rank, ind_total,
            feed_posts, industry_feed_posts
        )

        # Build record
        record = {
            "code": code,
            "name": name,
            "price": round(price, 2),
            "change": round(change, 2),
            "status": event,
            "industry": stock["industry"],
            "turnover": format_turnover(stock["turnover_yuan"]),
            "turnover_yuan": int(stock["turnover_yuan"]) if stock["turnover_yuan"] else 0,
            "netflow": round(stock["netflow"], 2),
            "amplitude": round(stock["amplitude"], 1),
            "turnover_rate": round(stock["turnover_rate"], 1),
            "market_cap": stock["market_cap"],
            "cause": cause,
            "causeDetail": causeDetail,
            "tags": tags,
            "selection": {
                "tier": selection["tier"],
                "threshold_count": selection["threshold_count"],
                "bonus_score": selection["bonus_score"],
                "bonus_items": selection["bonus_items"],
                "threshold_hits": selection["threshold_hits"],
                "blacklist_hits": selection["blacklist_hits"],
            },
            "key_catalyst": key_catalyst,
            "core_event": core_event,
        }
        records.append(record)

    print("  Processed %d stocks, %d matched in feed" % (
        len(records), feed_match_count
    ))

    # 7. Sort records
    records.sort(key=lambda x: (
        TIER_ORDER.get(x["selection"]["tier"], 9),
        -x["selection"]["bonus_score"],
        -x["change"],
    ))

    # Save current state
    new_state = {
        "update_time": now.isoformat(),
        "stocks": {},
    }
    for stock in stocks:
        new_state["stocks"][stock["code"]] = {
            "name": stock["name"],
            "price": stock["price"],
            "change": stock["change"],
            "industry": stock["industry"],
        }
    save_state(new_state)
    print("[OK] State saved to: %s" % STATE_PATH)

    # Build output
    output = {
        "update_time": now.isoformat(),
        "market_status": market_status,
        "total_count": len(records),
        "event_stats": event_stats,
        "industry_resonance": industry_resonance,
        "records": records,
    }

    # Save output
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("[OK] Output saved to: %s" % OUTPUT_PATH)

    # Print summary
    print_summary(output)

    return output


def print_summary(output):
    """Print a summary of the monitoring results."""
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Update Time: %s" % output.get("update_time", "N/A"))
    print("Market Status: %s" % output.get("market_status", "N/A"))
    print("Total Stocks (>=5%%): %d" % output.get("total_count", 0))

    event_stats = output.get("event_stats", {})
    print("\nEvent Stats:")
    for event in ["涨停", "首次突破", "继续拉升", "明显回落", "强势异动"]:
        count = event_stats.get(event, 0)
        if count > 0:
            print("  %s: %d" % (event, count))

    resonance = output.get("industry_resonance", [])
    if resonance:
        print("\nTop Industries (by count):")
        for r in resonance[:10]:
            print("  %s: %d stocks, avg %.1f%% [%s]" % (
                r["industry"], r["count"], r["avg_change"], r["level"]
            ))

    records = output.get("records", [])
    if records:
        print("\nTop 10 Stocks (by ranking):")
        for i, rec in enumerate(records[:10]):
            tier = rec.get("selection", {}).get("tier", "?")
            bonus = rec.get("selection", {}).get("bonus_score", 0)
            print("  %d. %s(%s) %.2f%% [%s] %s | 门槛:%d 加分:%d | %s" % (
                i + 1,
                rec.get("name", ""),
                rec.get("code", ""),
                rec.get("change", 0),
                rec.get("status", ""),
                tier,
                rec.get("selection", {}).get("threshold_count", 0),
                bonus,
                rec.get("cause", "")[:50],
            ))

    print("\n" + "=" * 60)


# ============================================================
# Main Entry Point
# ============================================================

def main():
    """Main entry point for the Eastmoney monitor script."""
    try:
        process_and_output()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user.")
    except Exception as e:
        print("[ERROR] Unexpected error: %s" % str(e))
        import traceback
        traceback.print_exc()
        # Try to use cached output on any error
        print("[INFO] Attempting to use cached output...")
        cached = load_cached_output()
        if cached:
            print("[OK] Using cached output from previous run.")
            print_summary(cached)
        else:
            print("[ERROR] No cached data available.")


if __name__ == "__main__":
    main()
