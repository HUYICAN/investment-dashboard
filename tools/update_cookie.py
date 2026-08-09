#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract zsxq cookie from local browser and update GitHub Secret.

Run this on your Mac when the cookie expires (every 7-30 days).
Requires GitHub CLI (gh) to be installed and authenticated.

Usage:
    python3 tools/update_cookie.py [--repo OWNER/REPO]

Prerequisites:
    brew install gh
    gh auth login
"""

import os
import sys
import sqlite3
import subprocess
import argparse
from pathlib import Path

DEFAULT_REPO = ""  # Set your repo here, e.g. "yourname/investment-dashboard"

# Find gh CLI (may be in ~/bin if installed manually)
def find_gh():
    for p in ["gh", os.path.expanduser("~/bin/gh"), "/usr/local/bin/gh"]:
        try:
            result = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return p
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return "gh"

COOKIE_DB_PATHS = [
    str(Path.home() / "Library/Application Support/TRAE SOLO CN/Partitions/trae-webview/Cookies"),
    str(Path.home() / "Library/Application Support/TRAE SOLO CN/Cookies"),
    str(Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies"),
    str(Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies"),
]


def extract_zsxq_cookie():
    """Extract zsxq cookies from browser SQLite database."""
    for db_path in COOKIE_DB_PATHS:
        if not os.path.exists(db_path):
            continue
        print("  Trying: %s" % db_path)
        try:
            uri = "file:%s?mode=ro&immutable=1" % db_path.replace(" ", "%20")
            conn = sqlite3.connect(uri, uri=True)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT host_key, name, value FROM cookies WHERE host_key LIKE '%zsxq%'"
            )
            rows = cursor.fetchall()
            conn.close()

            if rows:
                cookie_str = "; ".join("%s=%s" % (name, val) for host, name, val in rows)
                print("  Found %d cookie entries" % len(rows))
                return cookie_str
        except Exception as e:
            print("  Error: %s" % e)
    return None


def update_github_secret(repo, secret_name, secret_value):
    """Update a GitHub Secret using gh CLI."""
    gh = find_gh()
    cmd = [
        gh, "secret", "set", secret_name,
        "--repo", repo,
        "--body", secret_value,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("  Secret %s updated successfully" % secret_name)
            return True
        else:
            print("  Failed to update secret: %s" % result.stderr.strip())
            return False
    except FileNotFoundError:
        print("  GitHub CLI (gh) not found. Install with: brew install gh")
        return False
    except Exception as e:
        print("  Error: %s" % e)
        return False


def main():
    parser = argparse.ArgumentParser(description="Update zsxq cookie in GitHub Secrets")
    parser.add_argument("--repo", type=str, default=DEFAULT_REPO,
                        help="GitHub repo in OWNER/REPO format")
    args = parser.parse_args()

    if not args.repo:
        print("Error: --repo is required (e.g. --repo yourname/investment-dashboard)")
        print("  Or set DEFAULT_REPO in this script.")
        sys.exit(1)

    print("=" * 50)
    print("Extracting zsxq cookie from browser...")
    print("=" * 50)

    cookie = extract_zsxq_cookie()
    if not cookie:
        print("\nFailed to extract cookie!")
        print("Make sure you have logged in to zsxq.com in your browser.")
        sys.exit(1)

    print("\nCookie extracted (length: %d chars)" % len(cookie))

    # Verify cookie looks valid
    if "zsxqaccesssid" not in cookie.lower() and "zsxq_access_sid" not in cookie.lower():
        print("\nWarning: Cookie doesn't contain expected zsxq session tokens.")
        print("Make sure you're logged in to wx.zsxq.com")

    print("\n" + "=" * 50)
    print("Updating GitHub Secret: ZSXQ_COOKIE")
    print("=" * 50)

    success = update_github_secret(args.repo, "ZSXQ_COOKIE", cookie)

    if success:
        print("\nDone! The pipeline will use the new cookie on next run.")
        print("You can trigger a manual run from GitHub Actions tab.")
    else:
        print("\nFailed to update secret. See errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
