#!/usr/bin/env python3
"""Fetch RSS/Atom feeds and write items to _data/reading_list.yml.

Uses only the Python standard library (no pip dependencies).
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

FEEDS_FILE = Path(__file__).resolve().parent.parent / "_data" / "feeds.yml"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "_data" / "reading_list.yml"
MAX_ITEMS_PER_FEED = 5
USER_AGENT = "SidBlogFeedFetcher/1.0"

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
}


def parse_simple_yaml(text):
    """Parse the simple flat list-of-dicts YAML used in feeds.yml."""
    items = []
    current = None
    for line in text.splitlines():
        line = line.split("#")[0].rstrip()  # strip comments
        if not line.strip():
            continue
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = {}
            line = line[2:]
        if current is None:
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            current[key.strip()] = val.strip()
    if current is not None:
        items.append(current)
    return items


def yaml_escape(s):
    """Escape a string for safe YAML output."""
    if not s:
        return '""'
    if any(c in s for c in ":#{}[]&*?|>!%@`'\",\n"):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def write_yaml(items, path):
    """Write a list of dicts as YAML."""
    lines = []
    for item in items:
        first = True
        for key, val in item.items():
            prefix = "- " if first else "  "
            lines.append(f"{prefix}{key}: {yaml_escape(val)}")
            first = False
    path.write_text("\n".join(lines) + "\n")


def parse_date(date_str):
    """Try common RSS/Atom date formats and return an ISO date string."""
    if not date_str:
        return ""
    date_str = date_str.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return ""


def fetch_feed(url):
    """Fetch and return the raw XML bytes for a feed URL."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=15) as resp:
            return resp.read()
    except (URLError, TimeoutError, OSError) as e:
        print(f"  WARN: could not fetch {url}: {e}")
        return None


def parse_rss_items(root):
    """Parse items from an RSS 2.0 feed."""
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        date = parse_date(item.findtext("pubDate"))
        if title and link:
            items.append({"title": title, "url": link, "date": date})
    return items


def parse_atom_items(root):
    """Parse entries from an Atom feed."""
    ns = NAMESPACES["atom"]
    items = []
    for entry in root.findall(f"{{{ns}}}entry"):
        title = entry.findtext(f"{{{ns}}}title", "").strip()
        link_el = entry.find(f"{{{ns}}}link[@rel='alternate']")
        if link_el is None:
            link_el = entry.find(f"{{{ns}}}link")
        link = link_el.get("href", "").strip() if link_el is not None else ""
        date = parse_date(
            entry.findtext(f"{{{ns}}}published", "")
            or entry.findtext(f"{{{ns}}}updated", "")
        )
        if title and link:
            items.append({"title": title, "url": link, "date": date})
    return items


def parse_feed(xml_bytes):
    """Detect feed type and parse items."""
    root = ET.fromstring(xml_bytes)
    if root.tag == f'{{{NAMESPACES["atom"]}}}feed':
        return parse_atom_items(root)
    return parse_rss_items(root)


def main():
    feeds = parse_simple_yaml(FEEDS_FILE.read_text())

    all_items = []
    for feed in feeds:
        name = feed["name"]
        url = feed["url"]
        category = feed["category"]
        print(f"Fetching: {name} ({url})")

        xml_bytes = fetch_feed(url)
        if xml_bytes is None:
            continue

        try:
            items = parse_feed(xml_bytes)
        except ET.ParseError as e:
            print(f"  WARN: could not parse {name}: {e}")
            continue

        for item in items[:MAX_ITEMS_PER_FEED]:
            item["source"] = name
            item["category"] = category
            all_items.append(item)

    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    write_yaml(all_items, OUTPUT_FILE)
    print(f"Wrote {len(all_items)} items to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
