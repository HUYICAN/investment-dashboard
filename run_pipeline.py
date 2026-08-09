#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloud pipeline orchestrator for the investment research workbench.

Runs the full pipeline:
1. Fetch zsxq data (cookie from env var)
2. Update feed history
3. Fetch eastmoney abnormal stocks
4. Fetch CLS telegraph
5. Generate HTML workspace

HTML is deployed to GitHub Pages by the workflow.

Usage:
    python3 run_pipeline.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(REPO_DIR, "scripts")
DATA_DIR = os.path.join(REPO_DIR, "data")
PYTHON = sys.executable

ZSXQ_LATEST = os.path.join(DATA_DIR, "zsxq_latest.json")
HTML_OUTPUT = os.path.join(DATA_DIR, "touyan_workspace_final.html")


def log(msg):
    now = datetime.now(BJT).strftime("%Y-%m-%d %H:%M:%S")
    print("[%s] %s" % (now, msg), flush=True)


def run_script(script_name, args=None):
    """Run a Python script and return success status."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [PYTHON, script_path]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_DIR,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            log("  Script %s FAILED (exit %d)" % (script_name, result.returncode))
            return False
        else:
            log("  Script %s OK" % script_name)
            return True
    except subprocess.TimeoutExpired:
        log("  Script %s timed out" % script_name)
        return False
    except Exception as e:
        log("  Script %s error: %s" % (script_name, e))
        return False


def main():
    log("=" * 60)
    log("投研工作台云端管道启动")
    log("=" * 60)

    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Seed feed_history.json from repo if not in cache
    history_path = os.path.join(DATA_DIR, "feed_history.json")
    seed_path = os.path.join(REPO_DIR, "seed", "feed_history.json")
    if not os.path.exists(history_path) and os.path.exists(seed_path):
        import shutil
        shutil.copy2(seed_path, history_path)
        log("  Seeded feed_history.json from seed file")

    zsxq_ok = False
    history_ok = False
    eastmoney_ok = False
    cls_ok = False
    generate_ok = False

    # Step 1: Fetch zsxq data
    log("\n[1/5] 抓取知识星球数据...")
    zsxq_ok = run_script("fetch_zsxq.py")

    # Step 2: Update feed history
    if zsxq_ok:
        log("\n[2/5] 更新历史数据...")
        history_ok = run_script("update_history.py", [ZSXQ_LATEST])
    else:
        log("\n[2/5] 跳过历史数据更新（无新数据）")

    # Step 3: Fetch eastmoney data
    log("\n[3/5] 运行东方财富异动监控...")
    eastmoney_ok = run_script("fetch_eastmoney.py")

    # Step 4: Fetch CLS telegraph
    log("\n[4/5] 抓取财联社电报快讯...")
    cls_ok = run_script("fetch_cls.py", ["--pages", "1"])

    # Step 5: Generate HTML
    log("\n[5/5] 生成HTML工作台...")
    generate_ok = run_script("generate_html.py")

    # Summary
    log("\n" + "=" * 60)
    log("更新完成:")
    log("  知识星球: %s" % ("成功" if zsxq_ok else "失败/跳过"))
    log("  历史数据: %s" % ("成功" if history_ok else "跳过"))
    log("  异动监控: %s" % ("成功" if eastmoney_ok else "失败"))
    log("  财联社电报: %s" % ("成功" if cls_ok else "失败"))
    log("  HTML生成: %s" % ("成功" if generate_ok else "失败"))
    log("=" * 60)

    # Exit with error if HTML generation failed
    if not generate_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
