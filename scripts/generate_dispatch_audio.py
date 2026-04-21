#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beautifulsoup4",
#     "lxml",
#     "pydub",
#     "requests",
#     "python-dotenv",
# ]
# ///
"""Generate ElevenLabs TTS audio for The Sid Dispatch.

Extracts article text from dispatch HTML, generates per-story and
full-edition MP3s via ElevenLabs API, uploads to GitHub Releases,
and patches HTML with <audio> players.
"""

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
from pydub import AudioSegment

DISPATCH_DIR = Path(__file__).resolve().parent.parent / "dispatch"
AUDIO_DIR = DISPATCH_DIR / "audio"
REPO = "sngeth/sngeth.github.io"
R2_BUCKET = "dispatch-audio"
R2_PUBLIC_URL = "https://pub-9763ba4e3f6c471f86b2b40bc004a479.r2.dev"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVENLABS_MODEL = "eleven_turbo_v2_5"
DEFAULT_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam - popular news/narration voice

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
    p.add_argument("--voice", default=DEFAULT_VOICE, help="ElevenLabs voice ID")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract text and print plan without generating audio",
    )
    p.add_argument(
        "--patch-only",
        action="store_true",
        help="Skip audio generation; patch HTML using existing release assets",
    )
    return p.parse_args()


def clean_text(raw: str) -> str:
    """Strip markdown-style *emphasis* and normalize for TTS."""
    text = re.sub(r"\*([^*]+)\*", r"\1", raw)
    # Replace em-dashes with commas (em-dashes confuse TTS models)
    text = text.replace("\u2014", ", ")
    # Collapse repeated punctuation and whitespace
    text = re.sub(r",\s*,", ",", text)
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
                # Strip permalink/share buttons before extracting text
                for junk in headline_el.select(".permalink"):
                    junk.decompose()
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
            # Strip permalink/share buttons before extracting text
            for junk in el.select(".permalink"):
                junk.decompose()
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


def generate_story(text: str, voice: str, output_path: Path) -> float | None:
    """Generate an MP3 for a single story via ElevenLabs API.

    Returns the duration in seconds, or None on failure.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        log.error("ELEVENLABS_API_KEY not set")
        sys.exit(1)

    resp = requests.post(
        f"{ELEVENLABS_API_URL}/{voice}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=300,
    )

    if resp.status_code != 200:
        log.warning("ElevenLabs API error %d: %s", resp.status_code, resp.text[:200])
        return None

    output_path.write_bytes(resp.content)
    segment = AudioSegment.from_mp3(str(output_path))
    duration = len(segment) / 1000.0
    log.info("  Generated %.1fs audio", duration)
    return duration


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


def upload_to_r2(date_str: str, files: list[Path]) -> str:
    """Upload MP3s to Cloudflare R2. Returns the public base URL for this date."""
    for f in files:
        key = f"{date_str}/{f.name}"
        log.info("Uploading %s to R2...", key)
        subprocess.run(
            [
                "wrangler", "r2", "object", "put",
                f"{R2_BUCKET}/{key}",
                "--file", str(f),
                "--content-type", "audio/mpeg",
                "--remote",
            ],
            check=True,
        )
    return f"{R2_PUBLIC_URL}/{date_str}"


def strip_old_player(soup: BeautifulSoup) -> None:
    """Remove old Web Speech API player and any existing TTS players."""
    # Remove previous masthead player
    for audio in soup.find_all("audio", id="masthead-audio"):
        audio.parent.decompose()
        log.info("  Stripped existing masthead player")

    # Remove previous story pills and player JS
    for pill in soup.select(".listen-pill"):
        pill.decompose()
    for script in soup.find_all("script"):
        if script.string and "story-player" in script.string:
            script.decompose()
            log.info("  Stripped existing story-player script")

    for id_ in ("dispatch-player", "player-toggle"):
        el = soup.find(id=id_)
        if el:
            el.decompose()
            log.info("  Stripped #%s", id_)

    for script in soup.find_all("script"):
        if script.string and (
            "speechSynthesis" in script.string or "window.togglePlay" in script.string
        ):
            script.decompose()
            log.info("  Stripped speechSynthesis script")

    for style in soup.find_all("style"):
        if style.string and ".reading-active" in style.string:
            style.string = re.sub(
                r"\.reading-active\s*\{[^}]*\}", "", style.string
            )
            log.info("  Stripped .reading-active CSS")

    for style in soup.find_all("style"):
        if style.string:
            for sel in ("#dispatch-player", "#player-toggle", "#player-title", "#player-progress"):
                style.string = re.sub(
                    rf"{re.escape(sel)}[^{{]*\{{[^}}]*\}}", "", style.string
                )


def fmt_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def inject_masthead_player(
    soup: BeautifulSoup, full_edition_url: str, edition_date: str, duration: float
) -> None:
    """Inject 'The Daily Listen' masthead player between masthead and first section-label."""
    masthead = soup.select_one(".masthead")
    section_label = soup.select_one(".section-label")
    if not masthead or not section_label:
        log.warning("Could not find masthead or section-label for player injection")
        return

    player_html = f"""<div style="background:var(--sidebar);border:1px solid var(--light);padding:14px 18px;margin:12px 0 4px;display:flex;align-items:center;gap:16px;">
  <audio id="masthead-audio" preload="none" controls style="flex:1;height:36px;"><source src="{full_edition_url}" type="audio/mpeg"></audio>
  <div style="text-align:right;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;letter-spacing:.15em;color:var(--dark-red);font-weight:bold;">The Daily Listen</div>
    <div style="font-family:'Lora',serif;font-size:11px;color:var(--mid);margin-top:2px;">{edition_date} &middot; {fmt_duration(duration)}</div>
  </div>
</div>"""

    player_tag = BeautifulSoup(player_html, "lxml").body.contents[0]
    section_label.insert_before(player_tag)
    log.info("  Injected masthead player")


def inject_story_pills(
    soup: BeautifulSoup, audio_map: dict[str, dict], base_url: str
) -> None:
    """Inject LISTEN pill buttons into each story by matching headlines in the soup.

    audio_map: {headline_text: {"mp3_name": str, "duration": float}}
    Finds headlines directly in the soup so element references are always valid.
    """
    injected = 0

    # Find all headline elements in this soup
    for headline_el in soup.find_all(class_=["headline", "x-headline"]):
        # Strip permalink/share buttons to match extract_stories() normalization
        headline_copy = BeautifulSoup(str(headline_el), "lxml")
        for junk in headline_copy.select(".permalink"):
            junk.decompose()
        headline_text = clean_text(headline_copy.get_text())
        match = audio_map.get(headline_text)
        if not match:
            continue

        # Prefer placing in byline if it exists as a sibling
        byline = headline_el.find_next_sibling(class_="byline")
        anchor = byline if byline else headline_el

        url = f"{base_url}/{match['mp3_name']}"
        dur = fmt_duration(match["duration"])
        pill_html = (
            f'<span class="listen-pill" data-src="{url}" '
            f'style="display:inline-flex;align-items:center;gap:6px;'
            f"padding:3px 10px;border:1px solid var(--light);border-radius:3px;"
            f'margin-left:8px;cursor:pointer;font-family:\'IBM Plex Mono\',monospace;'
            f'font-size:9px;letter-spacing:.05em;color:var(--mid);transition:all .2s;">'
            f'<span style="color:var(--dark-red);font-size:10px;">&#9654;</span>'
            f" LISTEN &middot; {dur}</span>"
        )
        pill_tag = BeautifulSoup(pill_html, "lxml").body.contents[0]
        if byline:
            byline.append(pill_tag)
        else:
            headline_el.insert_after(pill_tag)
        injected += 1

    log.info("  Injected %d story pills", injected)


def inject_player_js(soup: BeautifulSoup) -> None:
    """Inject minimal JS for per-story pill playback before </body>."""
    js = """
(function() {
  var player = document.createElement('audio');
  player.id = 'story-player';
  player.preload = 'none';
  document.body.appendChild(player);

  var activePill = null;

  function deactivate() {
    if (activePill) {
      activePill.style.background = '';
      activePill.style.color = 'var(--mid)';
      activePill.style.borderColor = 'var(--light)';
      activePill = null;
    }
  }

  function activate(pill) {
    deactivate();
    activePill = pill;
    pill.style.background = 'var(--dark-red)';
    pill.style.color = '#fff';
    pill.style.borderColor = 'var(--dark-red)';
  }

  player.addEventListener('ended', deactivate);
  player.addEventListener('error', deactivate);

  document.querySelectorAll('.listen-pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      var src = this.getAttribute('data-src');
      if (activePill === this && !player.paused) {
        player.pause();
        deactivate();
        return;
      }
      while (player.firstChild) player.removeChild(player.firstChild);
      var source = document.createElement('source');
      source.src = src;
      source.type = 'audio/mpeg';
      player.appendChild(source);
      player.load();
      activate(this);
      player.play();
    });
  });
})();"""
    script_tag = soup.new_tag("script")
    script_tag.string = js
    soup.body.append(script_tag)
    log.info("  Injected player JavaScript")


def patch_html(
    html_path: Path,
    audio_map: dict[str, dict],
    base_url: str,
    edition_date: str,
    full_duration: float,
    is_page1: bool,
) -> None:
    """Patch a dispatch HTML file: strip old player, inject new players."""
    log.info("Patching %s...", html_path.name)
    soup = BeautifulSoup(html_path.read_text(), "lxml")

    strip_old_player(soup)

    if is_page1:
        full_url = f"{base_url}/full-edition.mp3"
        inject_masthead_player(soup, full_url, edition_date, full_duration)

    inject_story_pills(soup, audio_map, base_url)
    inject_player_js(soup)

    html_path.write_text(soup.decode(formatter="minimal"))
    log.info("  Wrote %s", html_path)


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

    date_str = args.date.isoformat()
    base_url = f"{R2_PUBLIC_URL}/{date_str}"

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"DRY RUN -- {len(all_stories)} stories found")
        print(f"R2 path: {R2_BUCKET}/{date_str}/")
        print(f"{'='*60}\n")
        for i, story in enumerate(all_stories, 1):
            words = len(story["text"].split())
            print(f"  story-{i:02d}.mp3  [{story['source']:>2}]  ~{words} words")
            print(f"    {story['headline'][:70]}...")
        print(f"\n  full-edition.mp3  (concatenation of all above)")
        print(f"\nEstimated audio: ~{sum(len(s['text'].split()) for s in all_stories) // 150} min")
        return

    # Verify external tools
    for tool in ["wrangler"]:
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            log.error("%s not found. Install it first.", tool)
            sys.exit(1)

    if args.patch_only:
        # In patch-only mode, download MP3s from R2 to get durations
        tmp_dir = Path(tempfile.mkdtemp(prefix="dispatch-audio-"))
        full_duration = 0.0
        for i, story in enumerate(all_stories, 1):
            mp3_name = f"story-{i:02d}.mp3"
            url = f"{base_url}/{mp3_name}"
            resp = requests.head(url, timeout=10)
            if resp.status_code == 200:
                story["mp3_name"] = mp3_name
                # Estimate duration from Content-Length (64kbps = 8000 bytes/sec)
                size = int(resp.headers.get("Content-Length", 0))
                story["duration"] = size / 8000.0
        # Get full edition duration
        resp = requests.head(f"{base_url}/full-edition.mp3", timeout=10)
        if resp.status_code == 200:
            full_duration = int(resp.headers.get("Content-Length", 0)) / 8000.0
        else:
            log.error("full-edition.mp3 not found on R2. Run without --patch-only first.")
            sys.exit(1)
    else:
        # Phase 2: Generate audio
        tmp_dir = Path(tempfile.mkdtemp(prefix="dispatch-audio-"))
        log.info("Working directory: %s", tmp_dir)

        story_mp3s = []
        for i, story in enumerate(all_stories, 1):
            mp3_name = f"story-{i:02d}.mp3"
            mp3_path = tmp_dir / mp3_name
            log.info("Generating %s: %s...", mp3_name, story["headline"][:50])
            duration = generate_story(story["text"], args.voice, mp3_path)
            if duration is not None:
                story_mp3s.append(mp3_path)
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

        # Phase 3: Upload to Cloudflare R2
        all_files = [full_path] + story_mp3s
        base_url = upload_to_r2(date_str, all_files)
        log.info("Uploaded to %s", base_url)

    # Phase 4: Patch HTML files
    page1_path = DISPATCH_DIR / "index.html"
    page2_path = DISPATCH_DIR / "page2.html"

    audio_map = {
        s["headline"]: {"mp3_name": s["mp3_name"], "duration": s["duration"]}
        for s in all_stories if "mp3_name" in s
    }

    title_tag = BeautifulSoup(page1_path.read_text(), "lxml").title
    edition_date = title_tag.string.split("\u2014")[-1].strip() if title_tag else date_str

    patch_html(page1_path, audio_map, base_url, edition_date, full_duration, is_page1=True)
    if page2_path.exists():
        patch_html(page2_path, audio_map, base_url, edition_date, full_duration, is_page1=False)

    # Cleanup temp files
    shutil.rmtree(tmp_dir, ignore_errors=True)

    log.info("Done! Audio: %s, HTML patched.", base_url)


if __name__ == "__main__":
    main()
