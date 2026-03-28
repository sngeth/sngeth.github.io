#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mlx-audio",
#     "beautifulsoup4",
#     "lxml",
#     "pydub",
#     "numpy",
# ]
# ///
"""Generate Voxtral TTS audio for The Sid Dispatch.

Extracts article text from dispatch HTML, generates per-story and
full-edition MP3s via Voxtral on Apple Silicon, uploads to GitHub
Releases, and patches HTML with <audio> players.
"""

import argparse
import logging
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

DISPATCH_DIR = Path(__file__).resolve().parent.parent / "dispatch"
REPO = "sngeth/sngeth.github.io"
MODEL_ID = "mlx-community/Voxtral-4B-TTS-2603-mlx-bf16"
DEFAULT_VOICE = "casual_male"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Date for the release tag (default: today)",
    )
    p.add_argument("--voice", default=DEFAULT_VOICE, help="Voxtral voice preset")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract text and print plan without generating audio",
    )
    return p.parse_args()


def clean_text(raw: str) -> str:
    """Strip markdown-style *emphasis* and collapse whitespace."""
    text = re.sub(r"\*([^*]+)\*", r"\1", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_stories(html_path: Path) -> list[dict]:
    """Extract stories from a dispatch HTML file.

    Returns list of dicts with keys: element, headline, text, source.
    Works for both page 1 (uses .lead/.sec/.tert) and page 2 (anonymous divs).
    """
    soup = BeautifulSoup(html_path.read_text(), "lxml")
    stories = []

    # HN stories: find elements inside .hn-col that have both .headline and .body-text
    hn_col = soup.select_one(".hn-col")
    if hn_col:
        for el in hn_col.find_all(True, recursive=True):
            headline_el = el.find(class_="headline", recursive=False)
            body_el = el.find(class_="body-text", recursive=False)
            if headline_el and body_el:
                headline = clean_text(headline_el.get_text())
                deck_el = el.find(class_="deck", recursive=False)
                deck = clean_text(deck_el.get_text()) if deck_el else ""

                # Get body text, skipping pull quotes
                body_parts = []
                for child in body_el.children:
                    if hasattr(child, "get") and "pull-quote" in (
                        child.get("class") or []
                    ):
                        continue
                    text = child.get_text() if hasattr(child, "get_text") else str(child)
                    cleaned = clean_text(text)
                    if cleaned:
                        body_parts.append(cleaned)
                body = " ".join(body_parts)

                parts = [headline]
                if deck:
                    parts.append(deck)
                parts.append(body)

                stories.append(
                    {
                        "element": el,
                        "headline": headline,
                        "text": ". ".join(parts),
                        "source": "hn",
                    }
                )

    # X/Twitter items
    for el in soup.select(".x-item"):
        handle_el = el.select_one(".x-handle")
        headline_el = el.select_one(".x-headline")
        body_el = el.select_one(".x-body")
        if headline_el:
            handle = clean_text(handle_el.get_text()).replace("\U0001d54f", "").strip() if handle_el else ""
            headline = clean_text(headline_el.get_text())
            body = clean_text(body_el.get_text()) if body_el else ""
            parts = ["From X"]
            if handle:
                parts[0] = f"From X. {handle} says"
            parts.append(headline)
            if body:
                parts.append(body)
            stories.append(
                {
                    "element": el,
                    "headline": headline,
                    "text": ". ".join(parts),
                    "source": "x",
                }
            )

    return stories


def main() -> None:
    args = parse_args()

    # Extract stories from both pages
    all_stories = []
    for page in ["index.html", "page2.html"]:
        path = DISPATCH_DIR / page
        if not path.exists():
            if page == "index.html":
                log.error("dispatch/index.html not found")
                sys.exit(1)
            log.warning("%s not found, skipping", page)
            continue
        stories = extract_stories(path)
        log.info("Extracted %d stories from %s", len(stories), page)
        all_stories.extend(stories)

    if not all_stories:
        log.warning("No stories found. Nothing to do.")
        sys.exit(0)

    tag = f"dispatch-audio-{args.date.isoformat()}"
    base_url = f"https://github.com/{REPO}/releases/download/{tag}"

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN -- {len(all_stories)} stories found")
        print(f"Release tag: {tag}")
        print(f"{'='*60}\n")
        for i, story in enumerate(all_stories, 1):
            words = len(story["text"].split())
            print(f"  story-{i:02d}.mp3  [{story['source']:>2}]  ~{words} words")
            print(f"    {story['headline'][:70]}...")
        print(f"\n  full-edition.mp3  (concatenation of all above)")
        print(f"\nEstimated audio: ~{sum(len(s['text'].split()) for s in all_stories) // 150} min")
        return

    # Phases 2-4 will be added in subsequent tasks
    log.info("Audio generation not yet implemented. Use --dry-run to preview.")


if __name__ == "__main__":
    main()
