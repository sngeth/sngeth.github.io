# Voxtral TTS for The Sid Dispatch

**Date:** 2026-03-28
**Status:** Approved

## Problem

The Dispatch uses the Web Speech API (`window.speechSynthesis`) for text-to-speech. The dispatch bot injects a `#dispatch-player` fixed bar, a `#player-toggle` FAB, and a `speechSynthesis` IIFE into the generated HTML. This produces robotic, low-quality audio that varies by browser and OS. We want to replace it with pre-generated, high-quality audio using Mistral's Voxtral TTS model running locally on Apple Silicon via `mlx-audio`.

## Solution

A single Python script (`scripts/generate_dispatch_audio.py`) that:

1. Parses dispatch HTML to extract article text
2. Generates per-story and full-edition MP3s via Voxtral
3. Uploads MP3s as GitHub Release assets
4. Rewrites dispatch HTML: strips the Web Speech API player and injects `<audio>`-based players

## Architecture

```
[Dispatch HTML from bot (includes Web Speech API player)]
        |
        v
scripts/generate_dispatch_audio.py (uv run)
        |
        ├── 1. Parse HTML with BeautifulSoup
        ├── 2. Extract article text
        ├── 3. Generate per-story MP3s via mlx-audio + Voxtral
        ├── 4. Concatenate into full-edition MP3
        ├── 5. Upload MP3s as GitHub Release assets (gh CLI)
        └── 6. Patch HTML: strip old player, inject new <audio> players
```

### Script interface

```bash
uv run scripts/generate_dispatch_audio.py [--date YYYY-MM-DD] [--voice casual_male] [--dry-run]
```

- `--date`: Controls the GitHub Release tag name (`dispatch-audio-YYYY-MM-DD`). Defaults to today. The script always reads `dispatch/index.html` and `dispatch/page2.html` regardless of date.
- `--voice`: Selects from Voxtral's 20 presets (default: `casual_male`)
- `--dry-run`: Extracts text and prints story count, estimated word counts, and planned file names without running inference or uploading.

### Dependencies (PEP 723 script metadata)

- `mlx-audio` — Voxtral inference on Apple Silicon
- `beautifulsoup4` + `lxml` — HTML parsing
- `pydub` — MP3 encoding and concatenation (requires `ffmpeg` on host)

External tools required on host: `ffmpeg`, `gh` (GitHub CLI).

### Text extraction

Page 1 (`index.html`) uses `.lead`, `.sec`, `.tert` classes for HN stories. Page 2 (`page2.html`) does **not** use these classes — stories are in anonymous `<div>` elements with inline styles inside `.hn-col`.

The script uses a unified extraction strategy that works for both pages:

1. Find all elements within `.hn-col` that contain a `.headline` and `.body-text`
2. For each, extract: `.headline` text + `.deck` text (if present) + `.body-text` text
3. Find all `.x-item` elements and extract: `.x-handle` + `.x-headline` + `.x-body`

Skip: `.pull-quote` elements, `.tag` elements, navigation, footers, and page teasers. Page teasers are identified as elements outside `.hn-col` that link to `page2.html` (the "On Page 2 -- Extended Coverage" section at the bottom of `index.html`). The script only extracts from within `.hn-col` containers, which naturally excludes teasers.

Strip markdown-style formatting (`*...*`) from extracted text before passing to Voxtral.

Text for each story is composed as:
- HN stories: `"{headline}. {deck}. {body}"` (deck omitted if absent)
- X items: `"From X. {handle} says: {headline}. {body}"`

Numbering is continuous across pages: page 1 stories are `story-01` through `story-N`, page 2 continues from `story-{N+1}`.

### Audio generation

- Model: `mlx-community/Voxtral-4B-TTS-2603-mlx-bf16`
- Output: 24kHz WAV from Voxtral, encoded to MP3 at 64kbps mono via pydub/ffmpeg
- Per-story files: `story-01.mp3`, `story-02.mp3`, etc.
- Full edition: `full-edition.mp3` — concatenation of all story MP3s with 1.5s silence between each
- The script reads each MP3's duration via `pydub.AudioSegment` and stores it for HTML injection
- Estimated full edition size: ~8-10MB for a typical 15-20 min dispatch
- If Voxtral fails on a particular story (OOM, malformed input), log a warning and skip that story. The full edition omits failed stories. The HTML pill for that story is not injected.

### Audio hosting

MP3s are uploaded as GitHub Release assets:

- Tag: `dispatch-audio-YYYY-MM-DD`
- Release title: `Dispatch Audio — YYYY-MM-DD`
- Assets: `full-edition.mp3`, `story-01.mp3`, `story-02.mp3`, ...
- URLs: `https://github.com/sngeth/sngeth.github.io/releases/download/dispatch-audio-YYYY-MM-DD/{filename}`

**Idempotency:** Before creating, check with `gh release view dispatch-audio-YYYY-MM-DD`. If the release exists, delete it with `gh release delete dispatch-audio-YYYY-MM-DD --yes --cleanup-tag` and recreate. This allows safe re-runs during debugging.

GitHub Release asset URLs redirect through `objects.githubusercontent.com`, which serves proper CORS headers for GitHub Pages origins.

### HTML modifications

**Remove (injected by dispatch bot, may not exist in local repo copies):**

The script searches for and strips if present:
- `#dispatch-player` element and its CSS
- `#player-toggle` button
- Any `<script>` block containing `speechSynthesis` or `window.togglePlay`
- `.reading-active` CSS rules

If these elements are not found, the script proceeds without error (the local repo files may not have them, but the bot-generated versions will).

**Inject — Masthead player (between masthead and first `.section-label`):**

Sidebar-style box ("The Daily Listen") on `index.html` only:
- Background: `var(--sidebar)` (#F3EFE8), 1px border
- Play button: dark red circle, 42px
- Label: "THE DAILY LISTEN" (IBM Plex Mono, uppercase)
- Subtitle: edition date
- Native `<audio>` element with `controls` attribute, `preload="none"`
- `src` points to `full-edition.mp3` GitHub Release URL

**Inject — Per-story pill buttons (after each story's `.byline`):**

Compact pill: `[> LISTEN . M:SS]`
- 1px bordered pill with play icon + "LISTEN" + duration (from pydub measurement)
- `data-src` attribute with the story's GitHub Release MP3 URL
- On click: a shared hidden `<audio>` element (at page bottom) swaps its `src` and plays
- Active pill gets `var(--dark-red)` background + white text
- Only one story plays at a time; clicking another pill stops the current one
- Pills are independent from the masthead player (no sync — they serve different use cases)

### Player JavaScript

Minimal inline `<script>` injected before `</body>`:

```
- Shared <audio id="story-player"> element (hidden)
- querySelectorAll('.listen-pill') click handler:
  - Set story-player.src from pill's data-src
  - story-player.play()
  - Toggle .active class on pills
  - On ended: remove .active
```

No Web Speech API usage. The masthead `<audio>` uses native browser controls (no custom JS needed).

## Edge cases

- **No stories found:** Script exits with a warning, no release created, no HTML modified.
- **Page 2 missing:** Script processes page 1 only, logs a warning.
- **Re-run for same date:** Deletes existing release and recreates (see idempotency above).
- **Story generation failure:** Skip that story, omit from full edition, don't inject its pill.

## File changes

| File | Action |
|------|--------|
| `scripts/generate_dispatch_audio.py` | Create — main script (PEP 723 inline deps) |
| `dispatch/index.html` | Modify — strip old player, inject masthead + pills |
| `dispatch/page2.html` | Modify — strip old player, inject pills |

Audio files live in GitHub Releases, not in the repo.

## Out of scope

- Archive editions (`dispatch/archive/`) — future iteration
- RSS feed / podcast XML — future iteration
- Multiple voices or voice cloning — future iteration

## Constraints

- Voxtral CC BY-NC 4.0 license: non-commercial use only (site is personal, this is fine)
- Requires M-series Mac with sufficient unified memory (~10GB free) to run locally
- First run downloads ~8GB model weights (cached by mlx-audio after)
- `ffmpeg` and `gh` CLI must be installed on the host
