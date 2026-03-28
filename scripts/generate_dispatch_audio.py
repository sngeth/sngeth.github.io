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
import numpy as np
from mlx_audio.tts.utils import load_model
from mlx_audio.audio_io import write as audio_write
from pydub import AudioSegment

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


def generate_story_audio(
    model, text: str, voice: str, output_path: Path
) -> float | None:
    """Generate MP3 for a single story. Returns duration in seconds or None on failure."""
    wav_path = output_path.with_suffix(".wav")
    try:
        for result in model.generate(text=text, voice=voice):
            audio_write(str(wav_path), np.array(result.audio), result.sample_rate)
            log.info(
                "  Generated %.1fs audio (RTF: %.2fx, peak mem: %.1fGB)",
                result.audio_duration,
                result.real_time_factor,
                result.peak_memory_usage,
            )
    except Exception as e:
        log.warning("  TTS failed: %s", e)
        return None

    # Encode to 64kbps mono MP3
    segment = AudioSegment.from_wav(str(wav_path))
    segment = segment.set_channels(1)
    segment.export(str(output_path), format="mp3", bitrate="64k")
    wav_path.unlink()

    duration_sec = len(segment) / 1000.0
    return duration_sec


def generate_full_edition(story_mp3s: list[Path], output_path: Path) -> float:
    """Concatenate story MP3s with 1.5s silence between each. Returns total duration."""
    silence = AudioSegment.silent(duration=1500)
    combined = AudioSegment.empty()
    for i, mp3 in enumerate(story_mp3s):
        if i > 0:
            combined += silence
        combined += AudioSegment.from_mp3(str(mp3))
    combined.export(str(output_path), format="mp3", bitrate="64k")
    return len(combined) / 1000.0


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

    # Phase 2: Generate audio
    log.info("Loading Voxtral model (first run downloads ~8GB)...")
    model = load_model(MODEL_ID)

    tmp_dir = Path(tempfile.mkdtemp(prefix="dispatch-audio-"))
    log.info("Working directory: %s", tmp_dir)

    story_mp3s = []
    story_durations = {}
    for i, story in enumerate(all_stories, 1):
        mp3_name = f"story-{i:02d}.mp3"
        mp3_path = tmp_dir / mp3_name
        log.info("Generating %s: %s...", mp3_name, story["headline"][:50])
        duration = generate_story_audio(model, story["text"], args.voice, mp3_path)
        if duration is not None:
            story_mp3s.append(mp3_path)
            story_durations[mp3_name] = duration
            story["mp3_name"] = mp3_name
            story["duration"] = duration
        else:
            log.warning("Skipping %s due to generation failure", mp3_name)

    if not story_mp3s:
        log.error("All story generations failed. Exiting.")
        sys.exit(1)

    full_path = tmp_dir / "full-edition.mp3"
    log.info("Concatenating %d stories into full-edition.mp3...", len(story_mp3s))
    full_duration = generate_full_edition(story_mp3s, full_path)
    log.info("Full edition: %.1f min", full_duration / 60)

    # Phases 3-4 will be added in subsequent tasks
    log.info("Upload and HTML patching not yet implemented.")
    log.info("Audio files in: %s", tmp_dir)


if __name__ == "__main__":
    main()
