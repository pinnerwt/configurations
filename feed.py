import math
import subprocess
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from wcwidth import wcswidth  # pip install wcwidth

FEED_URL = "https://trends.google.com/trending/rss?geo=TW"
POLL_INTERVAL_SECONDS = 60  # fetch every minute

MAX_TRAFFIC = 2_000_000  # cap traffic at 2M for plotting
MAX_BAR_LEN = 60  # max number of '#' characters in bar

POPUP_TMP_FILE = "/tmp/google_trends_popup.txt"  # temp file for tmux popup content


def fetch_rss_xml(url: str) -> bytes:
    """Download the RSS XML from the given URL."""
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def parse_items(xml_data: bytes):
    """
    Parse the RSS XML and return a list of items.

    Each item:
    {
        "title": str,
        "traffic": int,
        "pubdate": str,
        "news_items": [
            {"title": str, "source": str, "url": str},
            ...
        ]
    }
    """
    root = ET.fromstring(xml_data)
    ns = {"ht": "https://trends.google.com/trending/rss"}

    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        pubdate = (item.findtext("pubDate") or "").strip()
        traffic_raw = (
            item.findtext("ht:approx_traffic", "", namespaces=ns) or ""
        ).strip()

        if traffic_raw:
            # Handle "1,000+" / "1000+"
            traffic_raw_clean = traffic_raw.replace(",", "").replace("+", "")
            try:
                traffic = int(traffic_raw_clean)
            except ValueError:
                traffic = 0
        else:
            traffic = 0

        news_items = []
        for ni in item.findall("ht:news_item", ns):
            ni_title = (
                ni.findtext("ht:news_item_title", default="", namespaces=ns) or ""
            ).strip()
            ni_source = (
                ni.findtext("ht:news_item_source", default="", namespaces=ns) or ""
            ).strip()
            ni_url = (
                ni.findtext("ht:news_item_url", default="", namespaces=ns) or ""
            ).strip()

            if ni_title:
                news_items.append(
                    {
                        "title": ni_title,
                        "source": ni_source,
                        "url": ni_url,
                    }
                )

        items.append(
            {
                "title": title,
                "traffic": traffic,
                "pubdate": pubdate,
                "news_items": news_items,
            }
        )

    return items


def scaled_bar_len(traffic: int) -> int:
    """
    Compute bar length using log10(traffic), with:
    - traffic clamped to [1, MAX_TRAFFIC]
    - result scaled to [1, MAX_BAR_LEN]
    """
    if traffic <= 0:
        traffic = 1

    t = min(traffic, MAX_TRAFFIC)
    log_t = math.log10(t)
    log_max = math.log10(MAX_TRAFFIC)
    frac = log_t / log_max if log_max > 0 else 0.0

    bar_len = int(frac * MAX_BAR_LEN)
    return max(bar_len, 1)


def tmux_popup(new_items):
    """
    Show a tmux popup summarizing new items.
    Uses a temp file to avoid shell-quoting issues.
    """
    if not new_items:
        return

    lines = []
    lines.append(
        f"New Google Trends ({len(new_items)} item(s)) @ {datetime.now().strftime('%H:%M:%S')}"
    )
    lines.append("-" * 60)

    # Show up to 10 new items in popup
    for it in new_items[:10]:
        title = it["title"]
        traffic = it["traffic"]
        lines.append(f"- {title} ({traffic})")

        # Optionally show first news headline
        if it["news_items"]:
            first_news = it["news_items"][0]
            src = first_news["source"]
            ntitle = first_news["title"]
            if src:
                lines.append(f"    [{src}] {ntitle}")
            else:
                lines.append(f"    {ntitle}")

    text = "\n".join(lines) + "\n"

    try:
        # Write content to temp file
        with open(POPUP_TMP_FILE, "w", encoding="utf-8") as f:
            f.write(text)

        # Open popup that just cats the file
        subprocess.run(
            [
                "tmux",
                "popup",
                "-w",
                "70%",  # width
                "-h",
                "40%",  # height
                "-E",
                f"cat {POPUP_TMP_FILE}",
            ],
            check=False,
        )
    except Exception:
        # Fail silently if tmux is not available or popup fails
        pass


def tmux_set_message(msg: str):
    try:
        subprocess.run(
            ["tmux", "set-option", "-gq", "@trend_message", msg], check=False
        )
    except Exception:
        pass


def print_new_items(new_items, min_title_width=20):
    """
    Print new trend items + their news headlines in the main pane.
    Layout:
      <title padded> | <bar> (<traffic>)  [pubdate]
          - [source] news_title (url)
    """
    if not new_items:
        return

    print("\n" + "=" * 100)
    print(f"New items at {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 100)

    # 1) title width for left alignment (handles CJK)
    max_title_width = max(wcswidth(it["title"]) for it in new_items)
    title_pad_to = max(max_title_width, min_title_width)

    # 2) build left parts and measure widths
    left_parts = []  # (left_string, pubdate, news_items)
    left_widths = []

    for it in new_items:
        title = it["title"]
        traffic = it["traffic"]

        pad = title_pad_to - wcswidth(title)
        padded_title = title + (" " * pad)

        bar = "#" * scaled_bar_len(traffic)
        left = f"{padded_title} | {bar} ({traffic})"

        left_parts.append((left, it["pubdate"], it["news_items"]))
        left_widths.append(wcswidth(left))

    max_left_width = max(left_widths)

    # 3) print lines with aligned timestamps, then indented news
    for (left, pubdate, news_items), lw in zip(left_parts, left_widths):
        gap = max_left_width - lw
        spaces = " " * gap
        print(f"{left}{spaces}  [{pubdate}]")

        for ni in news_items:
            src = ni["source"]
            ntitle = ni["title"]
            url = ni["url"]

            if src:
                head = f"[{src}] {ntitle}"
            else:
                head = ntitle

            if url:
                line = f"    - {head} ({url})"
            else:
                line = f"    - {head}"

            print(line)


def main():
    # ensure each entry (title + pubdate) is shown only once
    seen = set()

    while True:
        try:
            xml_data = fetch_rss_xml(FEED_URL)
            items = parse_items(xml_data)

            new_items = []
            for it in items:
                key = f"{it['title']}|{it['pubdate']}"
                if key not in seen:
                    seen.add(key)
                    new_items.append(it)
                    tmux_set_message(key)

            # Print to the current tmux pane
            print_new_items(new_items)

            # Show popup summary in tmux
            # tmux_popup(new_items)

        except Exception as e:
            print(f"Error while fetching/parsing feed: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
