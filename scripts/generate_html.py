#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate investment research workspace HTML with calendar + scoring system.
Scoring: 7-day catalyst (80pts) + company fundamentals (20pts) = 100pts total.
Priority: S(>=70), A(>=55), B(>=35), C(<35, filtered out).
"""

import json
import re
import html as html_module
from datetime import datetime, timezone, timedelta
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "..", "templates", "workspace.html")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "feed_history.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "touyan_workspace_final.html")
EASTMONEY_DATA_PATH = os.path.join(SCRIPT_DIR, "..", "data", "eastmoney_5pct_latest.json")
CLS_DATA_PATH = os.path.join(SCRIPT_DIR, "..", "data", "cls_telegraph.json")

# ============================================================
# SCORING ENGINE
# ============================================================

def score_novelty(post_time_str, now=None):
    """0-20: How new is this information."""
    if now is None:
        now = datetime.now(timezone(timedelta(hours=8)))
    try:
        post_time = datetime.fromisoformat(post_time_str)
        if post_time.tzinfo is None:
            post_time = post_time.replace(tzinfo=timezone(timedelta(hours=8)))
        delta_hours = (now - post_time).total_seconds() / 3600
    except:
        return 10

    if delta_hours < 6:
        return 20
    elif delta_hours < 24:
        return 18
    elif delta_hours < 48:
        return 15
    elif delta_hours < 72:
        return 12
    elif delta_hours < 168:
        return 8
    else:
        return 3


def score_surprise(text):
    """0-20: How much does this exceed market expectations."""
    score = 8  # baseline

    # Strong surprise keywords
    strong = ["大超预期", "远超", "大幅超预期", "超市场预期", "远超预期", "史无前例",
              "历史首次", "首次突破", "前所未有", "里程碑", "颠覆性", "革命性"]
    for kw in strong:
        if kw in text:
            score = max(score, 18)
            break

    # Medium surprise
    medium = ["超预期", "高于预期", "好于预期", "超出预期", "超预期表现", "上调",
              "上修", "大幅增长", "翻倍", "倍增", "创历史新高", "创纪录"]
    for kw in medium:
        if kw in text:
            score = max(score, 14)
            break

    # Sudden change indicators
    sudden = ["突然", "紧急", "意外", "临时", "突发", "黑天鹅", "暴雷", "暴跌",
              "闪崩", "熔断", "停牌", "重大事项", "重大变化", "重大更新", "重大突破"]
    for kw in sudden:
        if kw in text:
            score = max(score, 16)
            break

    # Court/legal/policy sudden changes
    legal = ["法院", "裁定", "禁令", "判决", "胜诉", "败诉", "列入", "移出",
             "制裁", "关税", "禁运", "出口管制", "实体清单", "黑名单"]
    for kw in legal:
        if kw in text:
            score = max(score, 15)
            break

    # Negative surprise (also important but different direction)
    negative = ["低于预期", "不及预期", "miss", "下调", "下修", "减少", "下滑",
                "亏损", "暴跌", "闪崩", "减持", "警示", "退市"]
    for kw in negative:
        if kw in text:
            score = max(score, 12)
            break

    # Already expected / no surprise
    expected = ["符合预期", "一如预期", "符合市场", "平稳", "常规", "例行"]
    for kw in expected:
        if kw in text:
            score = min(score, 5)
            break

    return min(score, 20)


def score_company_impact(text):
    """0-20: Direct impact on company revenue/profit/position."""
    score = 5  # baseline

    # Direct financial impact - very high
    direct_high = [
        ("订单", 18), ("中标", 18), ("大额合同", 18), ("签约", 16),
        ("量产", 18), ("投产", 17), ("达产", 16), ("产能扩张", 16),
        ("收购", 18), ("并购", 18), ("重组", 16), ("借壳", 15),
        ("回购", 14), ("增持", 14), ("定增", 13),
    ]
    for kw, val in direct_high:
        if kw in text:
            score = max(score, val)

    # Product/technology breakthrough
    tech = [
        ("突破", 16), ("研发成功", 16), ("技术领先", 14), ("打破垄断", 17),
        ("国产替代", 16), ("首创", 16), ("专利", 13), ("认证", 14),
        ("获批", 17), ("批准", 17), ("批件", 16), ("III期", 15),
        ("临床", 13), ("ANDA", 14), ("NDA", 14),
    ]
    for kw, val in tech:
        if kw in text:
            score = max(score, val)

    # Customer/supply chain
    customer = [
        ("大客户", 16), ("供应链", 14), ("进入", 13), ("供应商", 14),
        ("合作", 12), ("战略协议", 14), ("框架协议", 12),
    ]
    for kw, val in customer:
        if kw in text:
            score = max(score, val)

    # Price changes
    price = [
        ("涨价", 16), ("提价", 15), ("降价", 12), ("价格上调", 15),
        ("价格下调", 10), ("反内卷", 14), ("联合涨价", 16),
    ]
    for kw, val in price:
        if kw in text:
            score = max(score, val)

    # Performance changes
    perf = [
        ("业绩预增", 15), ("业绩大增", 16), ("扭亏", 15), ("盈利", 13),
        ("毛利率", 12), ("净利率", 12), ("收入增长", 12), ("利润增长", 13),
        ("翻倍以上", 16), ("同比+", 12),
    ]
    for kw, val in perf:
        if kw in text:
            score = max(score, val)

    # Policy impact
    policy = [
        ("政策", 13), ("补贴", 14), ("减税", 13), ("松绑", 15),
        ("放开", 14), ("取消限购", 16), ("降息", 14), ("降准", 13),
    ]
    for kw, val in policy:
        if kw in text:
            score = max(score, val)

    return min(score, 20)


def score_industry_spread(text):
    """0-20: Ability to spread to entire sector/industry."""
    score = 5  # baseline

    # Sector-wide impact
    sector_wide = [
        ("整个行业", 20), ("全行业", 19), ("产业链", 17), ("产业格局", 17),
        ("行业格局", 16), ("板块", 15), ("重新定价", 18), ("格局重塑", 17),
        ("反内卷", 16), ("联署", 15), ("联合", 14),
    ]
    for kw, val in sector_wide:
        if kw in text:
            score = max(score, val)

    # Multiple companies / industry trend
    multi = [
        ("八巨头", 17), ("多家企业", 15), ("头部企业", 14), ("主要企业", 13),
        ("龙头", 12), ("八大家", 16), ("前十大", 14),
    ]
    for kw, val in multi:
        if kw in text:
            score = max(score, val)

    # Macro/market-wide
    macro = [
        ("非农", 16), ("美联储", 17), ("降息", 16), ("加息", 15),
        ("央行", 16), ("黄金储备", 14), ("房地产新政", 17),
        ("出口管制", 16), ("制裁", 15), ("关税", 15),
    ]
    for kw, val in macro:
        if kw in text:
            score = max(score, val)

    # Multiple regions/markets
    regions = ["美国", "中国", "日本", "韩国", "澳大利亚", "印度", "香港", "台湾"]
    region_count = sum(1 for r in regions if r in text)
    if region_count >= 4:
        score = max(score, 16)
    elif region_count >= 2:
        score = max(score, 12)

    return min(score, 20)


def score_company_fundamentals(text):
    """0-20: Company fundamentals (auxiliary, 20% weight)."""
    score = 10  # default baseline

    # Financial metrics mentioned
    metrics = [
        ("PE", 3), ("估值", 3), ("市值", 3), ("净利润", 3), ("营收", 3),
        ("毛利率", 3), ("ROE", 3), ("市占率", 3), ("产能", 2), ("订单", 2),
    ]
    bonus = 0
    for kw, val in metrics:
        if kw in text:
            bonus += val
    score = min(score + bonus, 18)

    # Known strong companies
    leaders = ["寒武纪", "药明康德", "宁德时代", "台积电", "立讯精密", "迈瑞医疗",
               "隆基绿能", "紫光国微", "京东方", "闻泰科技"]
    for name in leaders:
        if name in text:
            score = min(score + 3, 20)
            break

    # Growth indicators
    growth = ["同比+", "环比+", "增长", "提升", "改善", "加速", "爆发"]
    growth_count = sum(1 for g in growth if g in text)
    if growth_count >= 3:
        score = min(score + 2, 20)

    return min(score, 20)


def apply_anti_inflation(text, novelty, surprise, impact, spread, fundamentals):
    """Anti-inflation filter: penalize generic claims without specific new catalysts.

    Per user rules, do NOT give high scores just because of:
    - "XX行业未来空间巨大" / "市场空间"
    - "公司属于XX概念"
    - "公司是XX龙头"
    - "机构看好"
    - "行业景气度高"
    - "过去涨停很多"
    - "长期逻辑很好"
    Unless these are accompanied by recent specific changes.
    """
    penalty = 0

    # Generic inflation triggers
    generic_phrases = [
        "未来空间", "空间巨大", "市场空间", "千亿市场", "万亿市场",
        "概念股", "概念板块", "属于.*概念",
        "龙头", "领军", "领军者",
        "机构看好", "看好", "推荐", "买入评级",
        "景气度高", "景气向上", "高景气",
        "涨停", "连板", "封板",
        "长期逻辑", "长期看好", "长期空间",
        "核心标的", "核心龙头", "优质标的",
        "护城河", "壁垒",
    ]

    generic_count = 0
    for phrase in generic_phrases:
        if ".*" in phrase:
            import re as _re
            if _re.search(phrase, text):
                generic_count += 1
        elif phrase in text:
            generic_count += 1

    # Specific catalyst indicators (if present, generic claims are less penalized)
    specific_catalysts = [
        "订单", "中标", "签约", "合同", "量产", "投产", "达产",
        "获批", "批准", "批件", "认证", "突破", "研发成功",
        "收购", "并购", "重组", "涨价", "提价",
        "法院", "裁定", "禁令", "判决",
        "政策", "补贴", "减税", "放开", "取消限购",
        "业绩预增", "扭亏", "大超预期", "超预期",
        "首次", "创纪录", "创历史新高", "里程碑",
    ]
    has_specific = any(kw in text for kw in specific_catalysts)

    # Apply penalty: if generic claims present but no specific catalysts
    if generic_count >= 2 and not has_specific:
        penalty = min(generic_count * 4, 15)
    elif generic_count >= 1 and not has_specific:
        penalty = min(generic_count * 3, 8)

    # Also check for "broker recommendation only" pattern (no hard events)
    broker_only = any(kw in text for kw in ["建议布局", "建议关注", "建议买入", "当前位置"])
    if broker_only and not has_specific:
        penalty = max(penalty, 10)

    # Apply penalty proportionally across catalyst components
    if penalty > 0:
        ratio = 1.0 - (penalty / 80.0)  # penalty as fraction of 80 catalyst points
        novelty = int(novelty * ratio)
        surprise = int(surprise * ratio)
        impact = int(impact * ratio)
        spread = int(spread * ratio)

    return novelty, surprise, impact, spread


def calculate_score(post, now=None):
    """Calculate total score and assign priority level.

    Scoring: 7-day catalyst (80pts, 4x20) + company fundamentals (20pts) = 100pts.
    Priority: S(>=65 + high novelty/surprise), A(>=50), B(>=35), C(<35, filtered).
    Anti-inflation filter penalizes generic claims without specific new events.
    """
    text = post.get("text", "")
    time_str = post.get("time", "")

    # 7-day catalyst: 80 points total (4 categories x 20)
    novelty = score_novelty(time_str, now)
    surprise = score_surprise(text)
    impact = score_company_impact(text)
    spread = score_industry_spread(text)

    # Apply anti-inflation filter
    novelty, surprise, impact, spread = apply_anti_inflation(
        text, novelty, surprise, impact, spread, 0
    )

    catalyst_score = novelty + surprise + impact + spread  # 0-80

    # Company fundamentals: 20 points
    fundamentals = score_company_fundamentals(text)

    # Final score: catalyst (0-80) + fundamentals (0-20) = 0-100
    total = catalyst_score + fundamentals

    # Determine priority based on qualitative criteria:
    # S: recent 1-3 days, clearly exceeds expectations, direct company impact,
    #    can change future performance, market hasn't fully traded
    # A: within 7 days, clear industry logic, substantial company impact
    # B: some impact but moderate catalyst
    # C: old news, pure concept, no clear beneficiary → filter
    if total >= 65 and (novelty >= 15 or surprise >= 15) and impact >= 12:
        priority = "S"
    elif total >= 50:
        priority = "A"
    elif total >= 35:
        priority = "B"
    else:
        priority = "C"

    return {
        "total": total,
        "priority": priority,
        "novelty": novelty,
        "surprise": surprise,
        "impact": impact,
        "spread": spread,
        "catalyst": catalyst_score,
        "fundamentals": fundamentals,
    }


# ============================================================
# STOCK SELECTION ENGINE (选股框架：8门槛+18加分+黑名单)
# ============================================================

# Company name list for extraction
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
    "兴森科技", "博迈科", "生益科技", "深南电路", "沪电股份", "鹏鼎控股",
    "蓝思科技", "领益智造", "赛力斯", "德赛西威", "科大讯飞", "海康威视",
    "万华化学", "紫金矿业", "福耀玻璃", "比亚迪", "长安汽车",
]

# Company -> industry mapping (overrides keyword-based sector detection)
COMPANY_SECTOR_MAP = {
    "药明康德": "医药/生物", "寒武纪": "半导体/AI芯片", "美光": "半导体/AI芯片",
    "五洲特纸": "消费/轻工", "吉利德": "医药/生物", "奕瑞科技": "医药/医疗器械",
    "海泰新光": "医药/医疗器械", "英矽智能": "医药/生物", "小鹏": "汽车/新能源",
    "长鑫存储": "半导体/AI芯片", "长川科技": "半导体/AI芯片", "台积电": "半导体/AI芯片",
    "任天堂": "消费/电子", "商汤": "科技/通信", "隆基绿能": "新能源/光伏",
    "闻泰科技": "半导体/AI芯片", "紫光国微": "半导体/AI芯片", "宁德时代": "新能源/锂电",
    "京东方": "科技/显示", "立讯精密": "消费/电子", "迈瑞医疗": "医药/医疗器械",
    "联瑞新材": "半导体/AI芯片", "盛科通信": "科技/通信", "英特尔": "半导体/AI芯片",
    "山东威达": "新能源/汽车", "海力士": "半导体/AI芯片", "中芯国际": "半导体/AI芯片",
    "华虹半导体": "半导体/AI芯片", "韦尔股份": "半导体/AI芯片", "兆易创新": "半导体/AI芯片",
    "圣邦股份": "半导体/AI芯片", "汇川技术": "工业/自动化", "阳光电源": "新能源/光伏",
    "通威股份": "新能源/光伏", "恒瑞医药": "医药/生物", "百济神州": "医药/生物",
    "信达生物": "医药/生物", "药明生物": "医药/生物", "康龙化成": "医药/生物",
    "泰格医药": "医药/生物", "凯莱英": "医药/生物", "博腾股份": "医药/生物",
    "九洲药业": "医药/生物", "昭衍新药": "医药/生物", "特变电工": "电力/设备",
    "思源电气": "电力/设备", "中际旭创": "科技/通信", "新易盛": "科技/通信",
    "天孚通信": "科技/通信", "光迅科技": "科技/通信", "华工科技": "科技/通信",
    "联影医疗": "医药/医疗器械", "开立医疗": "医药/医疗器械", "澳华内镜": "医药/医疗器械",
    "海光信息": "半导体/AI芯片", "景嘉微": "半导体/AI芯片", "澜起科技": "半导体/AI芯片",
    "江丰电子": "半导体/AI芯片", "北方华创": "半导体/AI芯片", "中微公司": "半导体/AI芯片",
    "拓荆科技": "半导体/AI芯片", "华海清科": "半导体/AI芯片", "芯源微": "半导体/AI芯片",
    "富创精密": "半导体/AI芯片", "正帆科技": "半导体/AI芯片",
    "兴森科技": "半导体/PCB", "博迈科": "能源/海工", "生益科技": "半导体/PCB",
    "深南电路": "半导体/PCB", "沪电股份": "半导体/PCB", "鹏鼎控股": "半导体/PCB",
    "蓝思科技": "消费/电子", "领益智造": "消费/电子", "赛力斯": "汽车/新能源",
    "德赛西威": "汽车/智能", "科大讯飞": "科技/通信", "海康威视": "科技/通信",
    "万华化学": "化工/材料", "紫金矿业": "有色/矿业", "福耀玻璃": "汽车/部件",
    "比亚迪": "汽车/新能源", "长安汽车": "汽车/新能源",
}

# 8 mandatory threshold keywords (check if mentioned in text)
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
    # 1. 供需与涨价 (高权重)
    ("上下游行业景气上行", ["景气", "上行", "回暖", "复苏", "向好"]),
    ("核心产品涨价", ["涨价", "提价", "价格上调", "反内卷", "价格回升"]),
    ("行业供需缺口扩大", ["供需缺口", "供不应求", "缺货", "紧缺", "缺口"]),
    ("海外业务占比提升", ["海外", "出口", "出海", "国际化", "境外"]),
    # 2. 产能落地 + 0-1第二增长曲线
    ("新技术0-1低渗透", ["0-1", "渗透率", "初创", "起步", "导入期", "早期"]),
    ("6个月新建产能投产", ["投产", "达产", "量产", "扩产", "新建产能", "产能投放"]),
    ("第二增长曲线新品", ["第二曲线", "新品", "新产品", "新业务", "验证完毕", "即将出货"]),
    ("切入高景气赛道", ["切入", "进军", "布局", "转型", "拓展"]),
    ("新技术迭代突破", ["迭代", "性能领先", "大幅领先", "代际"]),
    ("行业巨头一级供应商", ["一级供应商", "定点", "进入供应链", "大客户", "绑定", "核心供应商"]),
    # 3. 资本运作/重组 (强催化)
    ("资产重组推进", ["重组", "资产注入", "并购", "收购", "兼并"]),
    ("实控人变更", ["实控人变更", "控股股东变更", "控制权"]),
    ("优质资产借壳预期", ["借壳", "壳资源", "注入预期"]),
    ("跨界切入热门赛道", ["跨界", "转型", "新赛道", "切入"]),
    # 4. 竞争壁垒与外部催化
    ("技术路线领先", ["技术领先", "路线领先", "壁垒", "护城河", "技术优势"]),
    ("同行扩产受限", ["同行", "竞争格局", "份额提升", "替代", "出清"]),
    ("行业1年内爆发期", ["爆发", "拐点", "元年", "起量", "快速增长"]),
    ("技术关键突破", ["突破", "研发成功", "首创", "专利", "认证", "获批"]),
]

# Blacklist keywords
# Note: "催化超6个月" only triggers when text explicitly says the catalyst itself is delayed,
# NOT when future years appear in revenue projections or market forecasts.
BLACKLIST_PATTERNS = {
    "催化超6个月": ["2027年才能", "2028年才能", "远期才能兑现", "尚需时日", "短期内无法兑现", "落地在6个月后", "催化尚远"],
    "纯概念无实质": ["纯概念", "蹭概念", "仅概念"],
    "毛利率下行": ["毛利率下行", "毛利率下滑", "毛利率下降", "毛利率承压"],
    "衰退赛道": ["衰退赛道", "长期下行", "产能严重过剩", "深度去产能"],
}


def score_stock_selection(text):
    """Apply stock selection framework to a text passage about a company.
    
    Returns: dict with threshold_count, bonus_score, bonus_items, blacklist_hits, tier
    """
    # Check 8 mandatory thresholds (how many are mentioned)
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


def extract_key_catalyst(company, texts, selection):
    """Extract the key catalyst/reason from 7-day info for a company.
    
    Finds the sentence with the most catalyst keywords and returns it as a concise summary.
    """
    # Catalyst keywords to look for (ordered by importance)
    catalyst_keywords = [
        "禁令", "裁定", "判决", "法院",  # legal
        "涨价", "提价", "反内卷", "价格回升",  # price
        "订单", "中标", "签约", "合同",  # orders
        "投产", "达产", "量产", "产能",  # capacity
        "突破", "研发成功", "获批", "认证",  # tech
        "重组", "并购", "收购", "借壳",  # restructuring
        "业绩预增", "扭亏", "超预期", "大超预期",  # performance
        "国产替代", "替代",  # substitution
        "大客户", "供应链", "定点", "绑定",  # customer
        "政策", "补贴", "放开", "取消限购",  # policy
        "新品", "新产品", "第二曲线",  # new product
        "0-1", "渗透率",  # early stage
    ]

    best_sentence = ""
    best_score = -1

    for text in texts:
        # Split into sentences by Chinese punctuation
        sentences = re.split(r'[。！？\n；]', text)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 5:
                continue
            # Score sentence by catalyst keyword count
            score = sum(1 for kw in catalyst_keywords if kw in sent)
            # Bonus if sentence contains company name
            if company in sent:
                score += 2
            # Prefer sentences with threshold hits
            for th_name in selection["threshold_hits"]:
                th_keywords = THRESHOLD_KEYWORDS.get(th_name, [])
                if any(kw in sent for kw in th_keywords):
                    score += 1
            if score > best_score:
                best_score = score
                best_sentence = sent

    # Truncate to ~80 chars
    if len(best_sentence) > 80:
        best_sentence = best_sentence[:80] + "..."
    elif not best_sentence:
        # Fallback: use first bonus item or threshold hit
        if selection["bonus_items"]:
            best_sentence = selection["bonus_items"][0]
        elif selection["threshold_hits"]:
            best_sentence = selection["threshold_hits"][0]
        else:
            best_sentence = "-"

    return best_sentence


def extract_and_score_companies(feed_items):
    """Extract companies from feed items and score them using stock selection framework.
    
    Returns: list of dicts with company info and selection scores, sorted by score.
    """
    company_data = {}  # company_name -> {text, items, score_info}

    for item in feed_items:
        raw_text = html_module.unescape(item["text"].replace("<br>", " "))
        raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()

        for company in COMPANY_NAMES:
            if company in raw_text:
                if company not in company_data:
                    company_data[company] = {
                        "name": company,
                        "texts": [],
                        "primary_texts": [],
                        "items": [],
                        "sector": COMPANY_SECTOR_MAP.get(company, item["sector"]),
                    }
                company_data[company]["texts"].append(raw_text)
                # Track primary texts: company name appears in first 100 chars (main subject)
                if company in raw_text[:100]:
                    company_data[company]["primary_texts"].append(raw_text)
                company_data[company]["items"].append(item)

    # Score each company
    results = []
    for company, data in company_data.items():
        # Combine all text about this company
        combined_text = " ".join(data["texts"])
        selection = score_stock_selection(combined_text)

        # Skip blacklisted companies
        if selection["tier"] == "黑名单":
            continue
        # Skip companies with very low scores
        if selection["bonus_score"] == 0 and selection["threshold_count"] < 2:
            continue

        # Get the best item (highest score) for this company
        best_item = max(data["items"], key=lambda x: x["score"])

        # Extract key catalyst: prefer primary texts (company is main subject)
        primary = data.get("primary_texts", [])
        catalyst_texts = primary if primary else data["texts"]
        key_catalyst = extract_key_catalyst(company, catalyst_texts, selection)

        results.append({
            "name": company,
            "sector": data["sector"],
            "tier": selection["tier"],
            "threshold_count": selection["threshold_count"],
            "bonus_score": selection["bonus_score"],
            "bonus_items": selection["bonus_items"],
            "threshold_hits": selection["threshold_hits"],
            "best_score": best_item["score"],
            "best_priority": best_item["priority"],
            "time": best_item["time"],
            "key_catalyst": key_catalyst,
            "summary": combined_text[:100] + "..." if len(combined_text) > 100 else combined_text,
        })

    # Sort by tier priority, then bonus score, then threshold count
    tier_order = {"顶级弹性": 0, "稳健弹性": 1, "试错备选": 2, "观察": 3}
    results.sort(key=lambda x: (tier_order.get(x["tier"], 9), -x["bonus_score"], -x["threshold_count"]))

    return results


def extract_hot_stocks(feed_data, now, days=15):
    """Extract hot stocks from the past N days of feed data.

    Hot score = mention_count*10 + avg_score*2 + max_score + recency_bonus + S/A bonus.
    Returns: list of dicts with company info and hot scores, sorted by hot_score desc.
    """
    cutoff_str = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    company_stats = {}  # company_name -> stats dict

    for date_key, items in feed_data.items():
        if date_key < cutoff_str:
            continue

        for item in items:
            raw_text = html_module.unescape(item["text"].replace("<br>", " "))
            raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()

            for company in COMPANY_NAMES:
                if company in raw_text:
                    if company not in company_stats:
                        company_stats[company] = {
                            "name": company,
                            "sector": COMPANY_SECTOR_MAP.get(company, item["sector"]),
                            "mention_count": 0,
                            "total_score": 0,
                            "max_score": 0,
                            "s_count": 0,
                            "a_count": 0,
                            "last_date": date_key,
                            "first_date": date_key,
                            "texts": [],
                            "primary_texts": [],
                            "items": [],
                        }
                    stats = company_stats[company]
                    stats["mention_count"] += 1
                    stats["total_score"] += item["score"]
                    stats["max_score"] = max(stats["max_score"], item["score"])
                    if item["priority"] == "S":
                        stats["s_count"] += 1
                    elif item["priority"] == "A":
                        stats["a_count"] += 1
                    if date_key > stats["last_date"]:
                        stats["last_date"] = date_key
                    if date_key < stats["first_date"]:
                        stats["first_date"] = date_key
                    stats["texts"].append(raw_text)
                    if company in raw_text[:100]:
                        stats["primary_texts"].append(raw_text)
                    stats["items"].append(item)

    # Calculate hot scores and build results
    results = []
    for company, stats in company_stats.items():
        avg_score = stats["total_score"] / stats["mention_count"] if stats["mention_count"] > 0 else 0

        # Days since last mention
        try:
            last_dt = datetime.strptime(stats["last_date"], "%Y-%m-%d")
            days_since_last = (now.replace(tzinfo=None) - last_dt).days
        except:
            days_since_last = 0

        # Hot score: frequency + quality + peak + recency + priority bonus
        hot_score = (
            stats["mention_count"] * 10
            + avg_score * 2
            + stats["max_score"]
            + max(0, days - days_since_last) * 3
            + stats["s_count"] * 15
            + stats["a_count"] * 8
        )

        # Hot category
        if hot_score >= 80 or stats["mention_count"] >= 5:
            category = "近期大热"
        elif stats["mention_count"] >= 3 and hot_score >= 50:
            category = "持续活跃"
        elif days_since_last <= 3 and stats["mention_count"] >= 2:
            category = "新晋热门"
        else:
            category = "有所关注"

        # Extract key catalyst from primary texts
        primary = stats.get("primary_texts", [])
        catalyst_texts = primary if primary else stats["texts"]
        best_item = max(stats["items"], key=lambda x: x["score"])

        combined_text = " ".join(stats["texts"])
        selection = score_stock_selection(combined_text)
        key_catalyst = extract_key_catalyst(company, catalyst_texts, selection)

        summary = combined_text[:100] + "..." if len(combined_text) > 100 else combined_text

        results.append({
            "name": company,
            "sector": stats["sector"],
            "hot_score": round(hot_score),
            "mention_count": stats["mention_count"],
            "avg_score": round(avg_score),
            "max_score": stats["max_score"],
            "s_count": stats["s_count"],
            "a_count": stats["a_count"],
            "category": category,
            "last_date": stats["last_date"],
            "days_since_last": days_since_last,
            "key_catalyst": key_catalyst,
            "summary": summary,
            "best_priority": best_item["priority"],
            "best_score": best_item["score"],
        })

    results.sort(key=lambda x: -x["hot_score"])
    return results


# ============================================================
# SECTOR DETECTION
# ============================================================

SECTOR_KEYWORDS = {
    "半导体/AI芯片": ["寒武纪", "芯片", "半导体", "AI芯片", "算力", "GPU", "DRAM", "NAND", "存储"],
    "医药/生物": ["药明", "医药", "生物", "CXO", "创新药", "医疗", "HIV", "临床", "制药", "ADC", "CAR-T"],
    "新能源/光伏": ["光伏", "多晶硅", "新能源", "锂电", "储能", "逆变器", "电池"],
    "宏观/海外": ["非农", "美联储", "降息", "加息", "美股", "美债", "黄金", "美元", "失业率", "就业"],
    "房地产": ["房地产", "二手房", "限购", "房价", "公积金", "楼市"],
    "消费/轻工": ["消费", "轻工", "宠物", "食品"],
    "科技/通信": ["光通信", "CPO", "AI", "云厂商", "硅光", "PCB", "光学", "显示"],
    "金融": ["银行", "金融", "量化", "基金"],
    "商品/贵金属": ["黄金", "白银", "贵金属", "原油", "石油"],
}

def detect_sector(text):
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return sector
    return "综合"

def detect_sentiment(text):
    bear = ["下调", "下跌", "miss", "低于预期", "减持", "风险", "走弱", "跌", "看空", "偏空", "熊市"]
    bull = ["超预期", "上涨", "增长", "利好", "偏多", "看多", "建议", "布局", "增持", "突破", "回升", "改善"]
    b = sum(1 for w in bear if w in text)
    u = sum(1 for w in bull if w in text)
    if b > u:
        return "bear", "偏空"
    elif u > b:
        return "bull", "偏多"
    return "neutral", "中性"

def extract_companies(text):
    names = ["寒武纪", "药明康德", "美光", "五洲特纸", "吉利德", "奕瑞科技",
             "海泰新光", "英矽智能", "小鹏", "长鑫存储", "长川科技", "台积电", "任天堂", "商汤",
             "隆基绿能", "闻泰科技", "紫光国微", "宁德时代", "京东方", "立讯精密", "迈瑞医疗"]
    found = [n for n in names if n in text]
    return " \u00b7 ".join(found[:4]) if found else ""

def fmt_time(t):
    try:
        return datetime.fromisoformat(t).strftime("%H:%M")
    except:
        return t

def clean(text):
    if not text:
        return ""
    text = re.sub(r'#\w+#$', '', text).strip()
    return text

def is_valid(text):
    if not text or len(text.strip()) < 10:
        return False
    return True


# ============================================================
# HTML GENERATION
# ============================================================

def process_post(post, now=None):
    text = clean(post.get("text", ""))
    if not is_valid(text):
        return None

    score_info = calculate_score(post, now)

    t = fmt_time(post.get("time", ""))
    sector = detect_sector(text)
    cls, label = detect_sentiment(text)
    comps = extract_companies(text)
    esc = html_module.escape(text).replace("\n", "<br>")

    return {
        "time": t,
        "fullTime": post.get("time", ""),
        "sentiment": cls,
        "sentimentLabel": label,
        "sector": sector,
        "companies": comps,
        "text": esc,
        "score": score_info["total"],
        "priority": score_info["priority"],
        "novelty": score_info["novelty"],
        "surprise": score_info["surprise"],
        "impact": score_info["impact"],
        "spread": score_info["spread"],
        "catalyst": score_info["catalyst"],
        "fundamentals": score_info["fundamentals"],
    }


PRIORITY_COLORS = {
    "S": "#ef4444",
    "A": "#f97316",
    "B": "#3b82f6",
}

PRIORITY_LABELS = {
    "S": "S\u7ea7\u00b7\u91cd\u5927\u50ac\u5316",
    "A": "A\u7ea7\u00b7\u5f3a\u50ac\u5316",
    "B": "B\u7ea7\u00b7\u6709\u6548\u4fe1\u606f",
}


def main():
    now = datetime.now(timezone(timedelta(hours=8)))

    # Load history
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            history = json.load(f)
    except:
        history = {}

    # Process all posts
    feed_data = {}
    for date_key, posts in history.items():
        items = []
        for p in posts:
            item = process_post(p, now)
            if item:
                items.append(item)
        # Sort by score descending
        items.sort(key=lambda x: x["score"], reverse=True)
        if items:
            feed_data[date_key] = items

    sorted_dates = sorted(feed_data.keys(), reverse=True)

    # Read template
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # === 1. Add CSS for scoring system ===
    scoring_css = """
/* ===== Scoring System ===== */
.highlights-section { margin-bottom: 20px; }
.highlights-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.highlight-card {
  background: var(--bg2); border-radius: 10px; padding: 14px 18px;
  border: 1px solid var(--rule); border-left: 4px solid var(--accent);
  transition: all 0.2s; cursor: pointer; position: relative;
}
.highlight-card:hover { border-color: var(--accent); box-shadow: 0 4px 12px rgba(59,130,246,0.08); transform: translateY(-1px); }
.highlight-card.priority-S { border-left-color: #ef4444; background: linear-gradient(135deg, #fef2f2 0%, var(--bg2) 100%); }
.highlight-card.priority-A { border-left-color: #f97316; background: linear-gradient(135deg, #fff7ed 0%, var(--bg2) 100%); }
.highlight-card .hl-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.highlight-card .hl-title { font-size: 13px; font-weight: 600; line-height: 1.5; color: var(--ink); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.highlight-card .hl-summary { font-size: 12px; color: var(--muted); line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-top: 4px; }
.priority-badge {
  font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; color: #fff; white-space: nowrap;
}
.priority-badge.S { background: #ef4444; }
.priority-badge.A { background: #f97316; }
.priority-badge.B { background: #3b82f6; }
.priority-badge.C { background: #94a3b8; }
.score-badge {
  font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px;
  background: var(--bg); color: var(--ink2); font-family: "SF Mono","Menlo",monospace;
}
.score-breakdown {
  font-size: 10px; color: var(--muted); margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap;
}
.score-breakdown span { background: var(--bg); padding: 1px 6px; border-radius: 8px; }
.feed-item { position: relative; }
.feed-item .item-priority { position: absolute; top: 14px; right: 16px; display: flex; gap: 6px; align-items: center; }
@media (max-width: 768px) {
  .highlights-grid { grid-template-columns: 1fr; }
  .highlight-card { padding: 12px 14px; }
}
"""
    # Insert CSS before </style>
    content = content.replace('</style>', scoring_css + '</style>', 1)

    # === 2. Replace the feed page section ===
    feed_page_marker = '<!-- Feed Page -->'
    feed_page_start = content.find(feed_page_marker)
    cls_marker = '<!-- CLS Telegraph Page -->'
    cls_start = content.find(cls_marker, feed_page_start)

    new_feed_section = '''      <!-- Feed Page -->
      <div class="page-section" id="page-feed">
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--accent)"></span>\u6bcf\u65e5\u91cd\u70b9\u4fe1\u606f <span class="count" id="feed-count">0\u6761</span></div>
          <div style="display:flex;align-items:center;gap:10px;">
            <label style="font-size:13px;font-weight:600;color:var(--ink2);">\U0001F4C5 \u9009\u62e9\u65e5\u671f:</label>
            <select id="feed-date-selector" style="padding:6px 12px;border:1px solid var(--rule);border-radius:6px;background:var(--bg2);color:var(--ink);font-size:13px;cursor:pointer;min-width:140px;">
            </select>
          </div>
        </div>
        <div id="feed-highlights"></div>
        <div style="margin-top:20px;margin-bottom:12px;font-size:13px;font-weight:600;color:var(--muted);display:flex;align-items:center;gap:8px;">
          <span style="width:6px;height:6px;border-radius:50%;background:var(--accent);"></span>
          \u5168\u90e8\u4fe1\u606f\uff08\u6309\u673a\u4f1a\u5206\u6392\u5e8f\uff0c\u5df2\u8fc7\u6ee4\u566a\u97f3\uff09
        </div>
        <div class="feed-list" id="feed-list-container">
        </div>
      </div>

      '''

    content = content[:feed_page_start] + new_feed_section + content[cls_start:]

    # === 2b. Replace Dashboard page with dynamic content ===
    today_key = sorted_dates[0] if sorted_dates else ""
    today_data = feed_data.get(today_key, [])
    total_today = len(today_data)
    s_count = len([x for x in today_data if x["priority"] == "S"])
    a_count = len([x for x in today_data if x["priority"] == "A"])
    sa_items = [x for x in today_data if x["priority"] in ("S", "A")]
    bull_count = len([x for x in today_data if x["sentiment"] == "bull"])
    bull_pct = int(bull_count / total_today * 100) if total_today > 0 else 0
    all_comps = set()
    for item in today_data:
        if item["companies"]:
            for c in item["companies"].split(" \u00b7 "):
                all_comps.add(c.strip())
    comp_count = len(all_comps)

    dashboard_start = content.find('<!-- Dashboard Page -->')
    attention_marker = '<!-- Attention Page -->'
    attention_start = content.find(attention_marker, dashboard_start)

    if dashboard_start != -1 and attention_start != -1:
        import html as _h
        # Build metrics cards
        metrics_html = '''        <!-- Metrics -->
        <div class="metrics-bar">
          <div class="metric-card blue">
            <div class="metric-label">\u4eca\u65e5\u4fe1\u606f\u603b\u91cf</div>
            <div class="metric-value">''' + str(total_today) + '''</div>
            <div class="metric-change neutral">\u77e5\u8bc6\u661f\u7403\u00b7\u5e72\u8d27\u56fe\u4e66\u9986</div>
          </div>
          <div class="metric-card green">
            <div class="metric-label">\u6d89\u53ca\u516c\u53f8</div>
            <div class="metric-value">''' + str(comp_count) + '''<span style="font-size:14px;font-weight:400">\u5bb6</span></div>
            <div class="metric-change up">S/A\u7ea7 ''' + str(s_count + a_count) + ''' \u6761\u91cd\u70b9</div>
          </div>
          <div class="metric-card orange">
            <div class="metric-label">S\u7ea7\u91cd\u5927\u50ac\u5316</div>
            <div class="metric-value">''' + str(s_count) + '''<span style="font-size:14px;font-weight:400">\u6761</span></div>
            <div class="metric-change neutral">\u5fc5\u987b\u91cd\u70b9\u5173\u6ce8</div>
          </div>
          <div class="metric-card purple">
            <div class="metric-label">\u504f\u591a\u89c2\u70b9</div>
            <div class="metric-value">''' + str(bull_count) + '''<span style="font-size:14px;font-weight:400">\u6761</span></div>
            <div class="metric-change up">\u5360\u6bd4 ''' + str(bull_pct) + '''%</div>
          </div>
        </div>'''

        # Calculate stock selection results (for attention page)
        stock_results = extract_and_score_companies(today_data)
        tier_count = {}
        for sr in stock_results:
            tier_count[sr["tier"]] = tier_count.get(sr["tier"], 0) + 1

        # Calculate hot stocks (past 15 days) for dashboard preview and companies page
        hot_stocks = extract_hot_stocks(feed_data, now, days=15)

        # Build attention cards from S/A level feed items (original behavior)
        attention_cards_html = '''        <!-- \u7279\u522b\u5173\u6ce8 Quick View -->
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--accent)"></span>\u4eca\u65e5\u91cd\u70b9\u5173\u6ce8\uff08S/A\u7ea7\uff09 <span class="count">''' + str(len(sa_items)) + '''\u6761</span></div>
          <button class="header-btn ghost" onclick="switchPage('feed')">\u67e5\u770b\u5168\u90e8 \u2192</button>
        </div>
        <div class="attention-grid">'''

        for item in sa_items[:6]:
            raw_text = _h.unescape(item["text"].replace("<br>", " "))
            raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()
            title = raw_text[:60] + "..." if len(raw_text) > 60 else raw_text
            summary = raw_text[:120] + "..." if len(raw_text) > 120 else raw_text

            type_class = "type-tech"
            type_label = item["sector"]
            if item["priority"] == "S":
                type_class = "type-geo"
                type_label = "S\u7ea7\u00b7\u91cd\u5927\u50ac\u5316"
            elif item["priority"] == "A":
                type_class = "type-policy"
                type_label = "A\u7ea7\u00b7\u5f3a\u50ac\u5316"

            stars = "\u2b50" * min(int(item["score"] / 20), 5)

            attention_cards_html += '''          <div class="attention-card">
            <div class="card-top">
              <span class="card-type ''' + type_class + '''">''' + type_label + '''</span>
              <span class="card-stars">''' + stars + '''</span>
              <span class="score-badge" style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;background:var(--bg);color:var(--ink2);font-family:monospace;">''' + str(item["score"]) + '''\u5206</span>
            </div>
            <h3>''' + html_module.escape(title) + '''</h3>
            <div class="card-summary">''' + html_module.escape(summary) + '''</div>
            <div class="card-meta">
              <span>''' + item["time"] + '''</span>
              <span class="tag">''' + item["sector"] + '''</span>
              <span class="tag">\u65b0\u989a\u6027''' + str(item["novelty"]) + '''/\u8d85\u9884\u671f''' + str(item["surprise"]) + '''/\u5f71\u54cd''' + str(item["impact"]) + '''</span>
            </div>
          </div>'''

        attention_cards_html += '''        </div>'''

        # Build company quick view table from top items
        company_rows_html = '''        <!-- \u516c\u53f8 Quick View -->
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--green)"></span>\u4eca\u65e5\u673a\u4f1a\u4fe1\u606f\u5feb\u89c8 <span class="count">''' + str(total_today) + '''\u6761</span></div>
          <button class="header-btn ghost" onclick="switchPage('feed')">\u67e5\u770b\u5168\u90e8 \u2192</button>
        </div>
        <div class="company-table-wrap">
          <table class="company-table">
            <thead>
              <tr>
                <th>\u4f18\u5148\u7ea7</th>
                <th>\u8bc4\u5206</th>
                <th>\u677f\u5757</th>
                <th>\u65f6\u95f4</th>
                <th>\u6838\u5fc3\u4fe1\u606f</th>
              </tr>
            </thead>
            <tbody>'''

        for item in today_data[:8]:
            raw_text = _h.unescape(item["text"].replace("<br>", " "))
            raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()
            short_text = raw_text[:50] + "..." if len(raw_text) > 50 else raw_text

            cat_class = "cat-strong" if item["priority"] == "S" else ("cat-watch" if item["priority"] == "A" else "cat-neutral")
            cat_label = item["priority"] + "\u7ea7"
            score_color = "#ef4444" if item["priority"] == "S" else ("#f97316" if item["priority"] == "A" else "#3b82f6")

            company_rows_html += '''              <tr>
                <td><span class="category-tag ''' + cat_class + '''">''' + cat_label + '''</span></td>
                <td><span style="font-weight:700;color:''' + score_color + '''">''' + str(item["score"]) + '''</span></td>
                <td><span class="company-industry">''' + item["sector"] + '''</span></td>
                <td style="font-size:12.5px;color:var(--muted)">''' + item["time"] + '''</td>
                <td style="font-size:12.5px;color:var(--ink2)">''' + html_module.escape(short_text) + '''</td>
              </tr>'''

        company_rows_html += '''            </tbody>
          </table>
        </div>'''

        # Build hot stocks quick view table (top 5 from past 15 days)
        hot_preview_html = '''        <!-- \u8fd1\u671f\u70ed\u95e8\u80a1 Quick View -->
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--green)"></span>\u8fd1\u671f\u70ed\u95e8\u80a1\u5feb\u89c8 <span class="count">\u8fd115\u5929 ''' + str(len(hot_stocks)) + '''\u5bb6</span></div>
          <button class="header-btn ghost" onclick="switchPage('companies')">\u67e5\u770b\u5168\u90e8 \u2192</button>
        </div>
        <div class="company-table-wrap">
          <table class="company-table">
            <thead>
              <tr>
                <th>\u516c\u53f8</th>
                <th>\u884c\u4e1a</th>
                <th>\u70ed\u5ea6</th>
                <th>\u5206\u7c7b</th>
                <th>\u63d0\u53ca</th>
                <th>\u6838\u5fc3\u4e8b\u4ef6</th>
              </tr>
            </thead>
            <tbody>'''

        for hs in hot_stocks[:5]:
            cat_colors_js = {"\u8fd1\u671f\u5927\u70ed": "#ef4444", "\u6301\u7eed\u6d3b\u8dc3": "#f97316", "\u65b0\u664b\u70ed\u95e8": "#3b82f6", "\u6709\u6240\u5173\u6ce8": "#94a3b8"}
            cat_color = cat_colors_js.get(hs["category"], "#94a3b8")
            cat_class = "cat-strong" if hs["category"] == "\u8fd1\u671f\u5927\u70ed" else ("cat-watch" if hs["category"] in ("\u6301\u7eed\u6d3b\u8dc3", "\u65b0\u664b\u70ed\u95e8") else "cat-neutral")
            catalyst_short = hs.get("key_catalyst", "-")
            if len(catalyst_short) > 50:
                catalyst_short = catalyst_short[:50] + "..."

            hot_preview_html += '''              <tr>
                <td><span class="company-name">''' + hs["name"] + '''</span></td>
                <td><span class="company-industry">''' + hs["sector"] + '''</span></td>
                <td><span style="font-weight:700;color:var(--accent)">''' + str(hs["hot_score"]) + '''\u5206</span></td>
                <td><span class="category-tag ''' + cat_class + '''" style="background:''' + cat_color + '''20;color:''' + cat_color + '''">''' + hs["category"] + '''</span></td>
                <td style="font-size:11px;color:var(--muted)">''' + str(hs["mention_count"]) + '''\u6b21</td>
                <td style="font-size:12px;color:var(--ink2)">''' + html_module.escape(catalyst_short) + '''</td>
              </tr>'''

        if len(hot_stocks) == 0:
            hot_preview_html += '''              <tr><td colspan="6" style="text-align:center;padding:20px;color:var(--muted);">\u8fd115\u5929\u6682\u65e0\u70ed\u95e8\u80a1\u6570\u636e</td></tr>'''

        hot_preview_html += '''            </tbody>
          </table>
        </div>'''

        new_dashboard = '''      <!-- Dashboard Page -->
      <div class="page-section active" id="page-dashboard">
''' + metrics_html + '''

''' + attention_cards_html + '''

''' + company_rows_html + '''

''' + hot_preview_html + '''
      </div>

      '''

        content = content[:dashboard_start] + new_dashboard + content[attention_start:]

    # === 2c. Replace Attention page with stock selection results ===
    attention_page_start = content.find('<!-- Attention Page -->')
    companies_marker = '<!-- Companies Page -->'
    # Also check for page-companies
    companies_page_start = content.find('id="page-companies"')
    if companies_page_start != -1:
        # Find the div tag start before page-companies
        companies_page_start = content.rfind('<div class="page-section"', 0, companies_page_start)
    feed_page_marker2 = '<!-- Feed Page -->'
    feed_page_start2 = content.find(feed_page_marker2, attention_page_start)

    # Use the earliest marker found after attention page
    next_section_start = -1
    for marker_pos in [companies_page_start, feed_page_start2]:
        if marker_pos != -1 and (next_section_start == -1 or marker_pos < next_section_start):
            next_section_start = marker_pos

    if attention_page_start != -1 and next_section_start != -1:
        tier_colors_js = {"\u9876\u7ea7\u5f39\u6027": "#ef4444", "\u7a33\u5065\u5f39\u6027": "#f97316", "\u8bd5\u9519\u5907\u9009": "#3b82f6", "\u89c2\u5bdf": "#94a3b8"}

        new_attention_page = '''      <!-- Attention Page -->
      <div class="page-section" id="page-attention">
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--accent)"></span>\u7279\u522b\u5173\u6ce8\uff08\u9009\u80a1\u6846\u67b6\u7b5b\u9009\uff09 <span class="count">''' + str(len(stock_results)) + '''\u5bb6\u516c\u53f8</span></div>
        </div>

        <!-- \u9009\u80a1\u6846\u67b6\u8bf4\u660e -->
        <div style="background:var(--bg2);border-radius:10px;padding:14px 18px;margin-bottom:16px;border:1px solid var(--rule);">
          <div style="font-size:13px;font-weight:600;margin-bottom:8px;color:var(--ink);">\U0001F3AF \u9009\u80a1\u6846\u67b6\uff08\u94c1\u5f8b\uff09</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.8;">
            \u5e02\u503c40-280\u4ebf \u00b7 6\u4e2a\u6708\u5151\u73b0\u5468\u671f \u00b7 8\u9879\u5f3a\u5236\u95e8\u69db \u00b7 18\u9879\u52a0\u5206\uff08\u226511\u5206\u9ad8\u5f39\u6027\uff09<br>
            \u7b2c\u4e00\u68af\u961f\u3010\u9876\u7ea7\u5f39\u6027\u3011\u226514\u5206 \u00b7 \u7b2c\u4e8c\u68af\u961f\u3010\u7a33\u5065\u5f39\u6027\u301111-13\u5206 \u00b7 \u7b2c\u4e09\u68af\u961f\u3010\u8bd5\u9519\u5907\u9009\u3011<11\u5206
          </div>
        </div>

        <!-- \u68af\u961f\u7edf\u8ba1 -->
        <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">'''

        for tier_name in ["\u9876\u7ea7\u5f39\u6027", "\u7a33\u5065\u5f39\u6027", "\u8bd5\u9519\u5907\u9009", "\u89c2\u5bdf"]:
            cnt = tier_count.get(tier_name, 0)
            if cnt > 0:
                color = tier_colors_js.get(tier_name, "#94a3b8")
                new_attention_page += '''<span style="font-size:12px;font-weight:600;padding:4px 12px;border-radius:12px;background:''' + color + '''20;color:''' + color + '''">''' + tier_name + ''' ''' + str(cnt) + '''\u5bb6</span>'''

        new_attention_page += '''</div>

        <!-- \u516c\u53f8\u9009\u80a1\u8868 -->
        <div class="company-table-wrap">
          <table class="company-table">
            <thead>
              <tr>
                <th>\u516c\u53f8</th>
                <th>\u68af\u961f</th>
                <th>\u95e8\u69db</th>
                <th>\u52a0\u5206</th>
                <th>\u52a0\u5206\u9879</th>
                <th>\u8fd17\u5929\u91cd\u8981\u4e3b\u56e0</th>
                <th>\u4fe1\u606f\u8bc4\u5206</th>
              </tr>
            </thead>
            <tbody>'''

        for sr in stock_results:
            tier_color = tier_colors_js.get(sr["tier"], "#94a3b8")
            cat_class = "cat-strong" if sr["tier"] == "\u9876\u7ea7\u5f39\u6027" else ("cat-watch" if sr["tier"] == "\u7a33\u5065\u5f39\u6027" else "cat-neutral")
            bonus_text = html_module.escape(" / ".join(sr["bonus_items"][:4]) if sr["bonus_items"] else "-")
            catalyst_text = html_module.escape(sr.get("key_catalyst", "-"))

            new_attention_page += '''              <tr>
                <td><span class="company-name">''' + sr["name"] + '''</span><span class="company-industry">''' + sr["sector"] + '''</span></td>
                <td><span class="category-tag ''' + cat_class + '''" style="background:''' + tier_color + '''20;color:''' + tier_color + '''">''' + sr["tier"] + '''</span></td>
                <td><span style="font-weight:600;color:var(--ink)">''' + str(sr["threshold_count"]) + '''/9</span></td>
                <td><span style="font-weight:700;color:''' + tier_color + '''">+''' + str(sr["bonus_score"]) + '''/18</span></td>
                <td style="font-size:11px;color:var(--muted);max-width:200px;">''' + bonus_text + '''</td>
                <td style="font-size:11.5px;color:var(--ink2);max-width:260px;line-height:1.5;">''' + catalyst_text + '''</td>
                <td><span style="font-weight:600;color:var(--accent)">''' + str(sr["best_score"]) + '''\u5206</span> <span style="font-size:11px;color:var(--muted)">''' + sr["best_priority"] + '''\u7ea7</span></td>
              </tr>'''

        if len(stock_results) == 0:
            new_attention_page += '''              <tr><td colspan="7" style="text-align:center;padding:32px;color:var(--muted);">\U0001F4C4 \u4eca\u65e5\u4fe1\u606f\u4e2d\u672a\u7b5b\u9009\u51fa\u7b26\u5408\u9009\u80a1\u6846\u67b6\u7684\u516c\u53f8</td></tr>'''

        new_attention_page += '''            </tbody>
          </table>
        </div>

        <!-- \u53cd\u5411\u6dd8\u6c70\u9ed1\u540d\u5355\u63d0\u793a -->
        <div style="margin-top:16px;background:#fef2f2;border-radius:10px;padding:12px 18px;border:1px solid #fecaca;">
          <div style="font-size:12px;font-weight:600;color:#ef4444;margin-bottom:4px;">\u26a0\ufe0f \u53cd\u5411\u6dd8\u6c70\u9ed1\u540d\u5355\uff08\u547d\u4e2d\u4efb\u610f\u4e00\u6761\u76f4\u63a5\u653e\u5f03\uff09</div>
          <div style="font-size:11px;color:#991b1b;line-height:1.6;">
            \u2460 \u50ac\u5316\u843d\u5730\u57286\u4e2a\u6708\u540e \u00b7 \u2461 \u7eaf\u9898\u6750\u6982\u5ff5\u65e0\u8ba2\u5355/\u5b9a\u70b9/\u4ea7\u80fd \u00b7 \u2462 \u6bdb\u5229\u7387\u6301\u7eed\u4e0b\u884c \u00b7 \u2463 \u8870\u9000\u8d5b\u9053\u65e0\u666f\u6c14\u903b\u8f91
          </div>
        </div>
      </div>

      '''

        content = content[:attention_page_start] + new_attention_page + content[next_section_start:]

    # === 2c-2. Replace Companies Page with hot stocks (past 15 days) ===

    companies_start2 = content.find('id="page-companies"')
    if companies_start2 != -1:
        companies_start2 = content.rfind('<div class="page-section"', 0, companies_start2)
    feed_page_marker3 = '<!-- Feed Page -->'
    feed_page_start3 = content.find(feed_page_marker3, companies_start2 if companies_start2 != -1 else 0)

    if companies_start2 != -1 and feed_page_start3 != -1:
        cat_colors = {"\u8fd1\u671f\u5927\u70ed": "#ef4444", "\u6301\u7eed\u6d3b\u8dc3": "#f97316", "\u65b0\u664b\u70ed\u95e8": "#3b82f6", "\u6709\u6240\u5173\u6ce8": "#94a3b8"}
        max_hot = max([s["hot_score"] for s in hot_stocks]) if hot_stocks else 100

        new_companies_page = '''      <!-- Companies Page -->
      <div class="page-section" id="page-companies">
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--green)"></span>\u8fd1\u671f\u70ed\u95e8\u80a1 <span class="count">''' + str(len(hot_stocks)) + '''\u5bb6</span></div>
          <div style="font-size:12px;color:var(--muted);">\u7edf\u8ba1\u5468\u671f\uff1a\u8fd115\u5929</div>
        </div>

        <!-- \u70ed\u5ea6\u7edf\u8ba1 -->
        <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">'''

        for cat_name in ["\u8fd1\u671f\u5927\u70ed", "\u6301\u7eed\u6d3b\u8dc3", "\u65b0\u664b\u70ed\u95e8", "\u6709\u6240\u5173\u6ce8"]:
            cnt = len([s for s in hot_stocks if s["category"] == cat_name])
            if cnt > 0:
                color = cat_colors.get(cat_name, "#94a3b8")
                new_companies_page += '''<span style="font-size:12px;font-weight:600;padding:4px 12px;border-radius:12px;background:''' + color + '''20;color:''' + color + '''">''' + cat_name + ''' ''' + str(cnt) + '''\u5bb6</span>'''

        new_companies_page += '''</div>

        <div class="company-table-wrap">
          <table class="company-table">
            <thead>
              <tr>
                <th>\u516c\u53f8</th>
                <th>\u884c\u4e1a</th>
                <th>\u70ed\u5ea6\u5f97\u5206</th>
                <th>\u70ed\u5ea6\u5206\u7c7b</th>
                <th>\u63d0\u53ca\u8be6\u60c5</th>
                <th>\u6838\u5fc3\u4e8b\u4ef6\u6458\u8981</th>
              </tr>
            </thead>
            <tbody>'''

        for hs in hot_stocks:
            cat_color = cat_colors.get(hs["category"], "#94a3b8")
            cat_class = "cat-strong" if hs["category"] == "\u8fd1\u671f\u5927\u70ed" else ("cat-watch" if hs["category"] in ("\u6301\u7eed\u6d3b\u8dc3", "\u65b0\u664b\u70ed\u95e8") else "cat-neutral")
            hot_pct = min(int(hs["hot_score"] / max(max_hot, 1) * 100), 100) if max_hot > 0 else 0
            bar_class = "high" if hot_pct >= 70 else ("mid" if hot_pct >= 40 else "low")

            mention_detail = str(hs["mention_count"]) + "\u6b21\u63d0\u53ca"
            sa_parts = []
            if hs["s_count"] > 0:
                sa_parts.append("S\u7ea7" + str(hs["s_count"]))
            if hs["a_count"] > 0:
                sa_parts.append("A\u7ea7" + str(hs["a_count"]))
            if sa_parts:
                mention_detail += " \u00b7 " + "/".join(sa_parts)
            mention_detail += "<br>\u6700\u8fd1: " + hs["last_date"]

            catalyst_text = html_module.escape(hs.get("key_catalyst", "-"))

            new_companies_page += '''              <tr>
                <td><span class="company-name">''' + hs["name"] + '''</span></td>
                <td><span class="company-industry">''' + hs["sector"] + '''</span></td>
                <td><div class="score-bar-wrap"><div class="score-bar"><div class="score-bar-fill ''' + bar_class + '''" style="width:''' + str(hot_pct) + '''%"></div></div><span class="score-text" style="color:var(--accent)">''' + str(hs["hot_score"]) + '''\u5206</span></div></td>
                <td><span class="category-tag ''' + cat_class + '''" style="background:''' + cat_color + '''20;color:''' + cat_color + '''">''' + hs["category"] + '''</span></td>
                <td style="font-size:11px;color:var(--muted);line-height:1.6;">''' + mention_detail + '''</td>
                <td style="font-size:12.5px;color:var(--ink2);max-width:260px;line-height:1.5;">''' + catalyst_text + '''</td>
              </tr>'''

        if len(hot_stocks) == 0:
            new_companies_page += '''              <tr><td colspan="6" style="text-align:center;padding:32px;color:var(--muted);">\U0001F4C4 \u8fd115\u5929\u6682\u65e0\u70ed\u95e8\u80a1\u6570\u636e</td></tr>'''

        new_companies_page += '''            </tbody>
          </table>
        </div>
      </div>

      '''

        content = content[:companies_start2] + new_companies_page + content[feed_page_start3:]

    # === 2d. Replace Abnormal page with dynamic eastmoney data ===
    try:
        with open(EASTMONEY_DATA_PATH, 'r', encoding='utf-8') as f:
            em_data = json.load(f)
    except:
        em_data = {"records": [], "total_count": 0, "event_stats": {},
                    "industry_resonance": [], "update_time": "", "market_status": "closed"}

    em_records = em_data.get("records", [])
    em_total = em_data.get("total_count", len(em_records))
    em_events = em_data.get("event_stats", {})
    em_industries = em_data.get("industry_resonance", [])
    em_time = em_data.get("update_time", "")
    em_market = em_data.get("market_status", "closed")

    try:
        em_time_fmt = datetime.fromisoformat(em_time).strftime("%m.%d %H:%M")
    except:
        em_time_fmt = now.strftime("%m.%d %H:%M")

    em_status_text = "\u76d8\u4e2d\u5b9e\u65f6" if em_market == "open" else "\u6536\u76d8\u6570\u636e"

    # Tier counts
    em_tier_counts = {}
    for r in em_records:
        tier = r.get("selection", {}).get("tier", "\u89c2\u5bdf")
        em_tier_counts[tier] = em_tier_counts.get(tier, 0) + 1

    em_max_stock = max(em_records, key=lambda x: x.get("change", 0)) if em_records else None
    em_top_ind = em_industries[0] if em_industries else None

    # Find abnormal page section
    abnormal_marker = '<!-- \u6bcf\u65e5\u5f02\u52a8\u6da8\u5e45 Page -->'
    abnormal_start = content.find(abnormal_marker)
    settings_marker = '<!-- Settings Page -->'
    settings_start = content.find(settings_marker, abnormal_start if abnormal_start != -1 else 0)

    if abnormal_start != -1 and settings_start != -1:
        # Build metrics
        em_metrics = '''        <!-- \u6838\u5fc3\u6307\u6807 -->
        <div class="metrics-bar">
          <div class="metric-card blue">
            <div class="metric-label">\u5f53\u524d5%+\u6d3b\u8dc3\u80a1</div>
            <div class="metric-value">''' + str(em_total) + '''</div>
            <div class="metric-change up">''' + em_status_text + '''</div>
          </div>
          <div class="metric-card green">
            <div class="metric-label">\u53d8\u5316\u4e8b\u4ef6</div>
            <div class="metric-value">''' + str(sum(em_events.values())) + '''</div>
            <div class="metric-change neutral">\u6da8\u505c''' + str(em_events.get("\u6da8\u505c", 0)) + ''' | \u9996\u6b21\u7a81\u7834''' + str(em_events.get("\u9996\u6b21\u7a81\u7834", 0)) + '''</div>
          </div>
          <div class="metric-card orange">
            <div class="metric-label">\u6700\u5f3a\u5171\u632f\u884c\u4e1a</div>
            <div class="metric-value" style="font-size:20px;">''' + (em_top_ind["industry"] if em_top_ind else "-") + '''</div>
            <div class="metric-change up">''' + (str(em_top_ind["count"]) + "\u80a1\u5171\u632f \u00b7 \u5747+" + str(em_top_ind["avg_change"]) + "%" if em_top_ind else "\u6682\u65e0") + '''</div>
          </div>
          <div class="metric-card purple">
            <div class="metric-label">\u6700\u9ad8\u6da8\u5e45</div>
            <div class="metric-value" style="color:var(--red)">+''' + (str(em_max_stock["change"]) + "%" if em_max_stock else "-") + '''</div>
            <div class="metric-change">''' + ((em_max_stock["name"] + " " + em_max_stock["code"]) if em_max_stock else "-") + '''</div>
          </div>
        </div>'''

        # Build industry resonance heatmap
        em_industry_html = '''        <!-- \u884c\u4e1a\u5171\u632f\u70ed\u529b\u56fe -->
        <div style="background:var(--bg2);border-radius:10px;padding:16px;border:1px solid var(--rule);margin-bottom:16px;">
          <div style="font-size:13px;font-weight:600;margin-bottom:12px;display:flex;align-items:center;gap:8px;">\U0001F3AF \u884c\u4e1a\u5171\u632f\u70ed\u5ea6</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;">'''

        for ind in em_industries[:12]:
            level = ind.get("level", "\u4e00\u822c")
            if level == "\u70ed\u95e8":
                bg, border_c, color_c, icon = "var(--red-light)", "var(--red)", "var(--red)", "\U0001F525 \u70ed\u95e8"
            elif level == "\u6d3b\u8dc3":
                bg, border_c, color_c, icon = "var(--accent-light)", "var(--accent)", "var(--accent)", "\U0001F4CA \u6d3b\u8dc3"
            else:
                bg, border_c, color_c, icon = "var(--bg)", "var(--rule)", "var(--muted)", "\u27a1\ufe0f \u4e00\u822c"

            em_industry_html += '''            <div style="padding:8px 14px;background:''' + bg + ''';border:1px solid ''' + border_c + ''';border-radius:8px;">
              <div style="font-size:11px;color:''' + color_c + ''';font-weight:600">''' + icon + '''</div>
              <div style="font-weight:600;font-size:13px;">''' + ind["industry"] + ''' \u00b7 ''' + str(ind["count"]) + '''\u80a1 \u00b7 \u5747+''' + str(ind["avg_change"]) + '''%</div>
            </div>'''

        em_industry_html += '''          </div>
        </div>'''

        # Build tier summary
        tier_colors_map = {"\u9876\u7ea7\u5f39\u6027": "#ef4444", "\u7a33\u5065\u5f39\u6027": "#f97316", "\u8bd5\u9519\u5907\u9009": "#3b82f6", "\u89c2\u5bdf": "#94a3b8", "\u9ed1\u540d\u5355": "#6b7280"}
        em_tier_html = '''        <!-- \u9009\u80a1\u6846\u67b6\u68af\u961f\u7edf\u8ba1 -->
        <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
          <div style="font-size:12px;font-weight:600;color:var(--muted);padding:4px 0;align-self:center;">\u9009\u80a1\u6846\u67b6\uff1a</div>'''
        for tier_name in ["\u9876\u7ea7\u5f39\u6027", "\u7a33\u5065\u5f39\u6027", "\u8bd5\u9519\u5907\u9009", "\u89c2\u5bdf"]:
            cnt = em_tier_counts.get(tier_name, 0)
            if cnt > 0:
                color_c = tier_colors_map.get(tier_name, "#94a3b8")
                em_tier_html += '''<span style="font-size:12px;font-weight:600;padding:4px 12px;border-radius:12px;background:''' + color_c + '''20;color:''' + color_c + '''">''' + tier_name + ''' ''' + str(cnt) + '''\u53ea</span>'''
        em_tier_html += '''</div>'''

        # Build filter bar
        em_filter_html = '''        <!-- \u7b5b\u9009\u680f -->
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;">
          <div style="position:relative;flex:1;min-width:200px;">
            <input type="text" id="abnormal-search" placeholder="\u641c\u7d22\u80a1\u7968\u540d\u79f0/\u4ee3\u7801..." style="width:100%;padding:8px 12px 8px 36px;border:1px solid var(--rule);border-radius:6px;font-size:13px;background:var(--bg2);" oninput="filterAbnormalTable()">
            <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:14px;">\U0001F50D</span>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="abnormal-filter-btn active" onclick="filterAbnormalByStatus(this,'all')" style="padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--rule);background:var(--accent);color:#fff;cursor:pointer;font-weight:500;">\u5168\u90e8</button>
            <button class="abnormal-filter-btn" onclick="filterAbnormalByStatus(this,'\u6da8\u505c')" style="padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--rule);background:var(--bg2);color:var(--ink2);cursor:pointer;">\u6da8\u505c</button>
            <button class="abnormal-filter-btn" onclick="filterAbnormalByStatus(this,'\u9996\u6b21\u7a81\u7834')" style="padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--rule);background:var(--bg2);color:var(--ink2);cursor:pointer;">\u9996\u6b21\u7a81\u7834</button>
            <button class="abnormal-filter-btn" onclick="filterAbnormalByStatus(this,'\u7ee7\u7eed\u62c9\u5347')" style="padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--rule);background:var(--bg2);color:var(--ink2);cursor:pointer;">\u7ee7\u7eed\u62c9\u5347</button>
            <button class="abnormal-filter-btn" onclick="filterAbnormalByStatus(this,'\u660e\u663e\u56de\u843d')" style="padding:5px 12px;border-radius:6px;font-size:12px;border:1px solid var(--rule);background:var(--bg2);color:var(--ink2);cursor:pointer;">\u660e\u663e\u56de\u843d</button>
          </div>
        </div>'''

        # Build table
        em_table_html = '''        <!-- \u6d3b\u8dc3\u6c60\u8868\u683c -->
        <div style="background:var(--bg2);border-radius:10px;border:1px solid var(--rule);overflow:hidden;margin-bottom:16px;">
          <div style="padding:12px 16px;background:var(--bg);font-size:13px;font-weight:600;display:flex;justify-content:space-between;align-items:center;">
            <span>\U0001F4CA \u5f53\u524d5%+\u6d3b\u8dc3\u6c60\uff08\u9009\u80a1\u6846\u67b6\u6392\u5e8f\uff09</span>
            <span style="font-size:11px;color:var(--muted)">''' + em_time_fmt + ''' \u00b7 ''' + str(em_total) + '''\u53ea</span>
          </div>
          <div style="overflow-x:auto;">
            <table id="abnormal-table" style="width:100%;border-collapse:collapse;font-size:12px;min-width:1650px;">
              <thead>
                <tr style="border-bottom:2px solid var(--rule);">
                  <th style="padding:10px 8px;text-align:left;">\u80a1\u7968</th>
                  <th style="padding:10px 8px;text-align:center;">\u6da8\u5e45</th>
                  <th style="padding:10px 8px;text-align:center;">\u53d8\u5316</th>
                  <th style="padding:10px 8px;text-align:left;">\u884c\u4e1a</th>
                  <th style="padding:10px 8px;text-align:center;">\u68af\u961f</th>
                  <th style="padding:10px 8px;text-align:center;">\u95e8\u69db</th>
                  <th style="padding:10px 8px;text-align:center;">\u52a0\u5206</th>
                  <th style="padding:10px 8px;text-align:left;">\u52a0\u5206\u9879</th>
                  <th style="padding:10px 8px;text-align:right;">\u6210\u4ea4\u989d</th>
                  <th style="padding:10px 8px;text-align:right;">\u51c0\u6d41\u5165</th>
                  <th style="padding:10px 8px;text-align:left;">\u6838\u5fc3\u4e8b\u4ef6\u6458\u8981</th>
                  <th style="padding:10px 8px;text-align:left;">AI\u4e3b\u56e0\u5f52\u56e0</th>
                  <th style="padding:10px 8px;text-align:left;">\u8fd17\u5929\u50ac\u5316</th>
                  <th style="padding:10px 8px;text-align:center;">\u8be6\u60c5</th>
                </tr>
              </thead>
              <tbody>
              </tbody>
            </table>
          </div>
        </div>'''

        # Build event timeline (top 15 by change)
        em_timeline_html = '''        <!-- \u53d8\u5316\u4e8b\u4ef6\u65f6\u95f4\u7ebf -->
        <div style="background:var(--bg2);border-radius:10px;padding:16px;border:1px solid var(--rule);margin-bottom:16px;">
          <div style="font-size:13px;font-weight:600;margin-bottom:12px;">\u23f1\ufe0f \u53d8\u5316\u4e8b\u4ef6\u6d41\uff08\u6309\u6da8\u5e45\u6392\u5e8f\uff09</div>
          <div style="display:flex;flex-direction:column;gap:8px;max-height:400px;overflow-y:auto;" id="events-timeline">'''

        for r in em_records[:15]:
            status = r.get("status", "")
            change = r.get("change", 0)
            name = r.get("name", "")
            cause = r.get("cause", "")
            industry = r.get("industry", "")

            if status == "\u6da8\u505c":
                bg, border_c, badge_bg = "var(--red-light)", "var(--red)", "var(--red)"
            elif status == "\u9996\u6b21\u7a81\u7834":
                bg, border_c, badge_bg = "var(--green-light)", "var(--green)", "var(--green)"
            elif status == "\u7ee7\u7eed\u62c9\u5347":
                bg, border_c, badge_bg = "var(--orange-light)", "var(--orange)", "var(--orange)"
            elif status == "\u660e\u663e\u56de\u843d":
                bg, border_c, badge_bg = "var(--purple-light)", "var(--purple)", "var(--purple)"
            else:
                bg, border_c, badge_bg = "var(--bg)", "var(--rule)", "var(--muted)"

            change_color = "var(--red)" if change >= 10 else "var(--orange)"

            em_timeline_html += '''            <div style="display:flex;gap:10px;align-items:flex-start;padding:8px 12px;background:''' + bg + ''';border-radius:8px;border-left:3px solid ''' + border_c + '''">
              <div style="flex:1;">
                <div style="font-size:12.5px;"><strong>''' + html_module.escape(name) + '''</strong> <span style="color:''' + change_color + ''';font-weight:700;">+''' + str(change) + '''%</span> <span style="font-size:11px;background:''' + badge_bg + ''';color:#fff;padding:1px 6px;border-radius:4px;">''' + status + '''</span></div>
                <div style="font-size:11px;color:var(--muted);margin-top:2px;">''' + html_module.escape(industry) + ''' \u00b7 ''' + html_module.escape(cause) + '''</div>
              </div>
            </div>'''

        em_timeline_html += '''          </div>
        </div>'''

        new_abnormal_page = '''      <!-- \u6bcf\u65e5\u5f02\u52a8\u6da8\u5e45 Page -->
      <div class="page-section" id="page-abnormal">
        <div class="section-header">
          <div class="section-title"><span class="dot" style="background:var(--accent2)"></span>\u6bcf\u65e5\u5f02\u52a8\u6da8\u5e45 5%+ \u00b7 \u4e3b\u56e0\u5f52\u56e0 <span class="count">\u5b9e\u65f6\u8ffd\u8e2a</span></div>
          <div style="font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px;">
            <span class="refresh-dot"></span>''' + em_time_fmt + ''' ''' + em_status_text + '''
          </div>
        </div>

        <div style="background:var(--accent2-light);border-radius:10px;padding:12px 16px;border:1px solid var(--accent2);margin-bottom:16px;font-size:12px;color:var(--ink2);display:flex;align-items:flex-start;gap:8px;">
          <span style="font-size:16px;flex-shrink:0">\u26a1</span>
          <div>
            <strong>\u6570\u636e\u6765\u6e90\uff1a</strong>\u4e1c\u65b9\u8d22\u5bcc\u5206\u949f\u7ea7\u6da8\u5e45\u76d1\u63a7\u811a\u672c + AI\u4e3b\u56e0\u5f52\u56e0\u5f15\u64ce<br>
            \u81ea\u52a8\u8ffd\u8e2aA\u80a1\u6bcf\u65e5\u6da8\u5e45\u22655%\u7684\u6d3b\u8dc3\u80a1\u7968\uff0c\u5b9e\u65f6\u8bb0\u5f55\u53d8\u5316\u4e8b\u4ef6\uff08\u9996\u6b21\u7a81\u78345%/\u7ee7\u7eed\u62c9\u5347/\u56de\u8e29/\u63a5\u8fd1\u6da8\u505c/\u660e\u663e\u56de\u843d\u7b49\uff09\uff0c\u9009\u80a1\u6392\u5e8f\u903b\u8f91\u4e0e\u7279\u522b\u5173\u6ce8\u6a21\u5757\u4e00\u81f4\uff088\u95e8\u69db+18\u52a0\u5206+\u9ed1\u540d\u5355\uff09
          </div>
        </div>

''' + em_metrics + '''

''' + em_industry_html + '''

''' + em_tier_html + '''

''' + em_filter_html + '''

''' + em_table_html + '''

''' + em_timeline_html + '''

        <div style="background:var(--bg2);border-radius:10px;padding:16px;border:1px solid var(--rule);">
          <div style="font-size:13px;font-weight:600;margin-bottom:10px;">\U0001F514 \u76d1\u63a7\u63d0\u9192\u89c4\u5219</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px;">
            <span style="padding:4px 10px;background:var(--green-light);border:1px solid var(--green);border-radius:6px;font-size:12px;color:var(--green);">\u9996\u6b21\u7a81\u78345%</span>
            <span style="padding:4px 10px;background:var(--accent-light);border:1px solid var(--accent);border-radius:6px;font-size:12px;color:var(--accent);">\u7ee7\u7eed\u62c9\u5347</span>
            <span style="padding:4px 10px;background:var(--orange-light);border:1px solid var(--orange);border-radius:6px;font-size:12px;color:var(--orange);">\u56de\u8e097%</span>
            <span style="padding:4px 10px;background:var(--red-light);border:1px solid var(--red);border-radius:6px;font-size:12px;color:var(--red);">\u63a5\u8fd1\u6da8\u505c</span>
            <span style="padding:4px 10px;background:var(--purple-light);border:1px solid var(--purple);border-radius:6px;font-size:12px;color:var(--purple);">\u660e\u663e\u56de\u843d</span>
            <span style="padding:4px 10px;background:var(--bg);border:1px solid var(--rule);border-radius:6px;font-size:12px;color:var(--muted);">\u6da8\u505c\u6253\u5f00</span>
            <span style="padding:4px 10px;background:var(--bg);border:1px solid var(--rule);border-radius:6px;font-size:12px;color:var(--muted);">\u8dcc\u505c\u6253\u5f00</span>
          </div>
        </div>
      </div>

      '''

        content = content[:abnormal_start] + new_abnormal_page + content[settings_start:]

    # === 3. Update date tag ===
    today_str = now.strftime("%Y-%m-%d")
    content = re.sub(
        r'class="date-tag">\s*\d{4}-\d{2}-\d{2}',
        'class="date-tag">' + today_str,
        content
    )

    # === 4. Add JavaScript ===
    feed_data_json = json.dumps(feed_data, ensure_ascii=False, indent=2)

    js_code = '''
// ============ \u6bcf\u65e5\u91cd\u70b9\u4fe1\u606f - \u65e5\u5386 + \u8bc4\u5206\u7cfb\u7edf ============
var FEED_DATA = ''' + feed_data_json + ''';

var PRIORITY_LABELS = {
  "S": "S\u7ea7\u00b7\u91cd\u5927\u50ac\u5316",
  "A": "A\u7ea7\u00b7\u5f3a\u50ac\u5316",
  "B": "B\u7ea7\u00b7\u6709\u6548\u4fe1\u606f",
  "C": "C\u7ea7\u00b7\u53c2\u8003\u4fe1\u606f"
};

function renderHighlights(dateKey) {
  var data = FEED_DATA[dateKey] || [];
  var saItems = data.filter(function(item) { return item.priority === 'S' || item.priority === 'A'; });
  var container = document.getElementById('feed-highlights');
  
  if (saItems.length === 0) {
    container.innerHTML = '';
    return;
  }
  
  var html = '<div class="highlights-section">';
  html += '<div style="margin-bottom:12px;font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px;">';
  html += '<span style="width:8px;height:8px;border-radius:50%;background:#ef4444;"></span>';
  html += '\u4eca\u65e5\u91cd\u70b9\u5173\u6ce8\uff08S/A\u7ea7\uff09';
  html += '<span style="font-size:12px;color:var(--muted);font-weight:400;">' + saItems.length + '\u6761</span>';
  html += '</div><div class="highlights-grid">';
  
  for (var i = 0; i < saItems.length; i++) {
    var item = saItems[i];
    var summary = item.text.replace(/<br>/g, ' ').replace(/<[^>]+>/g, '');
    if (summary.length > 120) summary = summary.substring(0, 120) + '...';
    var title = summary.substring(0, 60);
    if (summary.length > 60) title = summary.substring(0, 60) + '...';
    
    html += '<div class="highlight-card priority-' + item.priority + '" onclick="document.getElementById(\\'feed-list-container\\').scrollIntoView({behavior:\\'smooth\\',block:\\'start\\'})">';
    html += '<div class="hl-header">';
    html += '<span class="priority-badge ' + item.priority + '">' + item.priority + '</span>';
    html += '<span class="score-badge">' + item.score + '\u5206</span>';
    html += '<span class="feed-time">' + item.time + '</span>';
    html += '<span class="feed-tag neutral">' + item.sector + '</span>';
    html += '</div>';
    html += '<div class="hl-title">' + title + '</div>';
    html += '<div class="hl-summary">' + summary + '</div>';
    html += '<div class="score-breakdown">';
    html += '<span>\u65b0\u9896\u6027 ' + item.novelty + '/20</span>';
    html += '<span>\u8d85\u9884\u671f ' + item.surprise + '/20</span>';
    html += '<span>\u5f71\u54cd\u529b ' + item.impact + '/20</span>';
    html += '<span>\u6269\u6563 ' + item.spread + '/20</span>';
    html += '<span>\u57fa\u672c\u9762 ' + item.fundamentals + '/20</span>';
    html += '</div>';
    html += '</div>';
  }
  
  html += '</div></div>';
  container.innerHTML = html;
}

function renderFeed(dateKey) {
  var data = FEED_DATA[dateKey] || [];
  var container = document.getElementById('feed-list-container');
  var countEl = document.getElementById('feed-count');
  
  // Render highlights
  renderHighlights(dateKey);
  
  // Sort by time descending (newest first)
  data = data.slice().sort(function(a, b) {
    return (b.fullTime || '').localeCompare(a.fullTime || '');
  });
  
  var totalCount = data.length;
  countEl.textContent = totalCount + '\u6761';
  
  if (data.length === 0) {
    container.innerHTML = '<div style="text-align:center;padding:48px 20px;color:var(--muted);font-size:14px;background:var(--bg2);border-radius:10px;border:1px solid var(--rule);">\U0001F4C4 \u8be5\u65e5\u671f\u6682\u65e0\u6570\u636e\u8bb0\u5f55</div>';
    return;
  }
  
  var html = '';
  for (var i = 0; i < data.length; i++) {
    var item = data[i];
    var tags = '<span class="feed-time">' + item.time + '</span>';
    tags += '<span class="feed-tag ' + item.sentiment + '">' + item.sentimentLabel + '</span>';
    tags += '<span class="feed-tag neutral">' + item.sector + '</span>';
    if (item.companies) {
      tags += '<span class="feed-companies">' + item.companies + '</span>';
    }
    
    // Priority badge and score
    var priorityHtml = '<div class="item-priority">';
    priorityHtml += '<span class="priority-badge ' + item.priority + '">' + item.priority + '</span>';
    priorityHtml += '<span class="score-badge">' + item.score + '</span>';
    priorityHtml += '</div>';
    
    html += '<div class="feed-item">';
    html += priorityHtml;
    html += '<div class="feed-item-header">' + tags + '</div>';
    html += '<div class="feed-content">' + item.text + '</div>';
    html += '<div class="score-breakdown" style="margin-top:8px;">';
    html += '<span>\u65b0\u9896\u6027 ' + item.novelty + '/20</span>';
    html += '<span>\u8d85\u9884\u671f ' + item.surprise + '/20</span>';
    html += '<span>\u5f71\u54cd\u529b ' + item.impact + '/20</span>';
    html += '<span>\u6269\u6563 ' + item.spread + '/20</span>';
    html += '<span>\u57fa\u672c\u9762 ' + item.fundamentals + '/20</span>';
    html += '</div>';
    html += '</div>';
  }
  container.innerHTML = html;
}

function initFeedSelector() {
  var selector = document.getElementById('feed-date-selector');
  if (!selector) return;
  
  var dates = Object.keys(FEED_DATA).sort().reverse();
  
  if (dates.length === 0) {
    selector.innerHTML = '<option value="">\u6682\u65e0\u6570\u636e</option>';
    renderFeed('');
    return;
  }
  
  var optionsHtml = '';
  for (var i = 0; i < dates.length; i++) {
    var d = dates[i];
    var label = d.substring(5).replace('-', '.');
    var dayData = FEED_DATA[d];
    var saCount = dayData.filter(function(x){return x.priority==='S'||x.priority==='A';}).length;
    var isToday = (i === 0) ? ' (\u6700\u65b0)' : '';
    var saLabel = saCount > 0 ? ' \u00b7 ' + saCount + '\u6761\u91cd\u70b9' : '';
    optionsHtml += '<option value="' + d + '">' + label + ' (' + dayData.length + '\u6761' + saLabel + ')' + isToday + '</option>';
  }
  selector.innerHTML = optionsHtml;
  
  selector.value = dates[0];
  renderFeed(dates[0]);
  
  selector.addEventListener('change', function() {
    renderFeed(this.value);
  });
}

document.addEventListener('DOMContentLoaded', function() { initFeedSelector(); });
if (document.readyState !== 'loading') { initFeedSelector(); }
'''

    last_script_close = content.rfind('</script>')
    if last_script_close != -1:
        content = content[:last_script_close] + js_code + '\n' + content[last_script_close:]

    # === 4b. Replace abnormal JavaScript with eastmoney data version ===
    abnormal_js_start = content.find('// ============ \u5f02\u52a8\u6da8\u5e45\u6570\u636e ============')
    cls_js_marker = '// ============ \u8d22\u8054\u793e\u7535\u62a5\u5feb\u8baf ============'
    abnormal_js_end = content.find(cls_js_marker)

    if abnormal_js_start != -1 and abnormal_js_end != -1:
        em_data_json = json.dumps(em_data, ensure_ascii=False)

        new_abnormal_js = '''
// ============ \u5f02\u52a8\u6da8\u5e45\u6570\u636e\uff08\u4e1c\u65b9\u8d22\u5bcc\u5b9e\u65f6\uff09 ============
var ABNORMAL_DATA = ''' + em_data_json + ''';
var abnormalStocks = ABNORMAL_DATA.records || [];
var abnormalDataSource = ABNORMAL_DATA.market_status === 'open' ? 'api' : 'json';
var currentAbnormalFilter = 'all';

function renderAbnormalTable(filter) {
  var tbody = document.querySelector('#abnormal-table tbody');
  if (!tbody) return;
  var searchVal = '';
  var searchEl = document.getElementById('abnormal-search');
  if (searchEl) searchVal = searchEl.value.toLowerCase();
  var statusFilter = filter || 'all';

  var html = '';
  abnormalStocks.forEach(function(s) {
    if (statusFilter !== 'all' && s.status !== statusFilter) return;
    if (searchVal && s.name.toLowerCase().indexOf(searchVal) === -1 && s.code.indexOf(searchVal) === -1) return;

    var changeColor = parseFloat(s.change) >= 10 ? 'var(--red)' : 'var(--orange)';
    var statusBg = s.status === '\u6da8\u505c' ? 'var(--red)' :
                  s.status === '\u7ee7\u7eed\u62c9\u5347' ? 'var(--orange)' :
                  s.status === '\u9996\u6b21\u7a81\u7834' ? 'var(--green)' :
                  s.status === '\u660e\u663e\u56de\u843d' ? 'var(--purple)' : 'var(--muted)';

    var tier = (s.selection && s.selection.tier) || '\u89c2\u5bdf';
    var tierColors = {'\u9876\u7ea7\u5f39\u6027':'#ef4444','\u7a33\u5065\u5f39\u6027':'#f97316','\u8bd5\u9519\u5907\u9009':'#3b82f6','\u89c2\u5bdf':'#94a3b8','\u9ed1\u540d\u5355':'#6b7280'};
    var tierColor = tierColors[tier] || '#94a3b8';
    var thCount = (s.selection && s.selection.threshold_count) || 0;
    var bnScore = (s.selection && s.selection.bonus_score) || 0;
    var keyCat = s.key_catalyst || s.cause || '-';
    var bonusItemsList = (s.selection && s.selection.bonus_items) ? s.selection.bonus_items : [];
    var bonusItemsText = bonusItemsList.length > 0 ? bonusItemsList.slice(0,4).join(' / ') : '-';
    var coreEvent = s.core_event || '-';

    html += '<tr style="border-bottom:1px solid var(--rule);cursor:pointer;" onclick="showCauseDetail(\\''+s.code+'\\')">';
    html += '<td style="padding:8px;"><div style="font-weight:600;font-size:13px;">'+s.name+'</div><div style="font-size:11px;color:var(--muted);">'+s.code+' \u00b7 '+s.price+'\u5143</div></td>';
    html += '<td style="padding:8px;text-align:center;font-weight:700;color:'+changeColor+';">+'+s.change+'%</td>';
    html += '<td style="padding:8px;text-align:center;"><span style="font-size:11px;padding:2px 8px;border-radius:4px;background:'+statusBg+';color:#fff;font-weight:500;">'+s.status+'</span></td>';
    html += '<td style="padding:8px;"><span style="background:var(--bg);padding:2px 8px;border-radius:4px;font-size:11px;">'+s.industry+'</span></td>';
    html += '<td style="padding:8px;text-align:center;"><span style="font-size:11px;padding:2px 8px;border-radius:4px;background:'+tierColor+'20;color:'+tierColor+';font-weight:600;">'+tier+'</span></td>';
    html += '<td style="padding:8px;text-align:center;font-weight:600;">'+thCount+'/9</td>';
    html += '<td style="padding:8px;text-align:center;font-weight:700;color:'+tierColor+';">+'+bnScore+'/18</td>';
    html += '<td style="padding:8px;font-size:10.5px;color:var(--muted);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+bonusItemsText+'</td>';
    html += '<td style="padding:8px;text-align:right;font-size:11px;">'+s.turnover+'</td>';
    html += '<td style="padding:8px;text-align:right;font-size:11px;color:'+(parseFloat(s.netflow)>0?'var(--green)':'var(--red)')+';">'+(parseFloat(s.netflow)>0?'+':'')+s.netflow+'\u4ebf</td>';
    html += '<td style="padding:8px;font-size:11px;color:var(--ink2);max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:500;">'+coreEvent+'</td>';
    html += '<td style="padding:8px;font-size:11px;color:var(--ink2);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+s.cause+'</td>';
    html += '<td style="padding:8px;font-size:11px;color:var(--ink2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+keyCat+'</td>';
    html += '<td style="padding:8px;text-align:center;"><button style="padding:3px 10px;border-radius:4px;font-size:11px;border:1px solid var(--rule);background:var(--bg);cursor:pointer;color:var(--accent);" onclick="event.stopPropagation();showCauseDetail(\\''+s.code+'\\')">\u8be6\u60c5</button></td>';
    html += '</tr>';
  });

  tbody.innerHTML = html || '<tr><td colspan="14" style="padding:20px;text-align:center;color:var(--muted);">\u65e0\u5339\u914d\u7ed3\u679c</td></tr>';
}

function filterAbnormalTable() { renderAbnormalTable(currentAbnormalFilter || 'all'); }

function filterAbnormalByStatus(btn, status) {
  currentAbnormalFilter = status;
  document.querySelectorAll('.abnormal-filter-btn').forEach(function(b) {
    b.style.background = 'var(--bg2)';
    b.style.color = 'var(--ink2)';
  });
  btn.style.background = 'var(--accent)';
  btn.style.color = '#fff';
  renderAbnormalTable(status);
}

function showCauseDetail(code) {
  var stock = abnormalStocks.find(function(s) { return s.code === code; });
  if (!stock) return;
  var modal = document.getElementById('cause-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'cause-modal';
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;display:none;align-items:center;justify-content:center;';
    document.body.appendChild(modal);
  }
  var tagsHtml = (stock.tags || []).map(function(t){return '<span style="padding:3px 10px;background:var(--accent-light);border:1px solid var(--accent);border-radius:4px;font-size:11px;color:var(--accent);">'+t+'</span>';}).join(' ');
  var changeColor = parseFloat(stock.change) >= 10 ? 'var(--red)' : 'var(--orange)';
  var tier = (stock.selection && stock.selection.tier) || '\u89c2\u5bdf';
  var tierColors = {'\u9876\u7ea7\u5f39\u6027':'#ef4444','\u7a33\u5065\u5f39\u6027':'#f97316','\u8bd5\u9519\u5907\u9009':'#3b82f6','\u89c2\u5bdf':'#94a3b8','\u9ed1\u540d\u5355':'#6b7280'};
  var tierColor = tierColors[tier] || '#94a3b8';
  var bonusItemsHtml = (stock.selection && stock.selection.bonus_items && stock.selection.bonus_items.length > 0)
    ? stock.selection.bonus_items.map(function(b){return '<span style="padding:2px 8px;background:'+tierColor+'15;border:1px solid '+tierColor+'40;border-radius:4px;font-size:11px;color:'+tierColor+';margin:2px;display:inline-block;">'+b+'</span>';}).join('')
    : '<span style="color:var(--muted);font-size:12px;">\u6682\u65e0\u52a0\u5206\u9879</span>';
  var thresholdHits = (stock.selection && stock.selection.threshold_hits) ? stock.selection.threshold_hits : [];

  modal.innerHTML = '<div style="background:var(--bg2);border-radius:12px;padding:24px;max-width:560px;width:90%;max-height:80vh;overflow-y:auto;position:relative;">'
    +'<button onclick="document.getElementById(\\'cause-modal\\').style.display=\\'none\\'" style="position:absolute;top:12px;right:16px;background:none;border:none;font-size:20px;color:var(--muted);cursor:pointer;">&times;</button>'
    +'<div style="font-size:18px;font-weight:700;margin-bottom:4px;">'+stock.name+' <span style="font-size:13px;color:var(--muted);">'+stock.code+'</span></div>'
    +'<div style="font-size:14px;color:'+changeColor+';font-weight:700;margin-bottom:8px;">+'+stock.change+'% \u00b7 \u73b0\u4ef7'+stock.price+'\u5143</div>'
    +'<div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;">'+tagsHtml+'</div>'
    +'<div style="font-size:12px;color:var(--muted);margin-bottom:8px;">\u884c\u4e1a\uff1a'+stock.industry+' | \u6210\u4ea4\u989d\uff1a'+stock.turnover+' | \u51c0\u6d41\u5165\uff1a'+(parseFloat(stock.netflow)>0?'+':'')+stock.netflow+'\u4ebf | \u5e02\u503c\uff1a'+(stock.market_cap||'-')+'\u4ebf</div>'
    +'<div style="border-top:1px solid var(--rule);padding-top:12px;margin-bottom:12px;">'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:8px;">\U0001F3AF \u9009\u80a1\u6846\u67b6\u8bc4\u4f30</div>'
    +'<div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">'
    +'<span style="padding:3px 10px;background:'+tierColor+'20;color:'+tierColor+';border-radius:6px;font-size:12px;font-weight:600;">'+tier+'</span>'
    +'<span style="padding:3px 10px;background:var(--bg);color:var(--ink2);border-radius:6px;font-size:12px;">\u95e8\u69db '+((stock.selection&&stock.selection.threshold_count)||0)+'/9</span>'
    +'<span style="padding:3px 10px;background:var(--bg);color:'+tierColor+';border-radius:6px;font-size:12px;font-weight:700;">\u52a0\u5206 +'+((stock.selection&&stock.selection.bonus_score)||0)+'/18</span>'
    +'</div>'
    +(thresholdHits.length > 0 ? '<div style="font-size:11px;color:var(--muted);margin-bottom:6px;">\u95e8\u69db\u547d\u4e2d\uff1a'+thresholdHits.join(' / ')+'</div>' : '')
    +'<div style="margin-bottom:8px;">'+bonusItemsHtml+'</div>'
    +'</div>'
    +'<div style="border-top:1px solid var(--rule);padding-top:12px;margin-bottom:12px;">'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:8px;">\u26a1 \u6838\u5fc3\u4e8b\u4ef6\u6458\u8981</div>'
    +'<div style="font-size:13px;color:var(--accent);font-weight:600;line-height:1.6;">'+(stock.core_event||'-')+'</div>'
    +'</div>'
    +'<div style="border-top:1px solid var(--rule);padding-top:12px;margin-bottom:12px;">'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:8px;">\U0001F4DD AI\u4e3b\u56e0\u5f52\u56e0</div>'
    +'<div style="font-size:12.5px;color:var(--ink2);line-height:1.8;white-space:pre-line;">'+(stock.causeDetail||stock.cause||'\u6682\u65e0\u5f52\u56e0')+'</div>'
    +'</div>'
    +'<div style="border-top:1px solid var(--rule);padding-top:12px;">'
    +'<div style="font-size:13px;font-weight:600;margin-bottom:8px;">\U0001F525 \u8fd17\u5929\u50ac\u5316</div>'
    +'<div style="font-size:12.5px;color:var(--ink2);line-height:1.6;">'+(stock.key_catalyst||'\u6682\u65e0\u8fd1\u671f\u50ac\u5316\u4fe1\u606f')+'</div>'
    +'</div></div>';
  modal.style.display = 'flex';
  modal.onclick = function(e) { if (e.target === modal) modal.style.display = 'none'; };
}

// \u521d\u59cb\u5316
document.addEventListener('DOMContentLoaded', function() {
  renderAbnormalTable('all');
});
if (document.readyState !== 'loading') {
  renderAbnormalTable('all');
}

'''

        content = content[:abnormal_js_start] + new_abnormal_js + content[abnormal_js_end:]

    # === 4c. Inject CLS telegraph data ===
    cls_items = []
    cls_fetch_time = ""
    try:
        with open(CLS_DATA_PATH, 'r', encoding='utf-8') as f:
            cls_data = json.load(f)
        cls_items = cls_data.get("items", [])
        cls_fetch_time = cls_data.get("fetch_time", "")
    except:
        pass

    # Inject CLS data into JavaScript
    cls_js_data = json.dumps(cls_items, ensure_ascii=False)
    content = content.replace(
        'const clsData = []; // Will be populated by generation script',
        'const clsData = ' + cls_js_data + ';'
    )
    # Update fetch time label
    if cls_fetch_time:
        content = content.replace(
            'id="cls-fetch-time">加载中...',
            'id="cls-fetch-time">' + cls_fetch_time + ' 更新'
        )

    # === 5. Update nav badges ===
    today_data_nav = feed_data.get(sorted_dates[0], []) if sorted_dates else []
    sa_count_nav = len([x for x in today_data_nav if x["priority"] in ("S", "A")])
    total_today_nav = len(today_data_nav)
    s_count_nav = len([x for x in today_data_nav if x["priority"] == "S"])

    # Update feed page badge
    content = re.sub(
        r'data-page="feed"[^>]*>.*?<span class="nav-badge blue">\d+</span>',
        'data-page="feed">\n          <span class="nav-icon">\U0001F4F0</span>\u5168\u90e8\u4fe1\u606f\n          <span class="nav-badge blue">' + str(total_today_nav) + '</span>',
        content,
        flags=re.DOTALL
    )

    # Update dashboard page badge
    content = re.sub(
        r'data-page="dashboard"[^>]*>.*?<span class="nav-badge blue">\d+</span>',
        'data-page="dashboard">\n          <span class="nav-icon">\U0001F4CA</span>\u4eca\u65e5\u603b\u89c8\n          <span class="nav-badge blue">' + str(sa_count_nav) + '</span>',
        content,
        flags=re.DOTALL
    )


    # Update attention page badge
    content = re.sub(
        r'data-page="attention"[^>]*>.*?<span class="nav-badge[^"]*">\d+</span>',
        'data-page="attention">\n          <span class="nav-icon">\u26a0\ufe0f</span>\u7279\u522b\u5173\u6ce8\n          <span class="nav-badge">' + str(len(stock_results)) + '</span>',
        content,
        flags=re.DOTALL
    )


    # Update abnormal page badge
    content = re.sub(
        r'data-page="abnormal"[^>]*>.*?</div>',
        'data-page="abnormal">\n          <span class="nav-icon">\U0001F4C8</span>\u6bcf\u65e5\u5f02\u52a8\u6da8\u5e45\n          <span class="nav-badge orange">' + str(em_total) + '</span>\n        </div>',
        content,
        flags=re.DOTALL
    )


    # Update CLS telegraph page badge
    cls_count = len(cls_items) if cls_items else 0
    content = re.sub(
        r'data-page="cls"[^>]*>.*?<span class="nav-badge blue">\d+</span>',
        'data-page="cls">\n          <span class="nav-icon">\u26a1</span>\u8d22\u8054\u793e\u7535\u62a5\n          <span class="nav-badge blue">' + str(cls_count) + '</span>',
        content,
        flags=re.DOTALL
    )
    # Update mobile tab badge (must match only mobile-tab, not nav-item)
    content = re.sub(
        r'class="mobile-tab"[^>]*data-page="cls"[^>]*>.*?<span class="tab-badge">\d+</span>',
        'class="mobile-tab" data-page="cls" style="position:relative">\n      <span class="tab-icon">\u26a1</span><span>\u7535\u62a5</span>\n      <span class="tab-badge">' + str(cls_count) + '</span>',
        content,
        flags=re.DOTALL
    )


    # Write output
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(content)

    # Print summary
    print("OK: Generated HTML with " + str(len(sorted_dates)) + " dates")
    for d in sorted_dates:
        day_data = feed_data[d]
        s_count = len([x for x in day_data if x["priority"] == "S"])
        a_count = len([x for x in day_data if x["priority"] == "A"])
        b_count = len([x for x in day_data if x["priority"] == "B"])
        c_count = len([x for x in day_data if x["priority"] == "C"])
        print("  " + d + ": " + str(len(day_data)) + " posts (S:" + str(s_count) + " A:" + str(a_count) + " B:" + str(b_count) + " C:" + str(c_count) + ")")
    print("Output: " + OUTPUT_PATH)

if __name__ == "__main__":
    main()
