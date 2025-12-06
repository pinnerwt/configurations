#!/usr/bin/env python3
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from alert_system import send_to_telegram

import requests

RSS_URL = "https://news.ycombinator.com/rss"
STATE_FILE = "hn_state.json"
INTERVAL_SECONDS = 60  # check every minute


def fetch_rss(url: str) -> str:
    """Download the RSS feed and return the raw XML text."""
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.text


def parse_items(xml_text: str):
    """Parse RSS XML and return a list of items with title, link, pubdate."""
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    items = []
    for item in channel.findall("item"):
        title = item.findtext("title", default="(no title)")
        link = item.findtext("link", default="")

        pub_date_str = item.findtext("pubDate", default="")
        try:
            pub_date = parsedate_to_datetime(pub_date_str)
        except Exception:
            continue

        items.append(
            {
                "title": title,
                "link": link,  # ← external URL from <link>
                "pub_date": pub_date,
                "pub_date_str": pub_date_str,
            }
        )

    return items


def load_last_pub_date():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return parsedate_to_datetime(data.get("last_pub_date"))
    except Exception:
        return None


def save_last_pub_date(pub_date_str: str):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_pub_date": pub_date_str}, f)


def print_items(items):
    for item in items:
        print(item["title"])
        print(item["link"])
        print()  # blank line
        send_to_telegram(f"{item['title']},{item['link']}")



def check_once(last_pub_date):
    try:
        xml_text = fetch_rss(RSS_URL)
    except Exception as e:
        print(f"[error] Failed to fetch RSS: {e}", file=sys.stderr)
        return last_pub_date

    items = parse_items(xml_text)
    if not items:
        return last_pub_date

    # sort oldest → newest
    items.sort(key=lambda x: x["pub_date"])

    # First run: print everything
    if last_pub_date is None:
        print_items(items)
        newest = items[-1]
        save_last_pub_date(newest["pub_date_str"])
        return newest["pub_date"]

    # Subsequent runs: only new items
    new_items = [i for i in items if i["pub_date"] > last_pub_date]

    if new_items:
        print_items(new_items)
        newest = new_items[-1]
        save_last_pub_date(newest["pub_date_str"])
        return newest["pub_date"]

    return last_pub_date


def main():
    last_pub_date = load_last_pub_date()

    try:
        while True:
            last_pub_date = check_once(last_pub_date)
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping.")


if __name__ == "__main__":
    main()
