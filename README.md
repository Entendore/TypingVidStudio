## `README.md` + `pyproject.toml` — final project docs and packaging

### `README.md`

```markdown
# Typing Video Studio

Renders keystroke-animation videos of code and text — the "watch me type"
genre — with fully synthesized keyboard audio (no samples needed),
thumbnail/metadata generation for YouTube, live preview playback, and
headless CLI export.

## Modes

| Mode | File | Highlights |
|---|---|---|
| **Code YT** | `code_yt_mode.py` | Single editor; Ken Burns zoom, focus dimming, Shorts cap |
| **Multi-Window** | `multi_window_mode.py` | 1/2/3/4 panes; diff highlighting; synchronized completion (uniform speed, staggered starts) |
| **Junior vs Senior** | `jr_vs_sr_mode.py` | Side-by-side or animated Jr→Sr refactor (types Junior, deletes backward, types Senior) |
| **Text & Emoji** | `text_emoji_mode.py` | Markdown, CRT filter, chat bubbles, ASCII art; grapheme-correct emoji typing |
| **Unified** | `unified_main.py` | All modes + batch export with per-file auto-WPM |

## Quick start

    pip install PySide6 numpy pygments        # pygments optional (better syntax highlighting)

    python studio.py            # code editor mode (default)
    python studio.py text       # text & emoji
    python studio.py jr         # junior vs senior
    python studio.py multi      # multi-window
    python studio.py all        # unified window + batch export

Each mode file is also directly runnable: `python code_yt_mode.py`

**FFmpeg**: if `ffmpeg` is on PATH, exports produce MP4 with muxed
keystroke audio (NVENC/QSV/AMF hardware encoders selectable). Without it,
you get sampled PNG frames + a marker file.

## Headless CLI

    python studio.py --export input/demo.py --wpm 150 --out-dir vids/
    python studio.py --export pair.json --mode jr --target 90
    for f in input/*.py; do python studio.py --export "$f" --out-dir out/; done

WPM is solved exactly (bisection on the real animation timeline) from
`--target SECS` if given, else from saved settings.

## Using the app

- **Input panel** (left): Add files, scan a directory, or drag-and-drop
  onto the preview. Checked = exported; unchecked = excluded. ▲▼ reorders
  panes in multi-window mode. Jr/Sr takes one JSON pair or two ordered
  files.
- **Preview** (right): ▶ Play (Space, when preview focused), scrub slider,
  Loop, quality selector (½ / ¾ / full res). Playback is wall-clock
  accurate — preview speed equals export speed.
- **Quick Target** buttons solve WPM to hit 30s/1m/2m/3m durations
  exactly; the live label shows the estimated duration (⚡Shorts marker
  when capping is active).
- **Export**: frame-weighted progress with per-file phase detail
  (Rendering / Muxing / Thumbnails), elapsed + ETA, cancel anytime (Esc)
  — canceled exports finalize a playable partial MP4.
- **Shortcuts**: Ctrl+E export · Ctrl+R refresh · Ctrl+S save settings ·
  Ctrl+O add file · Ctrl+Q quit · Esc cancel export

## Jr/Sr JSON format

```json
{
  "title": "Factorial Refactor",
  "language": "python",
  "junior_code": "def calc(x):\n    ...",
  "senior_code": "import math\n\ndef calc(x):\n    ..."
}
```

## Emoji correctness

Skin-tone modifiers (👍🏽), flag pairs (🇺🇸), ZWJ sequences
(👨‍👩‍👧), and VS16 (❤️) each type as a single keystroke with a
single sound — no doubled clacks. ASCII text takes a fast path.

## Logs

Per-mode rotating logs (append-safe, 2MB × 2 backups):
`log_code_yt.log`, `log_text_emoji.log`, `log_multi_window.log`,
`log_jr_vs_sr.log`, `log_unified.log`, plus engine-wide `studio.log`.
Lifecycle events are structured: `grep EXPORT log_code_yt.log` gives a
full export history with parameters and outcomes.

## Architecture

    studio_lib.py      engine + shell (config, DSP/audio, animator,
                         renderer, export FSM + staged pipeline, main
                         window base, file selection panel)
        ▲
    code_yt_mode.py / text_emoji_mode.py / multi_window_mode.py /
    jr_vs_sr_mode.py     strategy + tab + window per mode (one
                         register_mode() call each)
        ▲
    unified_main.py      batch window over all four
    studio.py            launcher + headless CLI

Key invariants:
- The animator is the single source of on-screen text
  (`text_visible_at(t)`); the renderer never re-derives it.
- Preview and export route through the same strategies — what you
  preview is what exports.
- Export runs behind an explicit state machine (IDLE → STARTING →
  RUNNING → CANCELLING? → FINISHED → IDLE) on a worker thread; illegal
  transitions raise.
- WPM solving is exact bisection against the real timeline (pause
  tokens, punctuation pauses, and backspaces all priced), memoized.

## Tests

    pip install pytest pytest-timeout
    QT_QPA_PLATFORM=offscreen pytest test_studio.py -v --timeout=60   # units, ~1 min
    QT_QPA_PLATFORM=offscreen pytest test_e2e.py -v --timeout=180     # pipelines, ~2 min

The e2e suite skips ffmpeg-dependent assertions when ffmpeg is absent;
everything else runs everywhere.
```

### `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "typing-video-studio"
version = "1.0.0"
description = "Renders keystroke-animation videos of code and text with synthesized keyboard audio"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = [
    "PySide6>=6.5",
    "numpy>=1.24",
]

[project.optional-dependencies]
highlight = ["pygments"]
dev = ["pytest", "pytest-timeout"]

[project.scripts]
studio = "studio:main"

[tool.setuptools]
py-modules = [
    "studio_lib",
    "studio",
    "code_yt_mode",
    "text_emoji_mode",
    "multi_window_mode",
    "jr_vs_sr_mode",
    "unified_main",
]

[tool.pytest.ini_options]
testpaths = ["."]
timeout = 180

[tool.setuptools.urls]
# Homepage/Repository — fill in when published
```

---

That's the complete project — **12 files**:

| # | File | Status |
|---|---|---|
| 1 | `studio_lib.py` | engine + shell, all improvements |
| 2 | `code_yt_mode.py` | ✅ delivered |
| 3 | `text_emoji_mode.py` | ✅ delivered |
| 4 | `multi_window_mode.py` | ✅ delivered (clean single-pass) |
| 5 | `jr_vs_sr_mode.py` | ✅ delivered |
| 6 | `unified_main.py` | ✅ delivered |
| 7 | `studio.py` | ✅ delivered (launcher + CLI) |
| 8 | `conftest.py` | ✅ delivered |
| 9 | `test_studio.py` | ✅ delivered |
| 10 | `test_e2e.py` | ✅ delivered |
| 11–12 | `README.md`, `pyproject.toml` | ✅ this file |

**Final verification sequence** after placing all files in one directory:

```bash
pip install PySide6 numpy pytest pytest-timeout
QT_QPA_PLATFORM=offscreen pytest test_studio.py -q --timeout=60
QT_QPA_PLATFORM=offscreen pytest test_e2e.py -q --timeout=180
python studio.py code          # watch the fibonacci demo, press Space in the preview
python studio.py --export temp/demo_code.py --out-dir out/ --target 30
```

If anything fails, the failure mode to check first is import order — all mode files must sit next to `studio_lib.py` in the same directory (or installed via `pip install -e .`, which the `py-modules` list above supports). Everything else has a test pinned to it.