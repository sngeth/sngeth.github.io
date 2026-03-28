# Voxtral TTS for The Sid Dispatch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Web Speech API TTS player in The Sid Dispatch with pre-generated, high-quality audio using Mistral's Voxtral TTS via mlx-audio on Apple Silicon.

**Architecture:** A single PEP 723 Python script (`scripts/generate_dispatch_audio.py`) that parses dispatch HTML, extracts article text, generates per-story and full-edition MP3s via Voxtral, uploads them as GitHub Release assets, and patches the HTML with `<audio>`-based players.

**Tech Stack:** Python 3.12, mlx-audio (Voxtral-4B-TTS-2603), BeautifulSoup4/lxml, pydub, ffmpeg, gh CLI, uv

**Spec:** `docs/superpowers/specs/2026-03-28-voxtral-tts-dispatch-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/generate_dispatch_audio.py` | **Create** — Main script. PEP 723 inline deps. CLI entry point, text extraction, TTS generation, MP3 encoding, GitHub Release upload, HTML patching. |
| `dispatch/index.html` | **Modify** — Strip old Web Speech API player (if present), inject masthead player + per-story pills |
| `dispatch/page2.html` | **Modify** — Strip old Web Speech API player (if present), inject per-story pills |

No new test files — this is a CLI script with manual verification against the live dispatch. Testing is done via `--dry-run` and local HTML inspection.

---

## Task 1: Script Skeleton with CLI and Text Extraction

**Files:**
- Create: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Create script with PEP 723 header, CLI args, and text extraction**

```python
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
        # Find all elements that directly contain a .headline child
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
        print(f"DRY RUN — {len(all_stories)} stories found")
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
```

- [ ] **Step 2: Verify text extraction with dry-run**

Run:
```bash
cd /Users/sngeth/Code/sngeth.github.io && uv run scripts/generate_dispatch_audio.py --dry-run
```

Expected: Output showing ~4 HN stories + ~5 X items from page 1, ~6 HN stories + ~3 X items from page 2, with word counts and headline previews. No audio generated.

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "feat(dispatch): add TTS script skeleton with text extraction and --dry-run"
```

---

## Task 2: Audio Generation via Voxtral

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Add TTS generation function**

Add these imports at the top of the file, after the existing imports (below `from bs4 import BeautifulSoup`):

```python
import numpy as np
from mlx_audio.tts.utils import load_model
from mlx_audio.audio_io import write as audio_write
from pydub import AudioSegment


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
```

- [ ] **Step 2: Wire generation into main()**

Replace the `# Phases 2-4 will be added` comment block in `main()` with:

```python
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

    # Phase 3 & 4 will be added in subsequent tasks
    log.info("Upload and HTML patching not yet implemented.")
    log.info("Audio files in: %s", tmp_dir)
```

- [ ] **Step 3: Test audio generation on a single story**

Run (will take a few minutes on first model download):
```bash
cd /Users/sngeth/Code/sngeth.github.io && uv run scripts/generate_dispatch_audio.py --date 2026-03-21
```

Expected: Model downloads on first run. Per-story MP3s generated in temp dir. Full edition concatenated. Listen to a sample to verify quality.

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "feat(dispatch): add Voxtral TTS audio generation via mlx-audio"
```

---

## Task 3: GitHub Release Upload

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Add upload function**

Add after `generate_full_edition`:

```python
def upload_to_release(tag: str, title: str, files: list[Path]) -> str:
    """Upload MP3s as GitHub Release assets. Returns the release download base URL."""
    # Idempotency: delete existing release if present
    check = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO],
        capture_output=True,
    )
    if check.returncode == 0:
        log.info("Deleting existing release %s...", tag)
        subprocess.run(
            ["gh", "release", "delete", tag, "--yes", "--cleanup-tag", "--repo", REPO],
            check=True,
        )

    # Create release with all files
    cmd = [
        "gh", "release", "create", tag,
        "--repo", REPO,
        "--title", title,
        "--notes", f"Auto-generated TTS audio for {tag.replace('dispatch-audio-', '')}",
    ] + [str(f) for f in files]
    log.info("Creating release %s with %d files...", tag, len(files))
    subprocess.run(cmd, check=True)

    return f"https://github.com/{REPO}/releases/download/{tag}"
```

- [ ] **Step 2: Wire upload into main()**

Replace `# Phase 3 & 4 will be added` in `main()` with:

```python
    # Phase 3: Upload to GitHub Releases
    all_files = [full_path] + story_mp3s
    title = f"Dispatch Audio \u2014 {args.date.isoformat()}"
    base_url = upload_to_release(tag, title, all_files)
    log.info("Uploaded to %s", base_url)

    # Phase 4 will be added in next task
    log.info("HTML patching not yet implemented.")
```

- [ ] **Step 3: Test upload**

Run:
```bash
cd /Users/sngeth/Code/sngeth.github.io && uv run scripts/generate_dispatch_audio.py --date 2026-03-21
```

Expected: Release `dispatch-audio-2026-03-21` created on GitHub with MP3 assets. Verify at `https://github.com/sngeth/sngeth.github.io/releases`.

- [ ] **Step 4: Test idempotency — re-run same command**

Run same command again. Expected: "Deleting existing release..." then recreates cleanly.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "feat(dispatch): add GitHub Release upload for TTS audio"
```

---

## Task 4: HTML Patching — Strip Old Player

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Add function to strip Web Speech API player**

Add after `upload_to_release`:

```python
def strip_old_player(soup: BeautifulSoup) -> None:
    """Remove the Web Speech API player elements if present."""
    # Remove #dispatch-player and #player-toggle elements
    for id_ in ("dispatch-player", "player-toggle"):
        el = soup.find(id=id_)
        if el:
            el.decompose()
            log.info("  Stripped #%s", id_)

    # Remove script blocks containing speechSynthesis
    for script in soup.find_all("script"):
        if script.string and (
            "speechSynthesis" in script.string or "window.togglePlay" in script.string
        ):
            script.decompose()
            log.info("  Stripped speechSynthesis script")

    # Remove .reading-active CSS from <style> blocks
    for style in soup.find_all("style"):
        if style.string and ".reading-active" in style.string:
            style.string = re.sub(
                r"\.reading-active\s*\{[^}]*\}", "", style.string
            )
            log.info("  Stripped .reading-active CSS")

    # Remove #dispatch-player and #player-toggle CSS
    for style in soup.find_all("style"):
        if style.string:
            for sel in ("#dispatch-player", "#player-toggle", "#player-title", "#player-progress"):
                style.string = re.sub(
                    rf"{re.escape(sel)}[^{{]*\{{[^}}]*\}}", "", style.string
                )
```

- [ ] **Step 2: Verify stripping works on the live HTML**

We need to test against the live dispatch (which has the player). Fetch it and test:

```bash
curl -s https://sngeth.com/dispatch/ -o /tmp/dispatch-live.html
python3 -c "
from bs4 import BeautifulSoup
html = open('/tmp/dispatch-live.html').read()
assert 'speechSynthesis' in html, 'Live page should have speechSynthesis'
print('Live page has Web Speech API player - ready to test stripping')
"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "feat(dispatch): add function to strip Web Speech API player from HTML"
```

---

## Task 5: HTML Patching — Inject New Audio Players

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Add function to format duration**

Add after `strip_old_player`:

```python
def fmt_duration(seconds: float) -> str:
    """Format seconds as M:SS."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
```

- [ ] **Step 2: Add function to inject masthead player**

```python
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
  <audio id="masthead-audio" src="{full_edition_url}" preload="none" controls style="flex:1;height:36px;"></audio>
  <div style="text-align:right;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:9px;text-transform:uppercase;letter-spacing:.15em;color:var(--dark-red);font-weight:bold;">The Daily Listen</div>
    <div style="font-family:'Lora',serif;font-size:11px;color:var(--mid);margin-top:2px;">{edition_date} &middot; {fmt_duration(duration)}</div>
  </div>
</div>"""

    player_tag = BeautifulSoup(player_html, "lxml").body.contents[0]
    section_label.insert_before(player_tag)
    log.info("  Injected masthead player")
```

- [ ] **Step 3: Add function to inject per-story pill buttons**

```python
def inject_story_pills(
    soup: BeautifulSoup, stories: list[dict], base_url: str
) -> None:
    """Inject LISTEN pill buttons after each story's .byline element."""
    injected = 0
    for story in stories:
        if "mp3_name" not in story:
            continue  # Generation failed for this story
        byline = story["element"].find(class_="byline")
        if not byline:
            continue

        url = f"{base_url}/{story['mp3_name']}"
        dur = fmt_duration(story["duration"])
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
        byline.append(pill_tag)
        injected += 1

    log.info("  Injected %d story pills", injected)
```

- [ ] **Step 4: Add function to inject player JavaScript**

```python
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
      player.src = src;
      player.play();
      activate(this);
    });
  });
})();"""
    script_tag = soup.new_tag("script")
    script_tag.string = js
    soup.body.append(script_tag)
    log.info("  Injected player JavaScript")
```

- [ ] **Step 5: Add the patch_html orchestrator function**

```python
def patch_html(
    html_path: Path,
    stories: list[dict],
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

    inject_story_pills(soup, stories, base_url)
    inject_player_js(soup)

    html_path.write_text(soup.decode(formatter="minimal"))
    log.info("  Wrote %s", html_path)
```

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "feat(dispatch): add HTML patching — masthead player, story pills, and JS"
```

---

## Task 6: Wire Everything Together in main()

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Replace Phase 4 placeholder in main() with HTML patching**

Replace `# Phase 4 will be added in next task` with:

```python
    # Phase 4: Patch HTML files
    # Split stories back into per-page groups for patching
    page1_path = DISPATCH_DIR / "index.html"
    page2_path = DISPATCH_DIR / "page2.html"

    # Re-extract to get BeautifulSoup elements in the actual file DOMs
    # (the elements from extraction phase point to a different parse tree)
    page1_stories = extract_stories(page1_path)
    page2_stories = extract_stories(page2_path) if page2_path.exists() else []

    # Map generated audio info back to re-extracted stories by headline match
    audio_by_headline = {s["headline"]: s for s in all_stories if "mp3_name" in s}
    for stories in [page1_stories, page2_stories]:
        for s in stories:
            match = audio_by_headline.get(s["headline"])
            if match:
                s["mp3_name"] = match["mp3_name"]
                s["duration"] = match["duration"]

    # Extract edition date from page title
    title_tag = BeautifulSoup(page1_path.read_text(), "lxml").title
    edition_date = title_tag.string.split("\u2014")[-1].strip() if title_tag else args.date.isoformat()

    patch_html(page1_path, page1_stories, base_url, edition_date, full_duration, is_page1=True)
    if page2_path.exists() and page2_stories:
        patch_html(page2_path, page2_stories, base_url, edition_date, full_duration, is_page1=False)

    log.info("Done! Audio: %s, HTML patched.", base_url)
```

- [ ] **Step 2: Add the missing imports at the top of main or the module**

Verify these imports are present at the top of the file (they should already be there from Task 2):

```python
import numpy as np
from mlx_audio.tts.utils import load_model
from mlx_audio.audio_io import write as audio_write
from pydub import AudioSegment
```

Note: These should be inside a lazy import block or at module level. Since this is a CLI script run via `uv run`, top-level imports are fine — uv resolves the dependencies before execution.

- [ ] **Step 3: Full end-to-end test**

Run:
```bash
cd /Users/sngeth/Code/sngeth.github.io && uv run scripts/generate_dispatch_audio.py --date 2026-03-21
```

Expected:
1. Stories extracted from both pages
2. Per-story MP3s generated via Voxtral
3. Full edition MP3 concatenated
4. GitHub Release created with all MP3s
5. `dispatch/index.html` patched with masthead player + pills
6. `dispatch/page2.html` patched with pills
7. Open `dispatch/index.html` in browser — verify masthead player appears, pills appear after bylines, clicking a pill plays audio

- [ ] **Step 4: Verify HTML output**

```bash
# Check masthead player was injected
grep -c "masthead-audio" dispatch/index.html
# Expected: 1

# Check pills were injected
grep -c "listen-pill" dispatch/index.html
grep -c "listen-pill" dispatch/page2.html
# Expected: >0 for both

# Check old player was stripped (or was never present)
grep -c "speechSynthesis" dispatch/index.html
# Expected: 0
```

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_dispatch_audio.py dispatch/index.html dispatch/page2.html
git commit -m "feat(dispatch): complete Voxtral TTS pipeline — extract, generate, upload, patch"
```

---

## Task 7: Polish and Edge Cases

**Files:**
- Modify: `scripts/generate_dispatch_audio.py`

- [ ] **Step 1: Add cleanup of temp directory on success**

At the end of `main()`, after the success log line:

```python
    # Cleanup temp files
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    log.info("Cleaned up temp directory")
```

- [ ] **Step 2: Add error handling for missing gh CLI and ffmpeg**

At the start of `main()`, before any processing:

```python
    # Verify external tools
    for tool in ["gh", "ffmpeg"]:
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            log.error("%s not found. Install it first.", tool)
            sys.exit(1)
```

- [ ] **Step 3: Test dry-run still works**

```bash
cd /Users/sngeth/Code/sngeth.github.io && uv run scripts/generate_dispatch_audio.py --dry-run
```

Expected: Text extraction summary, no audio generation, no uploads, no HTML changes.

- [ ] **Step 4: Commit**

```bash
git add scripts/generate_dispatch_audio.py
git commit -m "chore(dispatch): add cleanup and tool verification to TTS script"
```

---

## Summary

| Task | What it does | Key files |
|------|-------------|-----------|
| 1 | Script skeleton + text extraction + `--dry-run` | `scripts/generate_dispatch_audio.py` |
| 2 | Voxtral TTS audio generation via mlx-audio | `scripts/generate_dispatch_audio.py` |
| 3 | GitHub Release upload with idempotency | `scripts/generate_dispatch_audio.py` |
| 4 | Strip old Web Speech API player from HTML | `scripts/generate_dispatch_audio.py` |
| 5 | Inject new `<audio>` players (masthead + pills + JS) | `scripts/generate_dispatch_audio.py` |
| 6 | Wire all phases together in main() | `scripts/generate_dispatch_audio.py`, `dispatch/*.html` |
| 7 | Polish: cleanup, tool checks, edge cases | `scripts/generate_dispatch_audio.py` |
