#!/usr/bin/env python3
"""
Poll Google Trends TW trending RSS every minute.
Print newest element(s) if any.
Resume correctly after restart using persisted state.

Correct link behavior:
- Use ht_news_item_url if present
- Use ht_news_item_title as the title if present
- Ignore entry.link (it's always the feed URL)
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import feedparser
import requests

RSS_URL = "https://trends.google.com.tw/trending/rss?geo=TW"
STATE_FILE = "rss_state.json"
POLL_SECONDS = 60
TIMEOUT = 15


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"last_seen_uid": None, "updated_at": None}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_seen_uid": None, "updated_at": None}


def save_state(path: str, state: Dict[str, Any]) -> None:
    state = dict(state)
    state["updated_at"] = utc_now_iso()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def fetch_feed(url: str) -> feedparser.FeedParserDict:
    headers = {"User-Agent": "rss-poller/1.0"}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.content)


def entry_uid(entry: feedparser.FeedParserDict) -> str:
    """
    Stable ID for resume purposes.
    Prefer ht_news_item_url; otherwise fall back to title + published time.
    """
    url = entry.get("ht_news_item_url")
    if url:
        return str(url)

    title = entry.get("title", "")
    published = entry.get("published", "")
    return f"{title}::{published}"


def extract_item(entry: feedparser.FeedParserDict) -> Optional[Dict[str, str]]:
    """
    Extract the *actual* item Google Trends intends:
    - title: ht_news_item_title (preferred)
    - url:   ht_news_item_url (preferred)
    """
    url = entry.get("ht_news_item_url")
    title = entry.get("ht_news_item_title") or entry.get("title")

    if not url and not title:
        return None

    return {
        "keyword": entry.get("title"),
        "title": title or "",
        "url": url or "",
        "published": entry.get("published", "") or "",
        "source": entry.get("ht_news_item_source", "") or "",
    }


def format_item(item: Dict[str, str]) -> str:
    lines = [f"🆕 {item['keyword']}", f"   Title: {item['title']}"]
    if item["published"]:
        lines.append(f"   Published: {item['published']}")
    if item["url"]:
        lines.append(f"   Link: {item['url']}")
    if item["source"]:
        lines.append(f"   Source: {item['source']}")
    return "\n".join(lines)


def get_new_entries(
    entries: List[feedparser.FeedParserDict],
    last_seen_uid: Optional[str],
) -> List[feedparser.FeedParserDict]:
    if not entries or not last_seen_uid:
        return []

    new_items = []
    for e in entries:
        if entry_uid(e) == last_seen_uid:
            break
        new_items.append(e)
    return new_items


def main() -> None:
    state = load_state(STATE_FILE)
    last_seen_uid = state.get("last_seen_uid")

    print(f"Polling: {RSS_URL}")
    print(f"State:   {STATE_FILE}")
    if last_seen_uid:
        print(f"Resuming from last_seen_uid={last_seen_uid}")
    else:
        last_seen_uid = 1
        print(
            "No prior state found. First run will record current item without printing."
        )

    while True:
        try:
            feed = fetch_feed(RSS_URL)
            entries = list(feed.entries or [])

            if entries:
                newest = entries[0]
                newest_uid = entry_uid(newest)

                if not last_seen_uid:
                    # First run: initialize state only
                    last_seen_uid = newest_uid
                    state["last_seen_uid"] = last_seen_uid
                    save_state(STATE_FILE, state)
                else:
                    new_entries = get_new_entries(entries, last_seen_uid)

                    if new_entries:
                        for e in reversed(new_entries):
                            item = extract_item(e)
                            if item:
                                print(format_item(item))
                                print("-" * 60)

                        last_seen_uid = newest_uid
                        state["last_seen_uid"] = last_seen_uid
                        save_state(STATE_FILE, state)

        except Exception as e:
            print(f"[{utc_now_iso()}] Error: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
