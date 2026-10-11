#!/usr/bin/env python3
"""
Unified Typing Video Studio — complete engine + shell (single file).

Layers (search ═══ markers):
  §1  Imports, logging (per-mode loggers), feature detection
  §2  Constants, enums, layouts, themes, mode registry
  §3  StudioConfig — dataclass + JSON persistence
  §4  Text utilities — graphemes, shortcodes, file reading, duration format,
      directory tree scanning
  §5  Audio — DSP (Karplus-Strong, bitcrush, reverb), modular synth, presets,
              typing sound gen, soundscapes, music-folder scan, ffmpeg decode,
              BGM track generator
  §6  Animation — TypingProfile, TypingAnimator (cursor + exact WPM solver)
  §7  Rendering — KeyboardOverlay, StudioRenderer, MultiPaneRenderer,
                  strategies, ExportManager (FSM + staged pipeline +
                  audio mux + BGM + extras)
  §8  UI SHELL — theme, preview state machine with wall-clock playback +
                  sync audio, StudioMainWindow, file selection panel
  §9  BaseModeTab — declarative wiring (+ combo_data) + estimates +
                     WPM spinbox factory + Quick Target + BGM + Typing Vol
"""
from __future__ import annotations

# ═════════════════════════════════════════════════════════════════════════════
# §1  IMPORTS, LOGGING, FEATURE DETECTION
# ═════════════════════════════════════════════════════════════════════════════
import bisect, copy, difflib, fnmatch, io, json, logging, math, os, random
import re, shutil, subprocess, sys, threading, time as _time, unicodedata, wave
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Callable

import numpy as np

from PySide6.QtCore import (Qt, QTimer, QThread, Signal, QBuffer, QIODevice,
                            QRect, QUrl, QByteArray, QObject, QElapsedTimer)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetrics, QImage,
                           QKeySequence, QLinearGradient, QPainter, QPalette,
                           QPen, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox,
                               QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSlider, QSpinBox,
                               QSplitter, QStatusBar, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    from pygments import lex
    from pygments.lexers import get_lexer_by_name
    _HAS_PYGMENTS = True
except ImportError:
    _HAS_PYGMENTS = False


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


HAS_FFMPEG = check_ffmpeg()

logger = logging.getLogger("TypingStudio")
logger.setLevel(logging.DEBUG)
_console = logging.StreamHandler(sys.stderr)
_console.setLevel(logging.ERROR)
_console.setFormatter(logging.Formatter("[!] %(levelname)s: %(message)s"))
logger.addHandler(_console)
try:
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler("studio.log", mode="a", maxBytes=2_000_000,
                              backupCount=2, encoding="utf-8")
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_fh)
except OSError:
    logger.warning("studio.log not writable; console logging only.")


# ── per-mode loggers ──────────────────────────────────────────────────────────
_logging_modes: Dict[str, logging.LoggerAdapter] = {}


def get_mode_logger(mode_name: str) -> logging.LoggerAdapter:
    key = (mode_name.lower().replace(" ", "_").replace("-", "_")
           .replace("&", "and"))
    if key in _logging_modes:
        return _logging_modes[key]
    base = logging.getLogger(f"TypingStudio.{key}")
    base.setLevel(logging.DEBUG)
    base.propagate = False
    try:
        fh = RotatingFileHandler(f"log_{key}.log", mode="a",
                                 maxBytes=2_000_000, backupCount=2,
                                 encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(mode)-12s %(levelname)-7s %(message)s",
            "%Y-%m-%d %H:%M:%S"))
        base.addHandler(fh)
    except OSError:
        base.addHandler(logging.NullHandler())
    adapter = logging.LoggerAdapter(base, {"mode": key})
    _logging_modes[key] = adapter
    return adapter


def log_mode_event(mode_logger, event: str, **details):
    parts = [f"{k}={v}" for k, v in details.items()]
    mode_logger.info(f"{event.upper()}{' ' + ' '.join(parts) if parts else ''}")


# Shared constants
OVERHEAD_MIN, OVERHEAD_MAX = 0.5, 1.5
SHORTS_TARGET_SECS = 179.0
MAX_INPUT_CHARS = 200_000

# ═════════════════════════════════════════════════════════════════════════════
# §2  CONSTANTS, ENUMS, LAYOUTS, THEMES, STATE MACHINES, MODE REGISTRY
# ═════════════════════════════════════════════════════════════════════════════
CWD = Path.cwd()
SETTINGS_FILE = CWD / "settings.json"
TEMP_DIR = CWD / "temp"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

MUSIC_DIR = CWD / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_FILE_EXTS = frozenset({
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus",
    ".wma", ".aiff", ".aif", ".au", ".snd",
})

SOUNDSCAPE_TYPES = ["Rain", "Wind", "Ocean", "Drone", "Forest"]
SOUNDSCAPE_ICONS = {"Rain": "🌧", "Wind": "💨", "Ocean": "🌊",
                    "Drone": "🎭", "Forest": "🌲"}

SCAN_SKIP_DIRS = frozenset({"__pycache__", ".git", ".hg", ".svn",
                            "node_modules", ".venv", "venv", ".idea",
                            ".vscode", "dist", "build"})


class StudioMode(Enum):
    MULTI_WINDOW = "Multi-Window Code Comparison"
    JR_VS_SR = "Junior vs Senior Dev"
    CODE_YT = "Single Window Code (YouTube Optimised)"
    TEXT_EMOJI = "Text & Emoji (Single Window)"


MODE_REGISTRY: Dict[str, dict] = {}


def register_mode(key: str, strategy_cls, tab_cls, window_cls):
    MODE_REGISTRY[key] = {"strategy": strategy_cls, "tab": tab_cls,
                          "window": window_cls}


# ── state machines ───────────────────────────────────────────────────────────
class InvalidStateTransition(RuntimeError):
    pass


class StateMachine:
    def __init__(self, name: str, initial, transitions: Dict[Enum, set]):
        self.name = name
        self.state = initial
        self.transitions = transitions
        self._subscribers: List[Callable] = []

    def subscribe(self, fn: Callable) -> "StateMachine":
        self._subscribers.append(fn)
        return self

    def can(self, new) -> bool:
        return new in self.transitions.get(self.state, set())

    def transition(self, new):
        if not self.can(new):
            raise InvalidStateTransition(
                f"{self.name}: illegal {self.state.name} → {new.name}")
        old = self.state
        self.state = new
        logger.debug("%s: %s -> %s", self.name, old.name, new.name)
        for fn in self._subscribers:
            try:
                fn(old, new)
            except Exception:
                logger.exception("FSM subscriber error in %s", self.name)
        return old

    def require(self, *states):
        if self.state not in states:
            raise InvalidStateTransition(
                f"{self.name}: requires "
                f"{'/'.join(s.name for s in states)}, is {self.state.name}")


class ExportState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FINISHED = "finished"

    @property
    def busy(self) -> bool:
        return self in (ExportState.STARTING, ExportState.RUNNING,
                        ExportState.CANCELLING)


_EXPORT_FSM = {
    ExportState.IDLE:       {ExportState.STARTING},
    ExportState.STARTING:   {ExportState.RUNNING, ExportState.CANCELLING,
                             ExportState.FINISHED, ExportState.IDLE},
    ExportState.RUNNING:    {ExportState.CANCELLING, ExportState.FINISHED},
    ExportState.CANCELLING: {ExportState.FINISHED},
    ExportState.FINISHED:   {ExportState.IDLE},
}


class PreviewState(Enum):
    EMPTY = "empty"
    READY = "ready"
    PLAYING = "playing"
    ERROR = "error"


_PREVIEW_FSM = {
    PreviewState.EMPTY:   {PreviewState.READY, PreviewState.ERROR},
    PreviewState.READY:   {PreviewState.PLAYING, PreviewState.EMPTY,
                           PreviewState.ERROR},
    PreviewState.PLAYING: {PreviewState.READY, PreviewState.EMPTY,
                           PreviewState.ERROR},
    PreviewState.ERROR:   {PreviewState.EMPTY},
}


class ExportCancelled(RuntimeError):
    pass


SUPPORTED_EXTENSIONS = frozenset({
    ".py", ".pyw", ".pyi", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
    ".java", ".kt", ".kts", ".scala", ".groovy", ".gradle",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx",
    ".cs", ".vb", ".go", ".rs", ".rb", ".rbw", ".php", ".swift", ".m", ".mm",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".psm1", ".bat", ".cmd",
    ".sql", ".html", ".htm", ".xhtml", ".css", ".scss", ".sass", ".less",
    ".json", ".json5", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".md", ".markdown", ".txt", ".csv", ".tsv", ".asc", ".ascii",
    ".art", ".nfo", ".diz", ".emoji", ".emo",
    ".lua", ".dart", ".r", ".R", ".pl", ".pm", ".hs", ".lhs",
    ".clj", ".cljs", ".cljc", ".ex", ".exs", ".erl", ".fs", ".fsi", ".fsx",
    ".ml", ".mli", ".nim", ".v", ".sv", ".vhdl", ".asm", ".s",
    ".tex", ".zig", ".vue", ".svelte",
})

EXT_TO_LANGUAGE = {
    ".py": "python", ".pyw": "python", ".pyi": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".scala": "scala",
    ".groovy": "groovy", ".gradle": "groovy",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp",
    ".hxx": "cpp",
    ".cs": "csharp", ".vb": "vbnet",
    ".go": "go", ".rs": "rust", ".rb": "ruby", ".rbw": "ruby", ".php": "php",
    ".swift": "swift", ".m": "objective-c", ".mm": "objective-c++",
    ".sh": "bash", ".bash": "bash", ".zsh": "bash", ".fish": "fish",
    ".ps1": "powershell", ".psm1": "powershell", ".bat": "batch",
    ".cmd": "batch", ".sql": "sql",
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass", ".less": "less",
    ".json": "json", ".json5": "json",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".ini": "ini", ".cfg": "ini", ".conf": "ini", ".xml": "xml",
    ".md": "markdown", ".markdown": "markdown",
    ".txt": "text", ".csv": "text", ".tsv": "text",
    ".asc": "text", ".ascii": "text", ".art": "text", ".nfo": "text",
    ".diz": "text", ".emoji": "text", ".emo": "text",
    ".lua": "lua", ".dart": "dart", ".r": "r", ".R": "r",
    ".pl": "perl", ".pm": "perl", ".hs": "haskell", ".lhs": "haskell",
    ".clj": "clojure", ".cljs": "clojure", ".cljc": "clojure",
    ".ex": "elixir", ".exs": "elixir", ".erl": "erlang",
    ".fs": "fsharp", ".fsi": "fsharp", ".fsx": "fsharp",
    ".ml": "ocaml", ".mli": "ocaml", ".nim": "nim",
    ".v": "verilog", ".sv": "systemverilog", ".vhdl": "vhdl",
    ".asm": "asm", ".s": "asm", ".tex": "latex", ".zig": "zig",
    ".vue": "vue", ".svelte": "svelte",
    "dockerfile": "docker", ".dockerfile": "docker",
    "makefile": "makefile", ".makefile": "makefile",
    ".gitignore": "gitignore", ".gitconfig": "ini",
}


def detect_language(path: str) -> str:
    p = Path(path)
    return (EXT_TO_LANGUAGE.get(p.name.lower())
            or EXT_TO_LANGUAGE.get(p.suffix.lower(), "text"))


MULTI_WINDOW_LAYOUTS = {"1 Window (Single)": 1, "2 Windows (Split)": 2,
                        "4 Windows (Grid)": 4, "Git Conflict (3-Pane)": 3}
JR_VS_SR_LAYOUTS = ["Side by Side (50/50)", "Stacked (50/50)",
                    "Junior Big (70/30)", "Senior Big (70/30)"]
RESOLUTIONS = {"1920x1080": (1920, 1080), "1280x720": (1280, 720),
               "3840x2160": (3840, 2160),
               "1080x1920 (9:16)": (1080, 1920),
               "720x1280 (9:16)": (720, 1280)}
ENCODERS = ["YouTube Optimised (H.264/AAC)", "NVENC (NVIDIA)",
            "QSV (Intel)", "AMF (AMD)"]
ENCODER_ARGS = {
    "YouTube Optimised (H.264/AAC)": ["-c:v", "libx264", "-preset", "fast",
                                      "-crf", "18", "-pix_fmt", "yuv420p"],
    "NVENC (NVIDIA)": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr",
                       "-cq", "19", "-pix_fmt", "yuv420p"],
    "QSV (Intel)": ["-c:v", "h264_qsv", "-global_quality", "20",
                    "-pix_fmt", "yuv420p"],
    "AMF (AMD)": ["-c:v", "h264_amf", "-quality", "balanced",
                  "-pix_fmt", "yuv420p"],
}

THEMES = {
    "Dracula": {"background": "#282a36", "foreground": "#f8f8f2",
                "comment": "#6272a4", "keyword": "#ff79c6",
                "string": "#f1fa8c", "number": "#bd93f9",
                "function": "#50fa7b", "builtin": "#8be9fd",
                "decorator": "#50fa7b", "operator": "#ff79c6",
                "class_name": "#8be9fd", "line_number": "#6272a4",
                "current_line": "#44475a", "cursor": "#f8f8f2",
                "title_bar": "#21222c", "title_text": "#8be9fd",
                "window_border": "#191a21", "junior_accent": "#8be9fd",
                "senior_accent": "#50fa7b"},
    "One Dark": {"background": "#282c34", "foreground": "#abb2bf",
                 "comment": "#5c6370", "keyword": "#c678dd",
                 "string": "#98c379", "number": "#d19a66",
                 "function": "#61afef", "builtin": "#e5c07b",
                 "decorator": "#56b6c2", "operator": "#c678dd",
                 "class_name": "#e5c07b", "line_number": "#4b5263",
                 "current_line": "#2c313c", "cursor": "#528bff",
                 "title_bar": "#21252b", "title_text": "#61afef",
                 "window_border": "#181a1f", "junior_accent": "#61afef",
                 "senior_accent": "#98c379"},
    "Catppuccin Mocha": {"background": "#1e1e2e", "foreground": "#cdd6f4",
                         "comment": "#6c7086", "keyword": "#cba6f7",
                         "string": "#a6e3a1", "number": "#fab387",
                         "function": "#89b4fa", "builtin": "#94e2d5",
                         "decorator": "#f5c2e7", "operator": "#94e2d5",
                         "class_name": "#f9e2af", "line_number": "#6c7086",
                         "current_line": "#313244", "cursor": "#f5e0dc",
                         "title_bar": "#181825", "title_text": "#89b4fa",
                         "window_border": "#11111b",
                         "junior_accent": "#f38ba8",
                         "senior_accent": "#a6e3a1"},
    "GitHub Dark": {"background": "#0d1117", "foreground": "#c9d1d9",
                    "comment": "#8b949e", "keyword": "#ff7b72",
                    "string": "#a5d6ff", "number": "#79c0ff",
                    "function": "#d2a8ff", "builtin": "#79c0ff",
                    "decorator": "#d2a8ff", "operator": "#ff7b72",
                    "class_name": "#ffa657", "line_number": "#6e7681",
                    "current_line": "#161b22", "cursor": "#58a6ff",
                    "title_bar": "#010409", "title_text": "#58a6ff",
                    "window_border": "#30363d",
                    "junior_accent": "#ff7b72", "senior_accent": "#3fb950"},
    "Solarized Dark": {"background": "#002b36", "foreground": "#93a1a1",
                       "comment": "#586e75", "keyword": "#859900",
                       "string": "#2aa198", "number": "#d33682",
                       "function": "#268bd2", "builtin": "#b58900",
                       "decorator": "#cb4b16", "operator": "#859900",
                       "class_name": "#b58900", "line_number": "#586e75",
                       "current_line": "#073642", "cursor": "#eee8d5",
                       "title_bar": "#001c23", "title_text": "#268bd2",
                       "window_border": "#000000",
                       "junior_accent": "#268bd2",
                       "senior_accent": "#859900"},
}

EMOJI_SHORTCODES = {":rocket:": "🚀", ":fire:": "🔥", ":sparkles:": "✨",
                    ":heart:": "❤️", ":check:": "✅"}


def _get_system_fonts():
    try:
        db = QFontDatabase
        preferred = ["Consolas", "JetBrains Mono", "Fira Code",
                     "Cascadia Code", "IBM Plex Mono", "DejaVu Sans Mono",
                     "Courier New", "monospace"]
        families = [f for f in db.families()
                    if f not in preferred and not f.startswith("@")]
        return preferred + families
    except Exception:
        return ["Consolas", "JetBrains Mono", "Fira Code", "monospace"]


_FONT_FAMILIES: Optional[List[str]] = None


def get_font_families() -> List[str]:
    global _FONT_FAMILIES
    if _FONT_FAMILIES is None:
        _FONT_FAMILIES = _get_system_fonts()
    return _FONT_FAMILIES


# ═════════════════════════════════════════════════════════════════════════════
# §3  STUDIO CONFIG
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class StudioConfig:
    mode: StudioMode = StudioMode.CODE_YT
    theme: str = "Dracula"
    resolution: str = "1920x1080"
    fps: int = 30
    sound_enabled: bool = True
    sound_preset: str = "Mechanical"
    stereo: bool = False
    volume: int = 50
    encoder: str = "YouTube Optimised (H.264/AAC)"
    use_custom: bool = False
    custom_code: str = ""
    show_cursor: bool = True
    kb_enabled: bool = False
    kb_layout: str = "QWERTY"
    kb_position: str = "Bottom Center"
    kb_opacity: float = 0.82
    layout_mw: str = "2 Windows (Split)"
    wpm_mw: int = 100
    shorts_mw: bool = False
    diff_highlight_mw: bool = True
    sync_mw: bool = True
    mw_ratio: int = 50
    font_mw: str = "Consolas"; font_sz_auto_mw: bool = False; font_sz_mw: int = 22
    font_mw_2: str = "Consolas"; font_sz_auto_mw_2: bool = False; font_sz_mw_2: int = 22
    font_mw_3: str = "Consolas"; font_sz_auto_mw_3: bool = False; font_sz_mw_3: int = 22
    font_mw_4: str = "Consolas"; font_sz_auto_mw_4: bool = False; font_sz_mw_4: int = 22
    layout_jr: str = "Side by Side (50/50)"
    jr_wpm: int = 90; sr_wpm: int = 130
    jr_custom_code: str = ""; sr_custom_code: str = ""
    jr_sound: str = "Mechanical"; sr_sound: str = "ASMR Deep Thock"
    font_jr: str = "Consolas"; font_sz_auto_jr: bool = False; font_sz_jr: int = 22
    font_sr: str = "Consolas"; font_sz_auto_sr: bool = False; font_sz_sr: int = 22
    jr_diff_mode: bool = False
    wpm_yt: int = 100; shorts_yt: bool = False
    yt_zoom: bool = False; yt_focus: bool = False
    font_yt: str = "Consolas"; font_sz_auto_yt: bool = False; font_sz_yt: int = 22
    wpm_txt: int = 100; shorts_txt: bool = False
    ascii_art: bool = False; txt_markdown: bool = False; txt_crt: bool = False
    txt_bubbles: bool = False; txt_clean: bool = True
    font_txt: str = "Consolas"; font_sz_auto_txt: bool = False; font_sz_txt: int = 22
    bgm_enabled: bool = False
    bgm_source: str = "Rain"
    bgm_volume: int = 30
    yt_extras: bool = True; gen_metadata: bool = True
    recursive_scan: bool = True; scan_depth: int = 10
    output_template: str = "{name}_{date}"
    input_dir: str = str(CWD / "input")
    output_dir: str = str(CWD / "output")
    batch_auto_wpm: bool = False
    target_duration: int = 60
    win_geometry: str = ""
    win_state: str = ""
    recent_files: List[str] = field(default_factory=list)
    preview_size: Optional[Tuple[int, int]] = None
    _show_time_badge: bool = False

    _PREVIEW_ONLY = {"preview_size", "_show_time_badge"}

    def save(self, path=SETTINGS_FILE):
        data = asdict(self)
        data["mode"] = self.mode.name
        for k in self._PREVIEW_ONLY:
            data.pop(k, None)
        try:
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning(f"Could not save settings: {e}")

    @classmethod
    def load(cls, path=SETTINGS_FILE) -> "StudioConfig":
        cfg = cls()
        p = Path(path)
        if not p.exists():
            return cfg
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read settings, using defaults: {e}")
            return cfg
        valid = {f.name for f in fields(cls)}
        for k, v in data.items():
            if k not in valid or k in cls._PREVIEW_ONLY:
                continue
            if k == "mode":
                try:
                    cfg.mode = StudioMode[v]
                except KeyError:
                    pass
                continue
            default = getattr(cfg, k)
            try:
                if isinstance(default, bool):
                    setattr(cfg, k, bool(v))
                elif isinstance(default, int):
                    setattr(cfg, k, int(v))
                elif isinstance(default, float):
                    setattr(cfg, k, float(v))
                elif isinstance(default, list):
                    setattr(cfg, k, list(v) if isinstance(v, list) else default)
                else:
                    setattr(cfg, k, v)
            except (TypeError, ValueError):
                pass
        return cfg


# ═════════════════════════════════════════════════════════════════════════════
# §4  TEXT UTILITIES
# ═════════════════════════════════════════════════════════════════════════════
ZWJ = '\u200d'
VS16 = '\ufe0f'


def split_graphemes(text: str) -> List[str]:
    if text.isascii():
        return list(text)
    graphemes, i, n = [], 0, len(text)
    while i < n:
        c, i = text[i], i + 1
        while i < n:
            nxt = text[i]
            if (nxt == ZWJ or nxt == VS16
                    or unicodedata.combining(nxt) != 0
                    or 0x1F3FB <= ord(nxt) <= 0x1F3FF):
                c += nxt
                i += 1
                if c[-1] == ZWJ and i < n:
                    c += text[i]
                    i += 1
            elif (0x1F1E6 <= ord(nxt) <= 0x1F1FF
                    and c and 0x1F1E6 <= ord(c[-1]) <= 0x1F1FF):
                c += nxt
                i += 1
            else:
                break
        graphemes.append(c)
    return graphemes


def is_emoji(char: str) -> bool:
    if not char:
        return False
    cat = unicodedata.category(char[0])
    return (cat.startswith(('So', 'Sk', 'Sm'))
            or ZWJ in char or VS16 in char)


def convert_shortcodes(text: str) -> str:
    for code, emoji in EMOJI_SHORTCODES.items():
        text = text.replace(code, emoji)
    return text


ASCII_ART_EXTS = (".asc", ".ascii", ".art", ".nfo", ".diz", ".emoji", ".emo")


def read_text_file(path: str, clean: bool = True) -> str:
    ext = Path(path).suffix.lower()
    enc = "cp437" if ext in (".nfo", ".diz") else "utf-8"
    try:
        with open(path, "r", encoding=enc) as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    text = convert_shortcodes(text)
    if clean and ext not in ASCII_ART_EXTS:
        text = text.replace("\xa0", " ").replace("\xad", "")
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = "\n".join(line.rstrip() for line in text.splitlines())
    return text


def format_duration(secs: float) -> str:
    s = int(round(secs))
    if s >= 3600:
        h, rest = divmod(s, 3600)
        m, sec = divmod(rest, 60)
        return f"{h}h {m:02d}m {sec:02d}s"
    if s >= 60:
        m, sec = divmod(s, 60)
        return f"{m}m {sec:02d}s"
    return f"{s}s"


def _text_key(text: str) -> tuple:
    return (len(text), hash(text))


# ── directory tree scanning ───────────────────────────────────────────────────

def scan_directory_tree(
    root: Path,
    *,
    extensions: Optional[frozenset] = None,
    skip_dirs: Optional[frozenset] = None,
    recursive: bool = True,
    max_depth: int = 10,
    max_files: int = 0,
    follow_symlinks: bool = False,
) -> List[Path]:
    """Efficiently scan a directory tree using os.scandir()."""
    if skip_dirs is None:
        skip_dirs = SCAN_SKIP_DIRS

    root = Path(root)
    if not root.is_dir():
        return []

    results: List[Path] = []

    def _scan(dir_path: str, depth: int):
        """Inner recursive scanner using os.scandir."""
        if max_files and len(results) >= max_files:
            return
        if recursive and depth > max_depth:
            return
        try:
            entries = os.scandir(dir_path)
        except (PermissionError, OSError):
            return
        try:
            files, dirs = [], []
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=follow_symlinks):
                        if entry.name.lower() in skip_dirs:
                            continue
                        if not follow_symlinks and entry.is_symlink():
                            continue
                        dirs.append(entry)
                    elif entry.is_file(follow_symlinks=follow_symlinks):
                        files.append(entry)
                except OSError:
                    continue

            for entry in sorted(files, key=lambda e: e.name.lower()):
                if max_files and len(results) >= max_files:
                    return
                ext = os.path.splitext(entry.name)[1].lower()
                if extensions is None or ext in extensions:
                    results.append(Path(entry.path))

            if recursive and depth < max_depth:
                for entry in sorted(dirs, key=lambda e: e.name.lower()):
                    if max_files and len(results) >= max_files:
                        return
                    _scan(entry.path, depth + 1)
        finally:
            entries.close()

    _scan(str(root), 0)
    return results


# ═════════════════════════════════════════════════════════════════════════════
# §5  AUDIO
# ═════════════════════════════════════════════════════════════════════════════
AUDIO_SAMPLE_RATE = 48000


class DSP:
    @staticmethod
    def env_exp(n, sr, attack=0.001, decay_rate=30.0, attack_curve=2.0):
        t = np.arange(n, dtype=np.float64) / sr
        env = np.exp(-t * decay_rate)
        a_samp = max(1, int(attack * sr))
        if a_samp < n:
            a_env = np.linspace(0, 1, a_samp) ** attack_curve
            env[:a_samp] = a_env * np.exp(
                -np.arange(a_samp, dtype=np.float64) / sr * decay_rate)
        return env

    @staticmethod
    def fir_lowpass(cutoff, sr=AUDIO_SAMPLE_RATE, n_taps=127):
        if n_taps % 2 == 0:
            n_taps += 1
        fc = min(max(1.0, cutoff), sr / 2.0 - 1.0) / sr
        n = np.arange(n_taps, dtype=np.float64)
        center = (n_taps - 1) / 2.0
        h = np.sinc(2 * fc * (n - center))
        w = (0.42 - 0.5 * np.cos(2 * np.pi * n / (n_taps - 1))
             + 0.08 * np.cos(4 * np.pi * n / (n_taps - 1)))
        h *= w
        s = np.sum(h)
        if s > 0:
            h /= s
        return h

    @staticmethod
    def convolve(x, h):
        n, nh = len(x), len(h)
        if nh <= 1:
            return x * h[0] if nh == 1 else x
        n_fft = 1 << ((n + nh - 1).bit_length())
        return np.fft.irfft(
            np.fft.rfft(x, n_fft) * np.fft.rfft(h, n_fft), n_fft)[:n]

    @staticmethod
    def filt_lp(x, c, sr=AUDIO_SAMPLE_RATE, n_taps=127):
        return DSP.convolve(x, DSP.fir_lowpass(c, sr, n_taps))

    @staticmethod
    def filt_hp(x, c, sr=AUDIO_SAMPLE_RATE, n_taps=63):
        hlp = DSP.fir_lowpass(c, sr, n_taps)
        h = -hlp
        h[len(h) // 2] += 1.0
        return DSP.convolve(x, h)

    @staticmethod
    def filt_bp(x, l, h, sr=AUDIO_SAMPLE_RATE):
        return DSP.filt_lp(x, h, sr) - DSP.filt_lp(x, l, sr)

    @staticmethod
    def osc_sine(f, n, sr):
        return np.sin(2 * np.pi * f * (np.arange(n, dtype=np.float64) / sr))

    @staticmethod
    def osc_fm(c, mr, mi, n, sr):
        t = np.arange(n, dtype=np.float64) / sr
        return np.sin(2 * np.pi * c * t + mi * np.sin(2 * np.pi * c * mr * t))

    @staticmethod
    def osc_pluck(freq, n, sr, decay=0.996):
        """Karplus-Strong pluck synthesis."""
        delay = max(1, int(sr / max(1.0, freq)))
        buf = np.random.uniform(-1, 1, delay).astype(np.float64)
        y = np.zeros(n, dtype=np.float64)
        for i in range(n):
            buf_idx = i % delay
            y[i] = buf[buf_idx]
            next_idx = (i + 1) % delay
            buf[buf_idx] = (buf[buf_idx] + buf[next_idx]) * 0.5 * decay
        return y

    @staticmethod
    def noise_white(n, rng):
        return rng.randn(n).astype(np.float64)

    @staticmethod
    def noise_pink(n, rng):
        white = rng.randn(n).astype(np.float64)
        fft = np.fft.rfft(white)
        freqs = np.fft.rfftfreq(n, 1.0 / AUDIO_SAMPLE_RATE)
        freqs[0] = max(freqs[1] if len(freqs) > 1 else 1.0, 1.0)
        fft[1:] /= np.sqrt(np.abs(freqs[1:]))
        fft[0] = 0
        return np.fft.irfft(fft, n=n)

    @staticmethod
    def modal(modes, n, sr, inharmonicity=0.0):
        t = np.arange(n, dtype=np.float64) / sr
        out = np.zeros(n, dtype=np.float64)
        f0 = modes[0][0] if modes else 440.0
        for freq, decay, amp in modes:
            af = freq
            if inharmonicity > 0:
                nh = freq / f0
                af = freq * np.sqrt(1 + inharmonicity * nh * nh)
            out += np.sin(2 * np.pi * af * t) * np.exp(-decay * t) * amp
        return out

    @staticmethod
    def bitcrush(x, bits=8):
        if bits <= 0 or bits >= 16:
            return x
        levels = 2 ** bits
        return np.round(x * levels) / levels

    @staticmethod
    def add_reverb(x, sr, mix=0.2):
        """Vectorized multi-tap delay reverb."""
        if mix <= 0 or len(x) < sr // 2:
            return x
            
        delays = [0.0297, 0.0371, 0.0411, 0.0437, 0.05, 0.06]
        gains = [0.65, 0.55, 0.45, 0.35, 0.25, 0.15]
        
        wet = np.zeros_like(x)
        for d, g in zip(delays, gains):
            delay_samples = int(d * sr)
            if delay_samples > 0 and delay_samples < len(x):
                wet[delay_samples:] += x[:-delay_samples] * g
                
        wet = DSP.filt_lp(wet, 3000.0, sr)
        return x * (1.0 - mix) + wet * mix

    @staticmethod
    def sat_tanh(x, drive=1.0):
        if drive <= 0:
            return x
        return np.tanh(x * drive) / max(0.001, np.tanh(drive))

    @staticmethod
    def to_int16(x, target_db=-1.0):
        pk = np.max(np.abs(x)) if len(x) > 0 else 0.0
        if pk < 1e-10:
            return np.zeros_like(x, dtype=np.int16)
        return np.clip(x * (10 ** (target_db / 20) / pk) * 32767,
                       -32768, 32767).astype(np.int16)


@dataclass
class VoiceSpec:
    osc: str = "sine"
    freq: float = 440.0
    fm_ratio: float = 1.0
    fm_index: float = 0.0
    attack: float = 0.001
    decay_rate: float = 30.0
    attack_curve: float = 2.0
    filt: str = "none"
    f_cutoff: float = 8000.0
    f_high: float = 12000.0
    f_q: float = 1.0
    drive: float = 0.0
    gain: float = 0.5
    delay: float = 0.0
    modes: Optional[List[Tuple[float, float, float]]] = None
    inharmonicity: float = 0.0
    reverb: float = 0.0
    bitcrush: int = 0


@dataclass
class SoundSpec:
    duration: float = 0.12
    layers: List[VoiceSpec] = field(default_factory=list)


MODULAR_SOUND_PRESETS = {
    "Mechanical": SoundSpec(duration=0.15, layers=[
        VoiceSpec(osc="noise_white", attack=0.0001, decay_rate=500.0,
                  filt="bp", f_cutoff=2500, f_high=6000, drive=1.5,
                  gain=0.4),
        VoiceSpec(osc="sine", freq=180, attack=0.001, decay_rate=60.0,
                  filt="lp", f_cutoff=600, gain=0.6),
        VoiceSpec(osc="sine", freq=90, attack=0.002, decay_rate=40.0,
                  filt="lp", f_cutoff=300, gain=0.5, delay=0.003),
        VoiceSpec(osc="fm", freq=2200, fm_ratio=1.5, fm_index=0.8,
                  attack=0.0003, decay_rate=90.0, filt="lp", f_cutoff=4000,
                  gain=0.2, delay=0.001)]),
    "Cherry MX Red": SoundSpec(duration=0.12, layers=[
        VoiceSpec(osc="noise_white", attack=0.0005, decay_rate=300.0,
                  filt="bp", f_cutoff=1200, f_high=3500, gain=0.1),
        VoiceSpec(osc="sine", freq=150, attack=0.0015, decay_rate=45.0,
                  filt="lp", f_cutoff=500, gain=0.65),
        VoiceSpec(osc="sine", freq=75, attack=0.002, decay_rate=35.0,
                  filt="lp", f_cutoff=250, gain=0.55, delay=0.001)]),
    "IBM Model M": SoundSpec(duration=0.30, layers=[
        VoiceSpec(osc="fm", freq=3500, fm_ratio=3.0, fm_index=1.5,
                  attack=0.0002, decay_rate=15.0, filt="lp", f_cutoff=10000,
                  gain=0.4, reverb=0.1),
        VoiceSpec(osc="noise_white", attack=0.0003, decay_rate=250.0,
                  filt="bp", f_cutoff=1500, f_high=4500, gain=0.3,
                  delay=0.0005),
        VoiceSpec(osc="sine", freq=120, attack=0.001, decay_rate=30.0,
                  filt="lp", f_cutoff=300, gain=0.5, delay=0.002)]),
    "ASMR Deep Thock": SoundSpec(duration=0.20, layers=[
        VoiceSpec(osc="sine", freq=100, attack=0.004, decay_rate=22.0,
                  filt="lp", f_cutoff=400, gain=0.8, reverb=0.15),
        VoiceSpec(osc="sine", freq=55, attack=0.005, decay_rate=18.0,
                  filt="lp", f_cutoff=200, gain=0.65, delay=0.001),
        VoiceSpec(osc="noise_pink", attack=0.008, decay_rate=40.0,
                  filt="lp", f_cutoff=800, gain=0.15)]),
    "Typewriter": SoundSpec(duration=0.25, layers=[
        VoiceSpec(osc="modal", modes=[(1500, 6.0, 1.0), (3000, 4.0, 0.5),
                                      (4500, 2.0, 0.3)], attack=0.001, 
                  decay_rate=5.0, filt="lp", f_cutoff=6000, gain=0.4, 
                  reverb=0.2),
        VoiceSpec(osc="noise_white", attack=0.0005, decay_rate=120.0,
                  filt="bp", f_cutoff=1000, f_high=3000, gain=0.3,
                  delay=0.005),
        VoiceSpec(osc="sine", freq=150, attack=0.001, decay_rate=20.0,
                  filt="lp", f_cutoff=400, gain=0.4, delay=0.004)]),
    "Cyberpunk Hacker": SoundSpec(duration=0.12, layers=[
        VoiceSpec(osc="fm", freq=800, fm_ratio=3.5, fm_index=2.0,
                  attack=0.0005, decay_rate=50.0, filt="lp", f_cutoff=4500,
                  gain=0.4, bitcrush=8),
        VoiceSpec(osc="sine", freq=80, attack=0.002, decay_rate=30.0,
                  filt="lp", f_cutoff=200, gain=0.5, delay=0.001)]),
    "Crystal Chime": SoundSpec(duration=0.60, layers=[
        VoiceSpec(osc="modal", modes=[(1500, 7.0, 1.0), (3150, 5.0, 0.5),
                                      (4950, 3.0, 0.3), (7050, 2.0, 0.2)],
                  inharmonicity=0.0005, attack=0.0001, decay_rate=5.0,
                  filt="lp", f_cutoff=16000, gain=0.5, reverb=0.3)]),
}


class ModularSoundEngine:
    def __init__(self, sr=AUDIO_SAMPLE_RATE):
        self.sr = sr

    def _render_voice(self, spec: VoiceSpec, n: int,
                      rng: np.random.RandomState) -> np.ndarray:
        if spec.osc == "sine":
            sig = DSP.osc_sine(spec.freq, n, self.sr)
        elif spec.osc == "fm":
            sig = DSP.osc_fm(spec.freq, spec.fm_ratio, spec.fm_index, n,
                             self.sr)
        elif spec.osc == "noise_white":
            sig = DSP.noise_white(n, rng)
        elif spec.osc == "noise_pink":
            sig = DSP.noise_pink(n, rng)
        elif spec.osc == "modal" and spec.modes:
            sig = DSP.modal(spec.modes, n, self.sr, spec.inharmonicity)
        elif spec.osc == "pluck":
            sig = DSP.osc_pluck(spec.freq, n, self.sr)
        else:
            sig = np.zeros(n, dtype=np.float64)
            
        sig *= DSP.env_exp(n, self.sr, attack=spec.attack,
                           decay_rate=spec.decay_rate,
                           attack_curve=spec.attack_curve)
                           
        if spec.filt == "lp":
            sig = DSP.filt_lp(sig, spec.f_cutoff, self.sr)
        elif spec.filt == "hp":
            sig = DSP.filt_hp(sig, spec.f_cutoff, self.sr)
        elif spec.filt == "bp":
            sig = DSP.filt_bp(sig, spec.f_cutoff, spec.f_high, self.sr)
            
        if spec.bitcrush > 0:
            sig = DSP.bitcrush(sig, spec.bitcrush)
            
        if spec.drive > 0:
            sig = DSP.sat_tanh(sig, spec.drive)
            
        if spec.reverb > 0:
            sig = DSP.add_reverb(sig, self.sr, mix=spec.reverb)
            
        d = int(spec.delay * self.sr)
        if d > 0 and d < n:
            return np.concatenate(
                [np.zeros(d, dtype=np.float64), sig[:n - d]]) * spec.gain
        return sig * spec.gain

    def render(self, spec: SoundSpec, seed: int) -> np.ndarray:
        rng = np.random.RandomState(seed)
        max_tail = 0.0
        for v in spec.layers:
            if v.reverb > 0:
                max_tail = max(max_tail, 1.0)
                
        n = int(self.sr * (spec.duration + max_tail))
        mix = np.zeros(n, dtype=np.float64)
        for v in spec.layers:
            mix += self._render_voice(v, n, rng)
            
        fade_samp = int(self.sr * 0.05)
        if len(mix) > fade_samp:
            mix[-fade_samp:] *= np.linspace(1, 0, fade_samp)
            
        return DSP.to_int16(DSP.filt_hp(mix, 20.0, self.sr, n_taps=63))


def _normalize_to_lufs(x, sr, target_lufs=-14.0):
    if len(x) < sr // 2:
        return x
    xk = DSP.filt_hp(np.asarray(x, dtype=np.float64), 60.0, sr, n_taps=63)
    ms = float(np.mean(xk * xk))
    if ms < 1e-20:
        return x
    loudness = -0.691 + 10.0 * np.log10(ms)
    if not np.isfinite(loudness) or loudness <= -70.0:
        return x
    gain = 10.0 ** ((target_lufs - loudness) / 20.0)
    return (np.asarray(x, dtype=np.float64) * gain).astype(np.float32)


_CLICK_BANK_CACHE: Dict[Tuple[str, int], dict] = {}


class SimpleSoundGen:
    _QWERTY_ROWS = ("`1234567890-=", "qwertyuiop[]\\", "asdfghjkl;'",
                    "zxcvbnm,./")
    _ROW_PITCH_SHIFT = [1.5, 0.5, -0.5, -2.0]

    def __init__(self, sr=AUDIO_SAMPLE_RATE, preset="Mechanical",
                 stereo=False, reverb_amt=0.1):
        self.sr = sr
        self.preset = preset
        self.stereo = stereo
        key = (preset, sr)
        bank = _CLICK_BANK_CACHE.get(key)
        if bank is None:
            engine = ModularSoundEngine(sr)
            spec = MODULAR_SOUND_PRESETS.get(
                preset, MODULAR_SOUND_PRESETS["Mechanical"])
            bank = {"clicks": [engine.render(spec, i) for i in range(32)],
                    "spaces": [engine.render(spec, 100 + i)
                               for i in range(16)],
                    "enters": [engine.render(spec, 200 + i)
                               for i in range(8)]}
            _CLICK_BANK_CACHE[key] = bank
        self.clicks = bank["clicks"]
        self.spaces = bank["spaces"]
        self.enters = bank["enters"]

    @staticmethod
    def _pitch_shift(sound: np.ndarray, semitones: float) -> np.ndarray:
        if semitones == 0 or len(sound) < 8:
            return sound
        factor = 2 ** (semitones / 12)
        n_orig = len(sound)
        n_new = max(1, int(n_orig / factor))
        if n_new == n_orig:
            return sound
        indices = np.linspace(0, n_orig - 1, n_new)
        i0 = indices.astype(np.int32)
        frac = indices - i0
        i1 = np.minimum(i0 + 1, n_orig - 1)
        s = sound.astype(np.float64)
        return (s[i0] * (1 - frac) + s[i1] * frac).astype(np.int16)

    def _get_pitch_shift(self, char: str) -> float:
        if char in (' ', '\n', '\t'):
            return -3.0
        c = char.lower()
        for r, row in enumerate(self._QWERTY_ROWS):
            if c in row:
                return self._ROW_PITCH_SHIFT[r]
        return 0.0

    def generate_pcm(self, timestamps, volume=0.5) -> np.ndarray:
        if not timestamps:
            return np.zeros(0, dtype=np.int16)
        sr = self.sr
        total = max(ts for ts, _ in timestamps) + 0.3
        n = int(sr * total)
        rng = random.Random(98765)
        raw, starts_i, pans = [], [], []
        for ts, ch in timestamps:
            if ch == "\n":
                snd, vm, pan = (rng.choice(self.enters),
                                rng.uniform(1.05, 1.20), 0.2)
            elif ch == " ":
                snd, vm, pan = (rng.choice(self.spaces),
                                rng.uniform(1.00, 1.15), 0.0)
            else:
                base_snd = rng.choice(self.clicks)
                shift = self._get_pitch_shift(ch)
                snd = (self._pitch_shift(base_snd, shift)
                       if shift != 0 else base_snd)
                vm, pan = rng.uniform(0.95, 1.10), rng.uniform(-0.3, 0.3)
            s = int(ts * sr)
            e = min(s + len(snd), n)
            if s < n:
                raw.append(snd[:e - s].astype(np.float32) * vm)
                starts_i.append(s)
                if self.stereo:
                    pans.append(pan)
        if not raw:
            return np.zeros(n, dtype=np.int16)
        if self.stereo:
            ml = np.zeros(n, dtype=np.float32)
            mr = np.zeros(n, dtype=np.float32)
            for i, snd in enumerate(raw):
                s = starts_i[i]
                pan = pans[i]
                lg = np.cos((pan + 1.0) * np.pi / 4.0)
                rg = np.sin((pan + 1.0) * np.pi / 4.0)
                e = min(s + len(snd), n)
                ml[s:e] += snd[:e - s] * lg
                mr[s:e] += snd[:e - s] * rg
            ml = _normalize_to_lufs(ml, sr) * volume
            mr = _normalize_to_lufs(mr, sr) * volume
            out = np.empty(n * 2, dtype=np.int16)
            out[0::2] = np.clip(ml * 32767, -32768, 32767).astype(np.int16)
            out[1::2] = np.clip(mr * 32767, -32768, 32767).astype(np.int16)
            return out
        mix = np.zeros(n, dtype=np.float32)
        for i, snd in enumerate(raw):
            s = starts_i[i]
            e = min(s + len(snd), n)
            mix[s:e] += snd[:e - s]
        mix = _normalize_to_lufs(mix, sr) * volume
        return np.clip(mix * 32767, -32768, 32767).astype(np.int16)


class SoundscapeGenerator:
    def __init__(self, sr=48000):
        self.sr = sr

    def _moving_avg(self, x, win_size):
        if win_size < 2:
            return x
        cumsum = np.cumsum(np.insert(x.astype(np.float64), 0, 0))
        return (cumsum[win_size:] - cumsum[:-win_size]) / float(win_size)

    def _simple_lp(self, x, cutoff):
        win_size = max(2, int(self.sr / (2 * math.pi * cutoff)))
        if win_size >= len(x):
            return np.zeros_like(x)
        y = self._moving_avg(x, win_size)
        return np.pad(y, (0, len(x) - len(y)), 'edge')[:len(x)]

    def generate_pcm(self, duration: float, soundscape_type: str,
                     volume: float = 0.3) -> np.ndarray:
        n = int(self.sr * duration)
        if n <= 0:
            return np.zeros(0, dtype=np.int16)
        rng = np.random.RandomState(42)

        if soundscape_type == "Rain":
            x = rng.randn(n).astype(np.float64)
            x = self._simple_lp(x, 2000.0)
            for _ in range(max(0, (n - 1000) // (self.sr * 2))):
                pos = rng.randint(0, n - 1000)
                t_drop = np.arange(1000) / self.sr
                drop = np.exp(-t_drop * 10.0) * np.sin(2 * np.pi * 150 * t_drop)
                x[pos:pos + 1000] += drop * 0.5
            return (x * volume * 0.5).astype(np.int16)
        if soundscape_type == "Wind":
            x = np.cumsum(rng.randn(n).astype(np.float64))
            x -= np.mean(x)
            pk = np.max(np.abs(x))
            if pk > 0:
                x /= pk
            x = self._simple_lp(x, 500.0)
            t = np.arange(n) / self.sr
            lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.1 * t)
            return (x * lfo * volume * 0.8).astype(np.int16)
        if soundscape_type == "Ocean":
            x = np.cumsum(rng.randn(n).astype(np.float64))
            x -= np.mean(x)
            pk = np.max(np.abs(x))
            if pk > 0:
                x /= pk
            x = self._simple_lp(x, 800.0)
            t = np.arange(n) / self.sr
            lfo = (0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t)
                   * np.sin(2 * np.pi * 0.05 * t))
            return (x * lfo * volume * 0.7).astype(np.int16)
        if soundscape_type == "Drone":
            t = np.arange(n) / self.sr
            x = np.zeros(n, dtype=np.float64)
            for f in [55, 110, 165, 220]:
                vib = 1.0 + 0.005 * np.sin(2 * np.pi * 0.5 * t)
                x += np.sin(2 * np.pi * f * vib * t)
            x /= 4.0
            return (x * volume).astype(np.int16)
        if soundscape_type == "Forest":
            x = self._simple_lp(rng.randn(n).astype(np.float64), 1000.0)
            chirp_len = self.sr // 2
            for _ in range(max(0, (n - chirp_len) // (self.sr * 5))):
                pos = rng.randint(0, n - chirp_len)
                f0 = rng.uniform(2000, 4000)
                f1 = f0 + rng.uniform(500, 1500)
                t_chirp = np.arange(chirp_len) / self.sr
                freq = f0 + (f1 - f0) * t_chirp / max(t_chirp[-1], 1e-9)
                phase = 2 * np.pi * np.cumsum(freq) / self.sr
                chirp = np.sin(phase) * np.exp(-t_chirp * 5)
                x[pos:pos + chirp_len] += chirp * 0.2
            return (x * volume * 0.5).astype(np.int16)
        return np.zeros(n, dtype=np.int16)


# ── music-folder scan, ffmpeg decode, BGM track generator ─────────────────────
def scan_music_folder() -> List[Tuple[str, str]]:
    """Scan music/ recursively. Returns [(display_name, relative_path), ...]."""
    files = []
    for p in scan_directory_tree(
        MUSIC_DIR,
        extensions=AUDIO_FILE_EXTS,
        skip_dirs=SCAN_SKIP_DIRS,
        recursive=True,
        max_depth=10,
        follow_symlinks=False,
    ):
        rel_music = p.relative_to(MUSIC_DIR)
        display = (str(rel_music) if str(rel_music.parent) != "."
                   else rel_music.name)
        files.append((display, str(p.relative_to(CWD))))
    return files


def decode_audio_file(path, duration, sr=AUDIO_SAMPLE_RATE) -> np.ndarray:
    """Decode any audio file to mono PCM via ffmpeg; loop if shorter."""
    if not HAS_FFMPEG:
        logger.warning("ffmpeg required to decode BGM file: %s", path)
        return np.zeros(0, dtype=np.int16)
    cmd = ["ffmpeg", "-i", str(path), "-f", "s16le", "-ac", "1",
           "-ar", str(sr), "-"]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or len(result.stdout) == 0:
        logger.warning("ffmpeg decode failed for %s", path)
        return np.zeros(0, dtype=np.int16)
    pcm = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float64)
    needed = int(sr * duration)
    if len(pcm) < needed and len(pcm) > 0:
        reps = (needed // len(pcm)) + 1
        pcm = np.tile(pcm, reps)
        fade = int(sr * 1.0)
        if len(pcm) > 2 * fade:
            pcm[:fade] *= np.linspace(0, 1, fade)
            pcm[-fade:] *= np.linspace(1, 0, fade)
    return pcm[:needed].astype(np.int16)


def generate_bgm_track(cfg, duration, n, sr=AUDIO_SAMPLE_RATE):
    """Generate the BGM bus."""
    if not getattr(cfg, "bgm_enabled", False):
        return None, None
    source = getattr(cfg, "bgm_source", "Rain")
    vol = getattr(cfg, "bgm_volume", 30) / 100.0
    try:
        if source in SOUNDSCAPE_TYPES:
            gen = SoundscapeGenerator(sr)
            pcm = gen.generate_pcm(duration, source, 1.0)
        else:
            pcm = decode_audio_file(CWD / source, duration, sr)
        if len(pcm) == 0:
            return None, None
        f = pcm.astype(np.float64)
        f = _normalize_to_lufs(f, sr, target_lufs=-24.0)
        f *= vol
        return f[:n], f[:n]
    except Exception:
        logger.debug("BGM generation failed (non-fatal)")
        return None, None


# ═════════════════════════════════════════════════════════════════════════════
# §6  ANIMATION
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class TypingProfile:
    name: str = "Default"
    wpm: int = 100
    start_pause: float = 0.5
    end_pause: float = 1.5
    is_text: bool = False


PAUSE_TOKEN = '\x01'
PAUSE_TOKEN_SECS = 0.5


class TypingAnimator:
    """Deterministic keystroke timeline with jitter, pause tokens, backspace
    replay, and cursor tracking."""

    _WPM_MIN, _WPM_MAX = 1, 1000

    def __init__(self, code: str, profile: TypingProfile, seed: int = 42,
                 build_replay: bool = True):
        self.code, self.profile = code, profile
        rng = random.Random(seed)
        chars = split_graphemes(code) if profile.is_text else list(code)
        base_delay = 1.0 / ((profile.wpm * 5) / 60)
        t = profile.start_pause
        self._timestamps, self.timeline = [], []
        for char in chars:
            if char == PAUSE_TOKEN:
                t += PAUSE_TOKEN_SECS
                self.timeline.append((t, char))
                self._timestamps.append(t)
                continue
            self.timeline.append((t, char))
            self._timestamps.append(t)
            if char in ".!?":
                t += base_delay * rng.uniform(4.0, 6.0)
            elif char in ",;:":
                t += base_delay * rng.uniform(2.0, 3.5)
            elif char == '\n':
                t += base_delay * rng.uniform(3.0, 5.0)
            else:
                t += base_delay * rng.uniform(0.7, 1.3)
        self._duration = t + profile.end_pause
        if build_replay:
            buf = []
            self._replay = []
            for ts, ch in self.timeline:
                if ch == '\b':
                    if buf:
                        buf.pop()
                elif ch != PAUSE_TOKEN:
                    buf.append(ch)
                self._replay.append(("".join(buf), ts))
            self._replay_ts = [ts for _, ts in self._replay]
        else:
            self._replay = []
            self._replay_ts = []

    def duration(self) -> float:
        return self._duration

    def visible_at(self, t: float) -> int:
        return bisect.bisect_right(self._timestamps, t) if t > 0 else 0

    def text_visible_at(self, t: float) -> str:
        idx = bisect.bisect_right(self._replay_ts, t)
        return self._replay[idx - 1][0] if idx > 0 else ""

    def cursor_at(self, t: float) -> Tuple[int, int]:
        text = self.text_visible_at(t)
        if not text:
            return 0, 0
        lines = text.split("\n")
        return len(lines) - 1, len(lines[-1])

    def char_timestamps(self) -> List[Tuple[float, str]]:
        return self.timeline

    def active_key_at(self, t: float,
                      fade: float = 0.18) -> Tuple[Optional[str], float]:
        if not self._timestamps or t < self._timestamps[0]:
            return None, 0.0
        idx = bisect.bisect_right(self._timestamps, t)
        if idx == 0:
            return None, 0.0
        last_ts, last_char = self.timeline[idx - 1]
        if last_char in ('\b', PAUSE_TOKEN):
            return None, 0.0
        elapsed = t - last_ts
        if elapsed < fade:
            return last_char, max(0.0, (1.0 - elapsed / fade) ** 1.5)
        return None, 0.0

    @classmethod
    def find_wpm_for_target(cls, text: str, target_dur: float,
                            start_pause: float = 0.5,
                            end_pause: float = 1.5,
                            is_text: bool = False, seed: int = 42) -> int:
        if target_dur <= start_pause + end_pause:
            return cls._WPM_MAX

        def dur(wpm):
            return cls(text, TypingProfile(wpm=wpm, start_pause=start_pause,
                                           end_pause=end_pause,
                                           is_text=is_text),
                       seed=seed, build_replay=False).duration()

        if dur(cls._WPM_MAX) > target_dur:
            return cls._WPM_MAX
        if dur(cls._WPM_MIN) <= target_dur:
            return cls._WPM_MIN
        lo, hi = cls._WPM_MIN, cls._WPM_MAX
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if dur(mid) > target_dur:
                lo = mid
            else:
                hi = mid
        return hi

    @classmethod
    def estimate_duration(cls, text: str, wpm: int,
                          start_pause: float = 0.5,
                          end_pause: float = 1.5,
                          is_text: bool = False, seed: int = 42) -> float:
        return cls(text, TypingProfile(wpm=wpm, start_pause=start_pause,
                                       end_pause=end_pause, is_text=is_text),
                   seed=seed, build_replay=False).duration()


_SOLVER_CACHE: Dict[tuple, int] = {}


def find_wpm_cached(text: str, target: float, sp: float = OVERHEAD_MIN,
                    ep: float = OVERHEAD_MAX, is_text: bool = False,
                    seed: int = 42) -> int:
    key = (_text_key(text), round(target, 1), sp, ep, is_text, seed)
    hit = _SOLVER_CACHE.get(key)
    if hit is None:
        hit = TypingAnimator.find_wpm_for_target(text, target, sp, ep,
                                                 is_text=is_text, seed=seed)
        if len(_SOLVER_CACHE) > 64:
            _SOLVER_CACHE.clear()
        _SOLVER_CACHE[key] = hit
    return hit


_EST_CACHE: Dict[tuple, float] = {}


def estimate_duration_cached(text, wpm, sp=OVERHEAD_MIN, ep=OVERHEAD_MAX,
                             is_text=False, seed=42) -> float:
    key = (_text_key(text), wpm, sp, ep, is_text, seed)
    hit = _EST_CACHE.get(key)
    if hit is None:
        hit = TypingAnimator.estimate_duration(text, wpm, sp, ep,
                                               is_text=is_text, seed=seed)
        if len(_EST_CACHE) > 128:
            _EST_CACHE.clear()
        _EST_CACHE[key] = hit
    return hit


# ═════════════════════════════════════════════════════════════════════════════
# §7  RENDERING
# ═════════════════════════════════════════════════════════════════════════════
def _remap_qwerty(base, mapping):
    rows = [list(r) for r in base]
    pos = {}
    for ri, row in enumerate(rows):
        for ci, (label, w) in enumerate(row):
            if len(label) == 1:
                pos[label.lower()] = (ri, ci)
    for src, dst in mapping.items():
        if src.lower() in pos:
            ri, ci = pos[src.lower()]
            rows[ri][ci] = (dst, rows[ri][ci][1])
    return rows


KEYBOARD_LAYOUTS = {
    "QWERTY": [
        [("`", 1), ("1", 1), ("2", 1), ("3", 1), ("4", 1), ("5", 1),
         ("6", 1), ("7", 1), ("8", 1), ("9", 1), ("0", 1), ("-", 1),
         ("=", 1), ("Bksp", 2)],
        [("Tab", 1.5), ("Q", 1), ("W", 1), ("E", 1), ("R", 1), ("T", 1),
         ("Y", 1), ("U", 1), ("I", 1), ("O", 1), ("P", 1), ("[", 1),
         ("]", 1), ("\\", 1.5)],
        [("Caps", 1.75), ("A", 1), ("S", 1), ("D", 1), ("F", 1), ("G", 1),
         ("H", 1), ("J", 1), ("K", 1), ("L", 1), (";", 1), ("'", 1),
         ("Enter", 2.25)],
        [("Shift", 2.25), ("Z", 1), ("X", 1), ("C", 1), ("V", 1), ("B", 1),
         ("N", 1), ("M", 1), (",", 1), (".", 1), ("/", 1), ("Shift", 2.75)],
        [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("", 6.25),
         ("Alt", 1.25), ("Fn", 1.25), ("Menu", 1.25), ("Ctrl", 1.25)],
    ],
}
KEYBOARD_LAYOUTS["AZERTY"] = _remap_qwerty(
    KEYBOARD_LAYOUTS["QWERTY"],
    {"q": "A", "w": "Z", "a": "Q", "z": "W", ";": "M", "m": ","})
KEYBOARD_LAYOUTS["QWERTZ"] = _remap_qwerty(
    KEYBOARD_LAYOUTS["QWERTY"], {"y": "Z", "z": "Y"})
KEYBOARD_LAYOUTS["Dvorak"] = _remap_qwerty(
    KEYBOARD_LAYOUTS["QWERTY"],
    {"q": "'", "w": ",", "e": ".", "r": "P", "t": "Y", "y": "F", "u": "G",
     "i": "C", "o": "R", "p": "L", "s": "O", "d": "E", "f": "U", "g": "I",
     "h": "D", "j": "H", "k": "T", "l": "N", "z": ";", "x": "Q", "c": "J",
     "v": "K", "b": "X", "n": "B", "m": "M"})
KEYBOARD_LAYOUTS["Colemak"] = _remap_qwerty(
    KEYBOARD_LAYOUTS["QWERTY"],
    {"e": "F", "r": "P", "t": "G", "y": "J", "u": "L", "i": "U", "o": "Y",
     "p": ";", "s": "R", "d": "S", "f": "T", "g": "D", "j": "N", "k": "E",
     "l": "I", ";": "O", "n": "K"})


class KeyboardOverlay:
    def __init__(self, video_w, video_h, layout_name="QWERTY", theme=None,
                 opacity=0.82, position="bottom_center"):
        self.video_w, self.video_h = video_w, video_h
        self.theme = theme or THEMES["Dracula"]
        self.opacity = opacity
        self.position = position.lower().replace(" ", "_")
        self.rows = KEYBOARD_LAYOUTS.get(layout_name,
                                         KEYBOARD_LAYOUTS["QWERTY"])
        self.char_map = {}
        for ri, row in enumerate(self.rows):
            for ci, (label, w) in enumerate(row):
                if len(label) == 1:
                    self.char_map[label] = \
                        self.char_map[label.lower()] = (ri, ci)
                low = label.lower()
                if "enter" in low:
                    self.char_map["\n"] = (ri, ci)
                elif "tab" in low:
                    self.char_map["\t"] = (ri, ci)
                elif "bksp" in low:
                    self.char_map["\b"] = (ri, ci)
                elif label == "":
                    self.char_map[" "] = (ri, ci)
        for s, b in {"~": "`", "!": "1", "@": "2", "#": "3", "$": "4",
                     "%": "5", "^": "6", "&": "7", "*": "8", "(": "9",
                     ")": "0", "_": "-", "+": "=", "{": "[", "}": "]",
                     "|": "\\", ":": ";", '"': "'", "<": ",", ">": ".",
                     "?": "/"}.items():
            if b in self.char_map:
                self.char_map[s] = self.char_map[b]
        target_kb_w = int(video_w * 0.65)
        self.key_unit = max(14, min(55, int(target_kb_w / 15.0)))
        self.key_gap = max(2, self.key_unit // 14)
        self.key_h = int(self.key_unit * 0.82)
        self._kb_w = int(max(sum(w for _, w in r) for r in self.rows)
                         * self.key_unit
                         + (max(len(r) for r in self.rows) - 1)
                         * self.key_gap)
        self._kb_h = int(len(self.rows) * self.key_h
                         + (len(self.rows) - 1) * self.key_gap)
        self._kb_x, self._kb_y = 0, 0
        self.key_rects = {}
        self.reposition()

    def height_needed(self):
        return self._kb_h + max(16, self.video_h // 30)

    def reposition(self, y_target=None):
        m_x = max(8, self.video_w // 60)
        m_y = max(8, self.video_h // 60)
        if "center" in self.position:
            self._kb_x = (self.video_w - self._kb_w) // 2
        elif "right" in self.position:
            self._kb_x = self.video_w - self._kb_w - m_x
        else:
            self._kb_x = m_x
        if "top" in self.position:
            self._kb_y = m_y
        elif y_target is not None:
            self._kb_y = max(m_y, min(y_target,
                                      self.video_h - self._kb_h - m_y))
        else:
            self._kb_y = self.video_h - self._kb_h - m_y
        self._rebuild_key_rects()

    def _rebuild_key_rects(self):
        self.key_rects = {}
        for ri, row in enumerate(self.rows):
            x = self._kb_x
            for ci, (_, w) in enumerate(row):
                kw = int(w * self.key_unit) - self.key_gap
                y = self._kb_y + ri * (self.key_h + self.key_gap)
                self.key_rects[(ri, ci)] = QRect(x, y, kw, self.key_h)
                x += int(w * self.key_unit)

    def resolve_key(self, ch):
        return self.char_map.get(ch)

    def draw(self, p: QPainter, active_key=None, flash=0.0):
        p.save()
        p.setOpacity(self.opacity)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th = self.theme
        radius = max(3, self.key_unit // 8)
        pad = max(6, self.key_unit // 4)
        p.setPen(QPen(QColor(th["window_border"]),
                      max(1, self.key_unit // 20)))
        p.setBrush(QColor(th["title_bar"]))
        p.drawRoundedRect(self._kb_x - pad, self._kb_y - pad,
                          self._kb_w + 2 * pad, self._kb_h + 2 * pad,
                          radius * 2, radius * 2)
        kbg = QColor(th["background"])
        kbr = QColor(th["window_border"])
        lc = QColor(th["foreground"])
        mc = QColor(th["line_number"])
        hlb = QColor(th["cursor"])
        hkf = hlg = None
        hle = 0
        if flash > 0 and active_key is not None:
            hkf = QColor(int(kbg.red() + (hlb.red() - kbg.red()) * flash),
                         int(kbg.green() + (hlb.green() - kbg.green()) * flash),
                         int(kbg.blue() + (hlb.blue() - kbg.blue()) * flash))
            hlg = QColor(hlb)
            hlg.setAlpha(int(60 * flash))
            hle = max(3, int(self.key_unit * 0.12 * flash))
        for (ri, ci), rect in self.key_rects.items():
            label = self.rows[ri][ci][0]
            ia = (active_key is not None and active_key == (ri, ci))
            if ia and hkf is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hlg)
                p.drawRoundedRect(rect.adjusted(-hle, -hle, hle, hle),
                                  radius, radius)
                p.setBrush(hkf)
                p.setPen(QPen(kbr, 1))
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(kbr.darker(150))
                p.drawRoundedRect(rect.adjusted(0, 3, 0, 3), radius, radius)
                p.setBrush(kbg)
                p.setPen(QPen(kbr, 1))
            p.drawRoundedRect(rect, radius, radius)
            if label:
                p.setPen(mc if len(label) > 1 else lc)
                p.setFont(QFont("Segoe UI",
                                max(7, int(self.key_unit * 0.30))))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        p.restore()


class StudioRenderer:
    _TOKEN_RULES = [
        (r'\bdef\b|\bclass\b|\bimport\b|\bfrom\b|\breturn\b|\bif\b|\belse\b'
         r'|\belif\b|\bfor\b|\bwhile\b|\btry\b|\bexcept\b|\bwith\b|\bas\b'
         r'|\bin\b|\bnot\b|\band\b|\bor\b|\blambda\b|\bpass\b|\braise\b'
         r'|\byield\b|\basync\b|\bawait\b', 'keyword'),
        (r'\b\d+\.?\d*\b', 'number'),
        (r'"[^"\n]*"|\'[^\'\n]*\'', 'string'),
        (r'#[^\n]*|//[^\n]*', 'comment'),
        (r'@\w+', 'decorator'),
        (r'\b[A-Z][A-Za-z0-9_]*\b', 'class_name'),
        (r'\bprint\b|\blen\b|\brange\b|\bstr\b|\bint\b|\bfloat\b|\blist\b'
         r'|\bdict\b', 'builtin'),
        (r'[\u2500-\u257F\u2580-\u259F]', 'builtin'),
        (r'[\u2600-\u26FF\u2700-\u27BF]', 'decorator'),
        (r'[\U0001F300-\U0001FAFF]', 'function'),
    ]
    _COMBINED = '|'.join(f'(?P<g{i}>{pat})'
                         for i, (pat, _) in enumerate(_TOKEN_RULES))

    def __init__(self, width, height, theme_name="Dracula",
                 font_family="Consolas", font_size=22,
                 show_line_numbers=True, show_window_chrome=True,
                 padding=24, tab_size=4, language="python",
                 ascii_art_mode=False, config=None, pane_idx=0,
                 line_diffs=None, kb_overlay=None, is_text=False,
                 code: str = "", title: str = ""):
        self.width, self.height = width, height
        self.theme = THEMES.get(theme_name, THEMES["Dracula"])
        self.font_family, self.font_size = font_family, font_size
        self.show_line_numbers = show_line_numbers
        self.show_window_chrome = show_window_chrome
        self.padding = max(8, min(padding, min(width, height) // 30))
        self.tab_size = tab_size
        self.language = language
        self.ascii_art_mode = ascii_art_mode
        self.is_text = is_text
        self.config = config
        self.pane_idx = pane_idx
        self.line_diffs = line_diffs or {}
        self.kb_overlay = kb_overlay
        self.code = code
        self.title = title
        self.CURSOR_BLINK = 0.53
        self.font = QFont(font_family, font_size)
        self.font.setFamilies(list(dict.fromkeys(
            [font_family, "JetBrains Mono", "DejaVu Sans Mono", "Consolas",
             "Noto Sans Mono CJK SC", "Segoe UI", "monospace"])) )
        self.font.setFixedPitch(not is_text)
        self.fm = QFontMetrics(self.font)
        self.char_w = max(1, self.fm.horizontalAdvance("M"))
        self.line_h = max(1, self.fm.height())
        self._qcolors = {k: QColor(v) for k, v in self.theme.items()
                         if isinstance(v, str) and v.startswith("#")}
        self._qc_fg = self._qcolors.get("foreground", QColor("#f8f8f2"))
        self._qc_ln = self._qcolors.get("line_number", QColor("#6272a4"))
        self._qc_cursor = self._qcolors.get("cursor", QColor("#f8f8f2"))
        self._qc_current = self._qcolors.get("current_line",
                                             QColor("#44475a"))
        self._qc_title_bg = self._qcolors.get("title_bar", QColor("#21222c"))
        self._qc_title_tx = self._qcolors.get("title_text",
                                              QColor("#8be9fd"))
        self._qc_border = self._qcolors.get("window_border",
                                            QColor("#191a21"))
        self._qc_bg = self._qcolors.get("background", QColor("#282a36"))
        self._qc_removed = QColor("#ff5555")
        self._token_cache = OrderedDict()
        self._token_lock = threading.Lock()
        px = max(1, width * height)
        self._cache_limit = max(1, min(8, 26_000_000 // px))
        self._frame_cache = OrderedDict()

    def _tokenize_pygments(self, text):
        return self._tokenize(text)

    @property
    def _tab_adv(self):
        return self.char_w * self.tab_size

    def _tokenize(self, text: str) -> List[Tuple[QColor, str]]:
        if self.is_text or not _HAS_PYGMENTS:
            return self._tokenize_regex(text)
        with self._token_lock:
            key = (self.language, hash(text))
            if key in self._token_cache:
                return self._token_cache[key]
            try:
                lexer = get_lexer_by_name(self.language, stripall=False)
                style_map = {"Token.Keyword": "keyword",
                             "Token.Literal.String": "string",
                             "Token.Literal.Number": "number",
                             "Token.Comment": "comment",
                             "Token.Name.Function": "function",
                             "Token.Name.Class": "class_name",
                             "Token.Name.Decorator": "decorator",
                             "Token.Name.Builtin": "builtin"}
                tokens, buf, cur = [], "", None
                for itype, value in lex(text, lexer):
                    name = str(itype)
                    style = None
                    for prefix, s in style_map.items():
                        if name.startswith(prefix):
                            style = s
                            break
                    if style == cur:
                        buf += value
                    else:
                        if buf:
                            tokens.append((self._color_for(cur), buf))
                        buf, cur = value, style
                if buf:
                    tokens.append((self._color_for(cur), buf))
            except Exception:
                tokens = self._tokenize_regex(text)
            self._token_cache[key] = tokens
            if len(self._token_cache) > 256:
                self._token_cache.popitem(last=False)
            return tokens

    def _color_for(self, style):
        return self._qcolors.get(style, self._qc_fg) if style else self._qc_fg

    def _tokenize_regex(self, text):
        color_map = {f"g{i}": self._qcolors.get(name, self._qc_fg)
                     for i, (_, name) in enumerate(self._TOKEN_RULES)}
        tokens, last = [], 0
        for m in re.finditer(self._COMBINED, text):
            if m.start() > last:
                tokens.append((self._qc_fg, text[last:m.start()]))
            for g, val in m.groupdict().items():
                if val:
                    tokens.append((color_map[g], val))
                    break
            last = m.end()
        if last < len(text):
            tokens.append((self._qc_fg, text[last:]))
        return tokens

    def _tokenize_markdown(self, line: str):
        out, i = [], 0
        for m in re.finditer(r'(\*\*[^*\n]+\*\*)|(\*[^*\n]+\*)|(`[^`\n]+`)',
                             line):
            if m.start() > i:
                out.append((line[i:m.start()], 'plain'))
            seg = m.group(0)
            if seg.startswith('**'):
                out.append((seg[2:-2], 'bold'))
            elif seg.startswith('`'):
                out.append((seg[1:-1], 'code'))
            else:
                out.append((seg[1:-1], 'italic'))
            i = m.end()
        if i < len(line):
            out.append((line[i:], 'plain'))
        return out or [("", 'plain')]

    def _md_style(self, style):
        f = QFont(self.font)
        if style == 'bold':
            f.setBold(True)
            return self._qc_fg, f
        if style == 'italic':
            f.setItalic(True)
            return self._qc_fg, f
        if style == 'code':
            f.setFamilies(["Consolas", "monospace"])
            return self._qcolors.get("string", self._qc_fg), f
        return self._qc_fg, f

    def _expand_tabs(self, line: str) -> str:
        return line.replace("\t", " " * self.tab_size)

    def _content_key(self, title, text):
        diff_key = (frozenset(self.line_diffs.items())
                    if self.line_diffs else frozenset())
        return (title, text, diff_key)

    def _render_content(self, title, text) -> QImage:
        img = QImage(self.width, self.height, QImage.Format.Format_ARGB32)
        img.fill(self._qc_bg)
        p = QPainter(img)
        try:
            self._paint_content(p, title, text)
        finally:
            p.end()
        return img

    def _paint_content(self, p: QPainter, title, text):
        w, h = self.width, self.height
        pad = self.padding
        title_h = int(self.line_h * 1.8) if self.show_window_chrome else 0
        if title_h:
            p.fillRect(0, 0, w, title_h, self._qc_title_bg)
            p.setPen(QPen(self._qc_border, 1))
            p.drawLine(0, title_h, w, title_h)
            dot_r = max(4, title_h // 5)
            p.setPen(Qt.PenStyle.NoPen)
            for i, color in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
                p.setBrush(QColor(color))
                cx = pad + i * dot_r * 3
                p.drawEllipse(cx, title_h // 2 - dot_r // 2, dot_r, dot_r)
            p.setPen(self._qc_title_tx)
            f = QFont(self.font)
            f.setPointSize(max(9, self.font_size - 4))
            p.setFont(f)
            p.drawText(QRect(0, 0, w, title_h),
                       Qt.AlignmentFlag.AlignCenter, title)
        area_y = title_h + pad
        line_w = (self.fm.horizontalAdvance("0" * 4) + 8
                  if self.show_line_numbers else 0)
        lines = self._expand_tabs(text).split("\n")
        n_shown = max(1, (h - area_y - pad) // self.line_h)
        use_md = self.is_text and bool(
            getattr(self.config, "txt_markdown", False))
        use_bubbles = self.is_text and bool(
            getattr(self.config, "txt_bubbles", False))
        for idx, line in enumerate(lines[:n_shown]):
            y = area_y + idx * self.line_h
            diff = self.line_diffs.get(idx)
            if diff == "removed":
                p.fillRect(0, y, w, self.line_h, QColor(255, 85, 85, 40))
            elif diff == "added":
                p.fillRect(0, y, w, self.line_h, QColor(80, 250, 123, 40))
            if idx == len(lines) - 1:
                p.fillRect(0, y, w, self.line_h, self._qc_current)
            if self.show_line_numbers:
                p.setPen(self._qc_ln)
                p.setFont(self.font)
                p.drawText(QRect(pad, y, line_w - 4, self.line_h),
                           Qt.AlignmentFlag.AlignRight, str(idx + 1))
            x = pad + line_w
            if use_bubbles:
                t = line.rstrip() or " "
                tw = min(self.fm.horizontalAdvance(t) + self.padding,
                         w - 3 * pad - line_w)
                th_ = self.line_h + 6
                from_left = (idx % 2 == 0)
                bx = pad + line_w if from_left else w - pad - tw
                bubble_bg = QColor(self._qc_title_bg)
                bubble_bg.setAlpha(200)
                p.setBrush(bubble_bg)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(bx, y, tw, th_, 10, 10)
                p.setPen(self._qc_fg)
                p.setFont(self.font)
                p.drawText(QRect(bx + 8, y, tw - 16, self.line_h),
                           Qt.AlignmentFlag.AlignVCenter
                           | (Qt.AlignmentFlag.AlignLeft if from_left
                              else Qt.AlignmentFlag.AlignRight), t)
                continue
            if self.ascii_art_mode:
                fm_w = self.fm.horizontalAdvance(line)
                cx = max(pad + line_w, (w - fm_w) // 2)
                p.setPen(self._qc_fg if diff != "removed"
                         else self._qc_removed)
                p.setFont(self.font)
                p.drawText(cx, y + self.fm.ascent(), line)
                continue
            if use_md:
                heading = re.match(r'^(#{1,3}) ', line)
                hsize = 1.0
                if heading:
                    line = line[heading.end():]
                    hsize = {1: 1.6, 2: 1.3, 3: 1.1}[len(heading.group(1))]
                for seg_text, style in self._tokenize_markdown(line):
                    color, fnt = self._md_style(style)
                    if style == 'plain' and hsize != 1.0:
                        fnt = QFont(self.font)
                        fnt.setBold(True)
                        fnt.setPointSizeF(self.font.pointSizeF() * hsize)
                    p.setFont(fnt)
                    p.setPen(color if diff != "removed"
                             else self._qc_removed)
                    p.drawText(x, y + self.fm.ascent(), seg_text)
                    x += self.fm.horizontalAdvance(seg_text)
            else:
                for color, seg in self._tokenize(line):
                    p.setFont(self.font)
                    p.setPen(color if diff != "removed"
                             else self._qc_removed)
                    p.drawText(x, y + self.fm.ascent(), seg)
                    x += self.fm.horizontalAdvance(seg)

    def _draw_cursor(self, p, text: str, t: float,
                     cursor_pos: Optional[Tuple[int, int]] = None):
        if not getattr(self.config, "show_cursor", True):
            return
        if cursor_pos is None:
            lines = self._expand_tabs(text).split("\n")
            if not lines:
                return
            cursor_pos = (len(lines) - 1, len(lines[-1]))
        cur_line, cur_col = cursor_pos
        title_h = int(self.line_h * 1.8) if self.show_window_chrome else 0
        pad = self.padding
        line_w = (self.fm.horizontalAdvance("0" * 4) + 8
                  if self.show_line_numbers else 0)
        area_y = title_h + pad
        n_shown = max(1, (self.height - area_y - pad) // self.line_h)
        if cur_line >= n_shown:
            return
        y = area_y + cur_line * self.line_h
        all_lines = self._expand_tabs(text).split("\n")
        line_text = all_lines[min(cur_line, len(all_lines) - 1)]
        x = pad + line_w + self.fm.horizontalAdvance(line_text[:cur_col])
        if int(t / self.CURSOR_BLINK) % 2 == 0:
            p.fillRect(x, y + 2, max(2, self.char_w // 3),
                       self.line_h - 4, self._qc_cursor)

    def _draw_crt(self, p):
        if not (self.is_text and getattr(self.config, "txt_crt", False)):
            return
        w, h = self.width, self.height
        scan = QColor(0, 0, 0, 45)
        for sy in range(0, h, 3):
            p.fillRect(0, sy, w, 1, scan)
        vignette = QLinearGradient(0, 0, 0, h)
        vignette.setColorAt(0.0, QColor(0, 0, 0, 0))
        vignette.setColorAt(0.85, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 70))
        p.fillRect(0, 0, w, h, vignette)

    def render_frame(self, p: QPainter, title: str, text: str, t: float,
                     active_key=None, flash=0.0,
                     cursor_pos: Optional[Tuple[int, int]] = None):
        key = self._content_key(title, text)
        content = self._frame_cache.get(key)
        if content is None:
            content = self._render_content(title, text)
            self._frame_cache[key] = content
            while len(self._frame_cache) > self._cache_limit:
                self._frame_cache.popitem(last=False)
        p.drawImage(0, 0, content)
        self._draw_cursor(p, text, t, cursor_pos)
        self._draw_crt(p)
        if self.kb_overlay is not None:
            self.kb_overlay.draw(p, active_key=active_key, flash=flash)


class MultiPaneRenderer:
    def __init__(self, panes, w, h, n_panes, layout="Grid", gap=20,
                 config=None):
        self.panes = list(panes)
        self.w, self.h = w, h
        self.n_panes = n_panes
        self.layout = layout
        self.gap = gap
        self.config = config
        self._scratch: Optional[QImage] = None

    @staticmethod
    def compute_pane_rects(w, h, n, layout="Grid", gap=20, config=None):
        def r(x, y, pw, ph):
            return QRect(x, y, max(1, pw), max(1, ph))
        if n == 1:
            return [r(0, 0, w, h)]
        if n == 2:
            if layout == "Stacked (50/50)":
                return [r(0, 0, w, h // 2 - gap // 2),
                        r(0, h // 2 + gap // 2, w, h // 2 - gap // 2)]
            ratio = 0.5
            if layout == "Junior Big (70/30)":
                ratio = 0.7
            elif layout == "Senior Big (70/30)":
                ratio = 0.3
            elif config is not None:
                ratio = getattr(config, "mw_ratio", 50) / 100.0
            split = int(w * ratio)
            return [r(0, 0, split - gap // 2, h),
                    r(min(w - 1, split + gap // 2), 0,
                      w - split - gap // 2, h)]
        if n == 3:
            top_h = (h - gap) // 2
            third = (w - 2 * gap) // 3
            return [r(0, 0, third, top_h),
                    r(third + gap, 0, third, top_h),
                    r(2 * (third + gap), 0, third, top_h)]
        top_h = (h - gap) // 2
        half_w = (w - gap) // 2
        return [r(0, 0, half_w, top_h),
                r(half_w + gap, 0, half_w, top_h),
                r(0, top_h + gap, half_w, top_h),
                r(half_w + gap, top_h + gap, half_w, top_h)]

    def duration(self) -> float:
        return max((a.duration() for _, a, _ in self.panes), default=2.0)

    def render_frame(self, t: float, scratch: bool = True) -> Optional[QImage]:
        if scratch and self._scratch is not None \
                and self._scratch.size() == (self.w, self.h):
            img = self._scratch
        else:
            img = QImage(self.w, self.h, QImage.Format.Format_ARGB32)
            if scratch:
                self._scratch = img
        if img.isNull():
            logger.error("Out of memory allocating %dx%d frame", self.w,
                         self.h)
            return None
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rects = self.compute_pane_rects(self.w, self.h, self.n_panes,
                                        self.layout, self.gap, self.config)
        for i, (renderer, animator, title) in enumerate(self.panes):
            if i >= len(rects):
                break
            rect = rects[i]
            pane_img = QImage(rect.width(), rect.height(),
                              QImage.Format.Format_ARGB32)
            if pane_img.isNull():
                continue
            pane_img.fill(renderer._qc_bg)
            pp = QPainter(pane_img)
            active, flash = animator.active_key_at(t)
            on_screen = animator.text_visible_at(t)
            cur = animator.cursor_at(t)
            renderer.render_frame(pp, title, on_screen, t,
                                  active_key=active, flash=flash,
                                  cursor_pos=cur)
            pp.end()
            progress = min(1.0, max(0.0, t / max(0.01, animator.duration())))
            if getattr(self.config, "yt_zoom", False):
                zoom = 1.0 + 0.08 * progress
                pp = QPainter(pane_img)
                pp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
                pp.translate(pane_img.width() / 2, pane_img.height() / 2)
                pp.scale(zoom, zoom)
                pp.translate(-pane_img.width() / 2, -pane_img.height() / 2)
                pp.drawImage(0, 0, pane_img)
                pp.end()
            if getattr(self.config, "yt_focus", False):
                pp = QPainter(pane_img)
                fade_h = int(pane_img.height() * 0.18)
                top = QLinearGradient(0, 0, 0, fade_h)
                top.setColorAt(0, QColor(0, 0, 0, 120))
                top.setColorAt(1, QColor(0, 0, 0, 0))
                pp.fillRect(0, 0, pane_img.width(), fade_h, top)
                bot = QLinearGradient(0, pane_img.height() - fade_h, 0,
                                      pane_img.height())
                bot.setColorAt(0, QColor(0, 0, 0, 0))
                bot.setColorAt(1, QColor(0, 0, 0, 120))
                pp.fillRect(0, pane_img.height() - fade_h,
                            pane_img.width(), fade_h, bot)
                pp.end()
            p.drawImage(rect, pane_img)
        if getattr(self.config, "_show_time_badge", False):
            p.setPen(QColor("#ffffff"))
            f = QFont("monospace", max(12, self.h // 60))
            p.setFont(f)
            p.drawText(12, self.h - 12,
                       f"{t:6.1f}s / {self.duration():.1f}s")
        p.end()
        return img


class FileItem:
    def __init__(self, path: str, checked: bool = True, status: str = ""):
        self.path = path
        self.checked = checked
        self.status = status
        self.wpm_override: Optional[int] = None


class BaseRenderStrategy(ABC):
    @abstractmethod
    def build_panes(self, config: StudioConfig, files,
                    custom_code) -> MultiPaneRenderer:
        ...

    def _output_size(self, config):
        if getattr(config, "preview_size", None):
            return config.preview_size
        return RESOLUTIONS.get(config.resolution, (1920, 1080))

    def _shorts_capped_wpm(self, code, user_wpm, shorts_on, is_text=False):
        if not shorts_on:
            return user_wpm
        cap = find_wpm_cached(code, SHORTS_TARGET_SECS, OVERHEAD_MIN,
                              OVERHEAD_MAX, is_text=is_text)
        return min(user_wpm, cap)

    @staticmethod
    def _clamp(text: str) -> str:
        if len(text) > MAX_INPUT_CHARS:
            logger.warning("Input truncated from %d to %d chars",
                           len(text), MAX_INPUT_CHARS)
            return text[:MAX_INPUT_CHARS] + "\n# … truncated (input too long)"
        return text

    def _get_code(self, config, files, custom_code):
        title = ("text.txt" if config.mode == StudioMode.TEXT_EMOJI
                 else "custom_code")
        if config.use_custom and custom_code:
            return (self._clamp(convert_shortcodes(custom_code)), "text",
                    title)
        checked = [f for f in files if f.checked]
        if checked:
            it = checked[0]
            return (self._clamp(read_text_file(it.path, config.txt_clean)),
                    detect_language(it.path), Path(it.path).name)
        if custom_code:
            return (self._clamp(convert_shortcodes(custom_code)), "text",
                    title)
        return ("# Add a file or enable Custom Code\n", "text", "empty")

    def _make_animator(self, code, wpm, is_text=False,
                       start_pause=OVERHEAD_MIN) -> TypingAnimator:
        return TypingAnimator(code, TypingProfile(
            wpm=wpm, is_text=is_text, start_pause=start_pause))

    def _make_renderer(self, config, w, h, code, title, lang,
                       pane_idx=0, line_diffs=None) -> StudioRenderer:
        font, size, auto_on = self._font_for(config, pane_idx)
        kb = None
        if getattr(config, "kb_enabled", False):
            kb = KeyboardOverlay(w, h, layout_name=config.kb_layout,
                                 theme=THEMES.get(config.theme),
                                 opacity=config.kb_opacity,
                                 position=config.kb_position)
        r = StudioRenderer(w, h, theme_name=config.theme, font_family=font,
                           font_size=size, language=lang,
                           ascii_art_mode=getattr(config, "ascii_art", False),
                           config=config, pane_idx=pane_idx,
                           line_diffs=line_diffs, kb_overlay=kb,
                           is_text=config.mode == StudioMode.TEXT_EMOJI,
                           code=code, title=title)
        if auto_on:
            longest = max((len(l) for l in code.splitlines()), default=80)
            avail = w - 2 * r.padding - (r.fm.horizontalAdvance("0000") + 8)
            fit = int(avail / max(1, longest) / 0.6)
            fit_size = max(8, min(28, fit))
            if fit_size != size:
                r.font.setPointSize(fit_size)
                r.fm = QFontMetrics(r.font)
                r.char_w = max(1, r.fm.horizontalAdvance("M"))
                r.line_h = max(1, r.fm.height())
        return r

    def _font_for(self, config, pane_idx):
        mode_attr = {
            StudioMode.CODE_YT: ("font_yt", "font_sz_yt", "font_sz_auto_yt"),
            StudioMode.TEXT_EMOJI: ("font_txt", "font_sz_txt",
                                    "font_sz_auto_txt"),
            StudioMode.JR_VS_SR: ("font_jr", "font_sz_jr",
                                  "font_sz_auto_jr"),
        }
        pane_attrs = {0: ("font_mw", "font_sz_mw", "font_sz_auto_mw"),
                      1: ("font_mw_2", "font_sz_mw_2", "font_sz_auto_mw_2"),
                      2: ("font_mw_3", "font_sz_mw_3", "font_sz_auto_mw_3"),
                      3: ("font_mw_4", "font_sz_mw_4", "font_sz_auto_mw_4")}
        if config.mode == StudioMode.MULTI_WINDOW:
            fa, sa, aa = pane_attrs.get(pane_idx, pane_attrs[0])
        elif config.mode == StudioMode.JR_VS_SR and pane_idx == 1:
            fa, sa, aa = "font_sr", "font_sz_sr", "font_sz_auto_sr"
        else:
            fa, sa, aa = mode_attr.get(config.mode, pane_attrs[0])
        font = getattr(config, fa, "Consolas")
        size = getattr(config, sa, 22)
        auto = getattr(config, aa, False)
        if auto:
            w, h = self._output_size(config)
            size = max(10, min(28, int(h / 45)))
        return font, size, auto


class ExportManager(QObject):
    batch_started = Signal(int)
    batch_progress = Signal(int, str)
    item_progress = Signal(int, int, str)
    batch_finished = Signal(int, int)
    item_status_changed = Signal(int, str)
    state_changed = Signal(object, object)

    def __init__(self, main_window=None):
        super().__init__(main_window)
        self._fsm = StateMachine("export", ExportState.IDLE, _EXPORT_FSM)
        self._fsm.subscribe(lambda old, new: self.state_changed.emit(old, new))
        self._cancel = False
        self._thread: Optional[QThread] = None
        self._cfg_snapshot: Optional[StudioConfig] = None
        self._current_name = ""
        self._current_path = ""
        self._current_item_idx = 0
        self._current_item_total = 0
        self._last_file_frames = 0
        self._frames_rendered = 0
        self._batch_t0 = 0.0
        self._item_t0 = 0.0

    @property
    def state(self) -> ExportState:
        return self._fsm.state

    def cancel(self):
        if self._fsm.can(ExportState.CANCELLING):
            self._fsm.transition(ExportState.CANCELLING)
            self._cancel = True

    def stop_thread(self):
        if self._thread is not None and self._thread.isRunning():
            self._cancel = True
            self._thread.wait(5000)

    def start(self, items):
        self._fsm.require(ExportState.IDLE)
        self._fsm.transition(ExportState.STARTING)
        checked = [copy.deepcopy(it) for it in items if it.checked]
        self._cfg_snapshot = copy.deepcopy(
            getattr(self.parent(), "config", None) or StudioConfig())
        if not checked:
            self._finish(0, 0)
            return
        self._cancel = False
        self._batch_t0 = _time.monotonic()
        self.batch_started.emit(len(checked))
        manager = self

        def run():
            ok = fail = 0
            for idx, item in enumerate(checked):
                if manager._fsm.state is ExportState.CANCELLING:
                    break
                manager._current_item_idx = idx
                manager._current_path = item.path
                manager._item_t0 = _time.monotonic()
                try:
                    manager._export_one(item)
                    ok += 1
                    manager.item_status_changed.emit(idx, "done")
                except ExportCancelled:
                    break
                except Exception as e:
                    logger.error(f"Export failed for {item.path}", exc_info=True)
                    fail += 1
                    manager.item_status_changed.emit(idx, f"failed: {e}")
                done = idx + 1
                elapsed = _time.monotonic() - manager._batch_t0
                eta = (elapsed / done * (len(checked) - done)) if done > 0 else 0
                manager.batch_progress.emit(
                    done, f"{Path(item.path).name} · ETA {eta:.0f}s")
            manager._finish(ok, fail)

        self._thread = QThread(self)
        self._thread.run = run
        self._thread.finished.connect(self._thread.deleteLater)
        self._fsm.transition(ExportState.RUNNING)
        self._thread.start()

    def _finish(self, ok, fail):
        if self._fsm.state is ExportState.IDLE:
            self.batch_finished.emit(ok, fail)
            return
        if self._fsm.state is not ExportState.FINISHED:
            try:
                self._fsm.transition(ExportState.FINISHED)
            except InvalidStateTransition:
                logger.exception("export FSM wedged in %s", self._fsm.state.name)
        self.batch_finished.emit(ok, fail)
        self._fsm.transition(ExportState.IDLE)

    def _build_panes_for(self, item: FileItem):
        cfg = self._cfg_snapshot or StudioConfig()
        items = [copy.deepcopy(item)]
        strategy = None
        host = self.parent()
        if host is not None and hasattr(host, "strategies"):
            strategy = host.strategies.get(cfg.mode)
        if strategy is None:
            strategy = self._fallback_strategy(cfg)
        return strategy.build_panes(cfg, items, cfg.custom_code), cfg

    def _fallback_strategy(self, cfg):
        import importlib
        mods = {"CODE_YT": ("code_yt_mode", "CodeYTStrategy"),
                "TEXT_EMOJI": ("text_emoji_mode", "TextEmojiStrategy"),
                "MULTI_WINDOW": ("multi_window_mode", "MultiWindowStrategy"),
                "JR_VS_SR": ("jr_vs_sr_mode", "JrVsSrStrategy")}
        mod_name, cls_name = mods.get(
            cfg.mode.name, ("code_yt_mode", "CodeYTStrategy"))
        return getattr(importlib.import_module(mod_name), cls_name)()

    def _stages(self, mpr, cfg, out_dir, name):
        stages = [("audio", lambda arts: self._stage_audio(mpr, cfg))]
        stages.append(("render",
                       lambda arts: self._stage_render(mpr, cfg, out_dir,
                                                       name,
                                                       arts.get("audio"))))
        if getattr(cfg, "yt_extras", False):
            stages.append(("thumbnails",
                           lambda arts: self._stage_thumbs(out_dir, name,
                                                           mpr)))
        if getattr(cfg, "gen_metadata", False):
            stages.append(("metadata",
                           lambda arts: self._stage_meta(out_dir, name, cfg)))
        return stages

    def _export_one(self, item: FileItem):
        host_log = getattr(self.parent(), "log", logger)
        mpr, cfg = self._build_panes_for(item)
        out_dir = Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            free = shutil.disk_usage(out_dir).free
            if free < 100 * 1024 * 1024:
                raise RuntimeError(
                    f"Insufficient disk space ({free // (1024 * 1024)}MB "
                    f"free) in {out_dir} — export aborted.")
            if free < 500 * 1024 * 1024:
                log_mode_event(host_log, "disk_low",
                            free_mb=free // (1024 * 1024))
        except OSError:
            pass
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = cfg.output_template.format(
            name=Path(item.path).stem, date=stamp,
            lang=mpr.panes[0][0].language)
        self._current_name = name
        fps = max(1, cfg.fps)
        dur = mpr.panes[0][1].duration()
        self._current_item_total = max(2, int(dur * fps))
        artifacts: Dict[str, Any] = {}
        for stage_name, stage_fn in self._stages(mpr, cfg, out_dir, name):
            if self._fsm.state is ExportState.CANCELLING:
                raise ExportCancelled()
            log_mode_event(host_log, "stage_begin", stage=stage_name,
                        file=Path(item.path).name)
            artifacts[stage_name] = stage_fn(artifacts)
            log_mode_event(host_log, "stage_done", stage=stage_name)
        log_mode_event(host_log, "render_done",
                    file=Path(item.path).name,
                    dur=round(mpr.duration(), 1))

    def _stage_audio(self, mpr, cfg) -> Optional[Path]:
        self.item_progress.emit(0, 1, "Audio")
        if not getattr(cfg, "sound_enabled", True):
            return None
        if cfg.mode == StudioMode.JR_VS_SR:
            presets = [cfg.jr_sound, cfg.sr_sound]
        else:
            presets = [cfg.sound_preset] * max(1, len(mpr.panes))
        n = int(AUDIO_SAMPLE_RATE * (mpr.duration() + 0.5))
        master_l = np.zeros(n, dtype=np.float64)
        master_r = np.zeros(n, dtype=np.float64)
        used = 0
        for i, (_r, animator, _t) in enumerate(mpr.panes):
            try:
                sg = SimpleSoundGen(preset=presets[i % len(presets)],
                                    stereo=cfg.stereo)
            except Exception:
                continue
            audible = [(ts, ch) for ts, ch in animator.char_timestamps()
                       if ch != PAUSE_TOKEN]
            pcm = sg.generate_pcm(audible, cfg.volume / 100.0)
            if len(pcm) == 0:
                continue
            if cfg.stereo and len(pcm) % 2 == 0:
                l = pcm[0::2].astype(np.float64)
                r = pcm[1::2].astype(np.float64)
            else:
                mono = pcm.astype(np.float64)
                l = r = mono
            l = l[:n]
            r = r[:n]
            master_l[:len(l)] += l
            master_r[:len(r)] += r
            used += 1
        has_typing = used > 0 and master_l.any()
        if has_typing:
            master_l /= max(1, used)
            master_r /= max(1, used)
        bgm_l, bgm_r = generate_bgm_track(cfg, mpr.duration(), n)
        if bgm_l is not None:
            master_l[:len(bgm_l)] += bgm_l
            master_r[:len(bgm_r)] += bgm_r
        if not master_l.any():
            return None
        st = np.empty(n * 2, dtype=np.int16)
        st[0::2] = DSP.to_int16(master_l)
        st[1::2] = DSP.to_int16(master_r)
        wav_path = TEMP_DIR / f"audio_{datetime.now().strftime('%H%M%S%f')}.wav"
        with wave.open(str(wav_path), "w") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(AUDIO_SAMPLE_RATE)
            wf.writeframes(st.tobytes())
        self.item_progress.emit(1, 1, "Audio")
        return wav_path

    def _stage_render(self, mpr, cfg, out_dir, name,
                      wav: Optional[Path]) -> Optional[Path]:
        renderer, animator, title = mpr.panes[0]
        w, h = mpr.w, mpr.h
        fps = max(1, cfg.fps)
        dur = animator.duration()
        n_frames = max(2, int(dur * fps))
        out_file = out_dir / f"{name}.mp4"
        self._frames_rendered = 0
        report_every = max(1, n_frames // 50)
        if HAS_FFMPEG:
            cmd = ["ffmpeg", "-y",
                   "-f", "rawvideo", "-pix_fmt", "bgra",
                   "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
            if wav:
                cmd += ["-i", str(wav), "-c:a", "aac", "-b:a", "192k",
                        "-shortest"]
            cmd += [*ENCODER_ARGS.get(cfg.encoder, ENCODER_ARGS[ENCODERS[0]]),
                    str(out_file)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            try:
                for i in range(n_frames):
                    if self._fsm.state is ExportState.CANCELLING:
                        break
                    t = i / fps
                    proc.stdin.write(self._render_frame_bgra(mpr, t, w, h))
                    self._frames_rendered += 1
                    if i % report_every == 0 or i == n_frames - 1:
                        self.item_progress.emit(i + 1, n_frames, "Rendering")
                proc.stdin.close()
                self.item_progress.emit(n_frames, n_frames,
                                        "Muxing audio" if wav
                                        else "Finalizing")
                try:
                    proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.terminate()
            except BrokenPipeError:
                proc.terminate()
        else:
            frames_dir = TEMP_DIR / f"frames_{name}"
            frames_dir.mkdir(parents=True, exist_ok=True)
            step = max(1, n_frames // 24)
            for i in range(0, n_frames, step):
                if self._fsm.state is ExportState.CANCELLING:
                    break
                img = mpr.render_frame(i / fps, scratch=False)
                if img is not None:
                    img.save(str(frames_dir / f"frame_{i:06d}.png"))
                self._frames_rendered += 1
                if (i // step) % 5 == 0:
                    self.item_progress.emit(i + 1, n_frames,
                                            "Rendering (PNG fallback)")
            marker = out_dir / f"{name}.txt"
            marker.write_text(
                f"rendered: frames sampled\n"
                f"ffmpeg available: {HAS_FFMPEG}\n", encoding="utf-8")
            return marker
        self._last_file_frames = self._frames_rendered
        return out_file if out_file.exists() else None

    def _stage_thumbs(self, out_dir, name, mpr):
        renderer, animator, _t = mpr.panes[0]
        self.item_progress.emit(1, 1, "Thumbnails")
        for pct, tag in ((0.25, "a"), (0.50, "b"), (0.75, "c")):
            img = mpr.render_frame(animator.duration() * pct, scratch=False)
            if img is None:
                continue
            p = QPainter(img)
            f = QFont(renderer.font)
            f.setPointSize(max(24, renderer.font_size * 2))
            f.setBold(True)
            p.setFont(f)
            band_h = img.height() // 5
            p.fillRect(0, img.height() - band_h, img.width(), band_h,
                       QColor(0, 0, 0, 160))
            p.setPen(QColor("#ffffff"))
            p.drawText(QRect(0, img.height() - band_h, img.width(), band_h),
                       Qt.AlignmentFlag.AlignCenter,
                       Path(renderer.title).stem)
            p.end()
            img.save(str(out_dir / f"{name}_thumb_{tag}.png"))

    def _stage_meta(self, out_dir, name, cfg):
        self.item_progress.emit(1, 1, "Metadata")
        (out_dir / f"{name}_metadata.txt").write_text(
            f"Title: export — Typing ASMR ({cfg.sound_preset})\n"
            f"Tags: typing, asmr, coding\n", encoding="utf-8")

    def _render_frame_bgra(self, mpr, t, w, h) -> bytes:
        img = mpr.render_frame(t, scratch=False)
        if img is None:
            return bytes(w * h * 4)
        if img.format() != QImage.Format.Format_ARGB32:
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
        return bytes(img.constBits())


class PreviewWorker(QThread):
    frame_ready = Signal(QImage)
    failed = Signal(str)

    def __init__(self, host):
        super().__init__(host)
        self._stop = False

    def request(self):
        pass

    def stop(self):
        self._stop = True


class PreviewController:
    def __init__(self, main_window=None):
        self.mw = main_window

    def invalidate(self):
        if self.mw is not None and hasattr(self.mw, "invalidate"):
            self.mw.invalidate()

    def update(self):
        if self.mw is not None and hasattr(self.mw, "refresh_preview"):
            self.mw.refresh_preview()


# ═════════════════════════════════════════════════════════════════════════════
# §8  UI SHELL — THEME, PREVIEW FSM W/ WALL-CLOCK PLAYBACK + SYNC AUDIO
# ═════════════════════════════════════════════════════════════════════════════
CAT = {"base": "#1e1e2e", "mantle": "#181825", "crust": "#11111b",
       "surface0": "#313244", "surface1": "#45475a", "surface2": "#585b70",
       "text": "#cdd6f4", "subtext": "#a6adc8", "blue": "#89b4fa",
       "green": "#a6e3a1", "red": "#f38ba8"}

STYLE = f"""
QMainWindow, QDialog {{ background: {CAT['base']}; }}
QGroupBox {{ color: {CAT['text']}; font-weight: bold; font-size: 12px;
    border: 1px solid {CAT['surface1']}; border-radius: 8px;
    margin-top: 10px; padding-top: 14px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; }}
QLabel, QCheckBox {{ color: {CAT['text']}; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px;
    border: 1px solid {CAT['surface1']}; background: {CAT['surface0']}; }}
QCheckBox::indicator:checked {{ background: {CAT['blue']}; border-color: {CAT['blue']}; }}
QTableWidget {{ background: {CAT['mantle']}; color: {CAT['text']};
    gridline-color: {CAT['surface0']}; border: none; outline: none;
    border-radius: 6px; }}
QTableWidget::item {{ padding: 4px 6px;
    border-bottom: 1px solid {CAT['crust']}; }}
QTableWidget::item:selected {{ background: {CAT['blue']}; color: {CAT['base']}; }}
QHeaderView::section {{ background: {CAT['base']}; color: {CAT['subtext']};
    border: none; padding: 4px; font-size: 10px; }}
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit {{
    background: {CAT['surface0']}; color: {CAT['text']};
    border: 1px solid {CAT['surface1']}; border-radius: 4px;
    padding: 4px 8px; min-height: 22px; }}
QPushButton {{ background: {CAT['surface0']}; color: {CAT['text']};
    border: 1px solid {CAT['surface1']}; border-radius: 6px;
    padding: 6px 12px; min-height: 22px; }}
QPushButton:hover {{ background: {CAT['surface1']}; border-color: {CAT['blue']}; }}
QPushButton:disabled {{ color: {CAT['surface1']}; }}
QPushButton#primary {{ background: {CAT['blue']}; color: {CAT['base']};
    font-weight: bold; border: none; }}
QProgressBar {{ background: {CAT['surface0']}; border: none; border-radius: 4px;
    text-align: center; color: {CAT['text']}; min-height: 16px; }}
QProgressBar::chunk {{ background: {CAT['blue']}; border-radius: 4px; }}
QTabWidget::pane {{ border: 1px solid {CAT['surface1']}; border-radius: 6px;
    background: {CAT['base']}; top: -1px; }}
QTabBar::tab {{ background: {CAT['surface0']}; color: {CAT['subtext']};
    padding: 6px 12px; border: 1px solid {CAT['surface1']};
    border-bottom: none; border-top-left-radius: 6px;
    border-top-right-radius: 6px; font-weight: bold; }}
QTabBar::tab:selected {{ background: {CAT['base']}; color: {CAT['text']};
    border-bottom: 2px solid {CAT['blue']}; }}
QPlainTextEdit {{ background: {CAT['crust']}; color: {CAT['text']};
    border: 1px solid {CAT['surface1']}; border-radius: 4px; }}
QListWidget {{ background: {CAT['crust']}; color: {CAT['text']};
    border: 1px solid {CAT['surface1']}; border-radius: 4px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: {CAT['mantle']}; width: 8px; border: none;
    border-radius: 4px; }}
QScrollBar::handle:vertical {{ background: {CAT['surface1']};
    border-radius: 4px; min-height: 20px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSplitter::handle {{ background: {CAT['mantle']}; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QStatusBar {{ background: {CAT['mantle']}; color: {CAT['subtext']}; }}
"""


def apply_theme(app: QApplication):
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    pal = QPalette()
    for role, key in {
        QPalette.ColorRole.Window: "base",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "surface0",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface0",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "blue",
        QPalette.ColorRole.HighlightedText: "base",
    }.items():
        pal.setColor(role, QColor(CAT[key]))
    app.setPalette(pal)


# ── Custom List Widget for Shift+Click Group Selection ─────────────────────
class FileSelectionListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionRectVisible(True)
        self._anchor_row = -1

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        clicked_row = self.currentRow()
        if clicked_row == -1:
            return
            
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self._anchor_row != -1 and self._anchor_row != clicked_row:
                start = min(self._anchor_row, clicked_row)
                end = max(self._anchor_row, clicked_row)
                target_state = self.item(clicked_row).checkState()
                
                panel = self.parent()
                if hasattr(panel, '_updating'):
                    panel._updating = True
                
                for i in range(start, end + 1):
                    self.item(i).setCheckState(target_state)
                    
                if hasattr(panel, '_updating'):
                    panel._updating = False
                if hasattr(panel, 'selection_changed'):
                    panel.selection_changed.emit()
        else:
            self._anchor_row = clicked_row


# ── Background Scanner Thread ──────────────────────────────────────────────
class DirectoryScanWorker(QThread):
    """Scans directories in the background to prevent UI freezing."""
    files_found = Signal(list)
    scan_finished = Signal(int)

    def __init__(self, root_dir, extensions, recursive, max_depth):
        super().__init__()
        self.root_dir = root_dir
        self.extensions = extensions
        self.recursive = recursive
        self.max_depth = max_depth

    def run(self):
        try:
            files = scan_directory_tree(
                Path(self.root_dir),
                extensions=self.extensions,
                skip_dirs=SCAN_SKIP_DIRS,
                recursive=self.recursive,
                max_depth=self.max_depth,
                max_files=10000,  # Hard limit to prevent memory issues
                follow_symlinks=False,
            )
            files = sorted(files, key=lambda p: str(p).lower())
            self.files_found.emit([str(f) for f in files])
            self.scan_finished.emit(len(files))
        except Exception:
            self.files_found.emit([])
            self.scan_finished.emit(0)


class FileSelectionPanel(QGroupBox):
    """File selection panel showing only file names, with live filtering and drag & drop."""

    selection_changed = Signal()

    def __init__(self, title="Input Files", max_files=1,
                 name_filter="All Files (*)", hint="", parent=None):
        super().__init__(title, parent)
        self.max_files = max_files
        self.name_filter = name_filter
        self._updating = False
        self.scan_extensions: frozenset = SUPPORTED_EXTENSIONS
        self.scan_max_depth: int = 10
        self._scan_worker = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        
        self.list_widget = FileSelectionListWidget(self)
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setSelectionRectVisible(True)
        
        self.list_widget.setAcceptDrops(True)
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.list_widget.dragEnterEvent = self._drag_enter_event
        self.list_widget.dragMoveEvent = self._drag_move_event
        self.list_widget.dropEvent = self._drop_event
        
        lay.addWidget(self.list_widget, 1)
        
        if hint:
            h = QLabel(hint)
            h.setWordWrap(True)
            h.setStyleSheet(f"color: {CAT['subtext']}; font-size: 10px;")
            lay.addWidget(h)
            
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        
        self.scan_btn = QPushButton("📁 Scan")
        self.scan_btn.setToolTip("Scan a directory for files")
        self.scan_btn.clicked.connect(self._on_scan_btn_clicked)
        row.addWidget(self.scan_btn)
        
        self.recursive_chk = QCheckBox("Subdirs")
        self.recursive_chk.setChecked(True)
        self.recursive_chk.setToolTip("Search inside subfolders")
        row.addWidget(self.recursive_chk)
        
        self.scan_all_chk = QCheckBox("All Types")
        self.scan_all_chk.setToolTip("Ignore file extensions and include everything")
        row.addWidget(self.scan_all_chk)
        
        row.addStretch()
        
        self.add_btn = QPushButton("➕ Add")
        self.add_btn.clicked.connect(self._add_files)
        row.addWidget(self.add_btn)
        
        self.rm_btn = QPushButton("➖ Remove")
        self.rm_btn.clicked.connect(self._remove_selected)
        row.addWidget(self.rm_btn)
        
        self.clear_btn = QPushButton("✖ Clear")
        self.clear_btn.clicked.connect(self.clear)
        row.addWidget(self.clear_btn)
        
        lay.addLayout(row)
        
        brow = QHBoxLayout()
        brow.setContentsMargins(0, 0, 0, 0)
        brow.setSpacing(4)
        for label, slot in [("☑ All", self.select_all),
                            ("☐ None", self.select_none),
                            ("⇄ Invert", self.invert_selection)]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            brow.addWidget(b)
        brow.addStretch()
        lay.addLayout(brow)
        
        frow = QHBoxLayout()
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setSpacing(4)
        frow.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to search list...")
        self.filter_edit.textChanged.connect(self._filter_list)
        frow.addWidget(self.filter_edit, 1)
        lay.addLayout(frow)

        self.list_widget.itemChanged.connect(self._on_item_changed)
        sc = QShortcut(QKeySequence("Ctrl+A"), self.list_widget,
                       activated=self.select_all)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def set_scan_options(self, *, recursive: bool = True,
                         max_depth: int = 10,
                         extensions: Optional[frozenset] = None) -> None:
        self.scan_max_depth = max(0, int(max_depth))
        if extensions is not None:
            self.scan_extensions = frozenset(extensions)

    def _get_start_dir(self) -> str:
        win = self.window()
        if hasattr(win, 'config'):
            return getattr(win.config, 'input_dir', str(CWD / "input"))
        return str(CWD / "input")

    def paths(self) -> List[str]:
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_widget.count())]

    def checked_paths(self) -> List[str]:
        return [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_widget.count())
                if self.list_widget.item(i).checkState()
                == Qt.CheckState.Checked]

    def selected_paths(self) -> List[str]:
        return [i.data(Qt.ItemDataRole.UserRole) for i in self.list_widget.selectedItems()]

    @staticmethod
    def _make_item(path, checked=True):
        item = QListWidgetItem(Path(path).name)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Checked if checked
                           else Qt.CheckState.Unchecked)
        return item

    def set_paths(self, paths: List[str],
                  states: Optional[Dict[str, bool]] = None):
        self._updating = True
        try:
            self.list_widget.clear()
            for p in paths:
                self.list_widget.addItem(
                    self._make_item(p, (states or {}).get(p, True)))
        finally:
            self._updating = False
        self.selection_changed.emit()

    def clear(self):
        self.list_widget.clear()
        self.selection_changed.emit()

    def _filter_list(self, text):
        text = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())

    def _set_all_checks(self, state: bool):
        self._updating = True
        try:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    item.setCheckState(
                        Qt.CheckState.Checked if state
                        else Qt.CheckState.Unchecked)
        finally:
            self._updating = False
        self.selection_changed.emit()

    def select_all(self):
        self._set_all_checks(True)

    def select_none(self):
        self._set_all_checks(False)

    def invert_selection(self):
        self._updating = True
        try:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if not item.isHidden():
                    item.setCheckState(
                        Qt.CheckState.Unchecked
                        if item.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked)
        finally:
            self._updating = False
        self.selection_changed.emit()

    def _add_files(self):
        start_dir = self._get_start_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Add", start_dir, f"{self.name_filter};;All Files (*)")
        
        existing = set(self.paths())
        for p in paths:
            if p not in existing:
                self.list_widget.addItem(self._make_item(p))
        self.selection_changed.emit()

    def _on_scan_btn_clicked(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.terminate()
            self._scan_worker.wait(500)
            self._on_scan_finished(0)
        else:
            self._scan_directory()

    def _scan_directory(self, path=None):
        if path is None or not Path(path).is_dir():
            path = QFileDialog.getExistingDirectory(self, "Select Directory to Scan",
                                                 self._get_start_dir())
            if not path:
                return

        self.scan_btn.setText("✖ Stop")
        exts = None if self.scan_all_chk.isChecked() else self.scan_extensions
        recursive = self.recursive_chk.isChecked()
        
        self._scan_worker = DirectoryScanWorker(
            path, exts, recursive, self.scan_max_depth
        )
        self._scan_worker.files_found.connect(self._on_scan_files_found)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.start()

    def _on_scan_files_found(self, files):
        existing_lower = {p.lower() for p in self.paths()}
        for sp in files:
            if sp.lower() not in existing_lower:
                self.list_widget.addItem(self._make_item(sp))
                existing_lower.add(sp.lower())
        self.selection_changed.emit()

    def _on_scan_finished(self, total_found):
        self.scan_btn.setText("📁 Scan")
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(
                f"Scan complete. Found {total_found} files.", 4000)

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.selection_changed.emit()

    def _on_item_changed(self, item):
        if not self._updating:
            self.selection_changed.emit()

    def _drag_enter_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drag_move_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _drop_event(self, event):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.terminate()
            self._scan_worker.wait(500)
            self._on_scan_finished(0)
            
        existing = set(self.paths())
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p and p not in existing:
                if Path(p).is_dir():
                    self._scan_directory(p)
                else:
                    self.list_widget.addItem(self._make_item(p))
                    existing.add(p)
        self.selection_changed.emit()

    def statusBar_tip(self, msg):
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(msg, 4000)


class StudioMainWindow(QMainWindow):
    WINDOW_TITLE = "Typing Video Studio"
    STRATEGIES: dict = {}
    SETTINGS_MIN_W, SETTINGS_MAX_W = 320, 440
    DEBOUNCE_MS = 150
    PREVIEW_SCALE = 0.5
    _QUALITY_SCALES = [0.5, 0.75, 1.0]
    SETTINGS_PATH = SETTINGS_FILE
    DEMO_FILES: dict = {}
    MODE_LOG_NAME = ""
    FILE_PANEL_TITLE = "Input Files"
    FILE_PANEL_MAX = 1
    FILE_PANEL_FILTER = "All Files (*)"
    FILE_PANEL_HINT = ""
    FILE_PANEL_STRICT_ORDER = False

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.WINDOW_TITLE)
        self.resize(1400, 900)
        self._loading = False
        self._preview_fraction = 0.2
        self._preview_snapshot = None
        self._cached_panes = None
        self._cached_panes_key = None
        self._failed_fingerprint = None
        self._playback_t = 0.0
        self._preview_dirty = True
        self._clock = QElapsedTimer()
        self._last_ui_update = 0.0
        self._exp_total = 0
        self._exp_done = 0
        self._exp_clock = QElapsedTimer()
        self.log = (get_mode_logger(self.MODE_LOG_NAME)
                    if self.MODE_LOG_NAME else logger)
        log_mode_event(self.log, "session_start", title=self.WINDOW_TITLE,
                       ffmpeg=HAS_FFMPEG, pygments=_HAS_PYGMENTS)

        self.config = StudioConfig.load(self.SETTINGS_PATH)
        self.strategies = dict(self.STRATEGIES)
        self._items = []
        self.export_manager = ExportManager(self)
        self.export_manager.state_changed.connect(self._on_export_state)
        self.export_manager.batch_started.connect(self._on_export_started)
        self.export_manager.batch_progress.connect(self._on_export_progress)
        self.export_manager.item_progress.connect(self._on_item_progress)
        self.export_manager.batch_finished.connect(self._on_export_finished)
        self.export_manager.item_status_changed.connect(self._on_item_status)
        self._preview_fsm = StateMachine("preview", PreviewState.EMPTY, _PREVIEW_FSM)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(self.splitter, 1)
        self._build_settings_panel()
        self._build_preview_panel()
        outer.addWidget(self._build_bottom_bar())

        self.preview_worker = PreviewWorker(self)
        self._hide_progress_timer = QTimer(self)
        self._hide_progress_timer.setSingleShot(True)
        self._hide_progress_timer.setInterval(3000)
        self._hide_progress_timer.timeout.connect(self._hide_progress_bar)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._dispatch_preview)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(2000)
        self._save_timer.timeout.connect(
            lambda: self.config.save(self.SETTINGS_PATH))
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)
        self._play_timer.timeout.connect(self._playback_tick)
        self.setStatusBar(QStatusBar())

        self.tabs = self.make_tabs()
        for tab in self.tabs:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(tab)
            self.settings_tabs.addTab(
                scroll, getattr(tab, "TAB_LABEL", type(tab).__name__))
        self.settings_tabs.currentChanged.connect(self._on_settings_tab_changed)
        self._loading = True
        try:
            for tab in self.tabs:
                tab.load_settings(self.config)
            if hasattr(self, "_post_load_settings"):
                self._post_load_settings()
        finally:
            self._loading = False

        self._load_demo_content()
        self._restore_geometry()
        self._install_shortcuts()
        QTimer.singleShot(0, self._render_preview_now)

    def _hide_progress_bar(self):
        self.progress_bar.setVisible(False)
        self.progress_detail.setVisible(False)

    def _on_export_state(self, old, new):
        busy = new.busy
        self.export_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(new in (ExportState.RUNNING,
                                        ExportState.STARTING))
        if new is ExportState.STARTING:
            self._hide_progress_timer.stop()
            self.progress_bar.setStyleSheet("")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            self.progress_detail.setVisible(True)
            self.progress_detail.setText("Starting export…")
        elif new is ExportState.CANCELLING:
            self.statusBar().showMessage("Cancelling…")
            self.progress_detail.setText("Cancelling…")
        elif new is ExportState.IDLE:
            if old is not ExportState.FINISHED:
                self._hide_progress_bar()

    def _on_export_started(self, total):
        self._exp_total = total
        self._exp_done = 0
        self._exp_done_frames_acc = 0
        self._exp_clock.restart()
        self._last_ui_update = 0.0
        self._hide_progress_timer.stop()
        self.progress_bar.setStyleSheet("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_detail.setVisible(True)
        self.progress_detail.setText(f"Exporting {total} item(s)…")
        self.statusBar().showMessage(
            f"Export started — {total} item(s)", 3000)

    def _on_item_progress(self, frames_done, frames_total, phase):
        now = _time.monotonic()
        if 0 < frames_done < frames_total and now - self._last_ui_update < 0.1:
            return
        self._last_ui_update = now
        items_done = self._exp_done
        total_items = max(1, self._exp_total)
        cur_frac = frames_done / max(1, frames_total)
        overall = (items_done + cur_frac) / total_items
        self.progress_bar.setValue(min(int(100 * overall), 99))
        elapsed = self._exp_clock.elapsed() / 1000.0
        if overall > 0.01:
            eta = elapsed / overall * (1 - overall)
        else:
            eta = 0
        name = self.export_manager._current_name or "?"
        self.progress_detail.setText(
            f"[{items_done + 1}/{total_items}] {phase} · "
            f"{frames_done}/{frames_total} · {name} · "
            f"ETA {format_duration(eta)}")

    def _on_export_progress(self, done, msg):
        self._exp_done = done
        elapsed = self._exp_clock.elapsed() / 1000.0
        remaining = self._exp_total - done
        if done > 0 and remaining > 0:
            eta = elapsed / done * remaining
            self.statusBar().showMessage(
                f"Exporting — {done}/{self._exp_total} done · "
                f"{format_duration(elapsed)} elapsed · "
                f"~{format_duration(eta)} remaining · {msg}", 10000)
        else:
            self.statusBar().showMessage(
                f"Exporting — {done}/{self._exp_total} done · {msg}", 10000)

    def _on_item_status(self, idx, status):
        total = max(1, self._exp_total)
        if status == "done":
            self.statusBar().showMessage(
                f"Item {idx + 1}/{total} exported", 2000)
        elif status.startswith("failed"):
            reason = status[len("failed:"):].strip()
            self.statusBar().showMessage(
                f"Item {idx + 1}/{total} failed: {reason}", 5000)

    def _on_export_finished(self, ok_count, fail_count):
        log_mode_event(self.log, "export_finished", ok=ok_count, fail=fail_count)
        if fail_count == 0 and ok_count > 0:
            color = CAT["green"]
            msg = f"✓ Export finished — {ok_count} item(s) completed"
        elif ok_count == 0:
            color = CAT["red"]
            msg = f"✗ Export failed — {fail_count} item(s) failed"
        else:
            color = CAT["blue"]
            msg = f"⚠ Export partial — {ok_count} ok, {fail_count} failed"
        self.progress_bar.setStyleSheet(
            f"QProgressBar::chunk {{ background: {color}; "
            f"border-radius: 4px; }}")
        self.progress_bar.setValue(100)
        self.progress_detail.setText(msg)
        self.statusBar().showMessage(msg, 8000)
        self._hide_progress_timer.start()   

    def make_tabs(self) -> list:
        raise NotImplementedError

    def demo_content(self):
        return None, "print('Hello, Studio!')"

    # ── preview pipeline ─────────────────────────────────────────────────
    def _dispatch_preview(self):
        self._preview_snapshot = (
            copy.deepcopy(self.config),
            [copy.deepcopy(it) for it in self._items],
            self._preview_fraction)
        self._preview_dirty = True
        self._render_preview_now()
        for tab in self.tabs:
            if hasattr(tab, "_refresh_estimate"):
                tab._refresh_estimate()

    def _panes_fingerprint(self):
        cfg, items, _ = (self._preview_snapshot
                         or (self.config, self._items,
                             self._preview_fraction))
        item_paths = tuple(sorted(it.path for it in items if it.checked))
        return (cfg.mode,
                hash(json.dumps(asdict(cfg), sort_keys=True, default=str)),
                item_paths)

    def render_preview_panes(self):
        cfg, items, _ = (self._preview_snapshot
                         or (self.config, self._items,
                             self._preview_fraction))
        strategy = self.strategies.get(cfg.mode)
        if strategy is None:
            return None
        cfg = copy.deepcopy(cfg)
        w, h = strategy._output_size(cfg)
        cfg.preview_size = (max(2, int(w * self.PREVIEW_SCALE)),
                            max(2, int(h * self.PREVIEW_SCALE)))
        cfg._show_time_badge = True
        return strategy.build_panes(cfg, items, cfg.custom_code)

    def _get_or_build_panes(self):
        key = self._panes_fingerprint()
        if key == self._failed_fingerprint and self._cached_panes is None:
            return None
        if (self._cached_panes is None or key != self._cached_panes_key
                or self._preview_dirty):
            was_playing = self._preview_fsm.state is PreviewState.PLAYING
            saved_t = self._playback_t
            try:
                self._cached_panes = self.render_preview_panes()
            except Exception as e:
                logger.exception("preview build failed")
                self._failed_fingerprint = key
                self._cached_panes = None
                self._cached_panes_key = None
                self._preview_dirty = False
                if self._preview_fsm.can(PreviewState.ERROR):
                    self._preview_fsm.transition(PreviewState.ERROR)
                self._on_preview_failed(str(e))
                return None
            self._failed_fingerprint = None
            self._cached_panes_key = key
            self._preview_dirty = False
            if self._preview_fsm.state is not PreviewState.READY:
                self._preview_fsm.transition(PreviewState.READY)
            if was_playing:
                self._playback_t = min(
                    saved_t, self._cached_panes.duration())
                self._clock.restart()
            else:
                self._playback_t = 0.0
        return self._cached_panes

    def _current_preview_t(self, mpr):
        return (self._playback_t
                if self._preview_fsm.state is PreviewState.PLAYING
                or self._playback_t > 0
                else mpr.duration() * self._preview_fraction)

    def _render_preview_now(self):
        mpr = self._get_or_build_panes()
        if mpr is None:
            return
        t = self._current_preview_t(mpr)
        img = mpr.render_frame(t)
        if img is not None:
            self._show_preview_frame(img)
            self.preview_worker.frame_ready.emit(img)
        pct = int(100 * t / max(0.01, mpr.duration()))
        self.scrub_slider.blockSignals(True)
        self.scrub_slider.setValue(pct)
        self.scrub_slider.blockSignals(False)
        self.scrub_lbl.setText(f"{t:.1f}s / {format_duration(mpr.duration())}")

    def toggle_playback(self):
        mpr = self._get_or_build_panes()
        if mpr is None:
            return
        if self._preview_fsm.state is PreviewState.PLAYING:
            self._preview_fsm.transition(PreviewState.READY)
            self._play_timer.stop()
            self.play_btn.setText("▶ Play")
            self._stop_preview_audio()
        else:
            self._preview_fsm.transition(PreviewState.PLAYING)
            if self._playback_t >= mpr.duration():
                self._playback_t = 0.0
            self._clock.restart()
            self._play_timer.start()
            self.play_btn.setText("⏸ Pause")
            self._start_preview_audio(mpr)

    def _playback_tick(self):
        if self._preview_fsm.state is not PreviewState.PLAYING:
            self._play_timer.stop()
            return
        mpr = self._cached_panes
        if mpr is None:
            self._play_timer.stop()
            return
        self._playback_t = self._clock.elapsed() / 1000.0
        if self._playback_t >= mpr.duration():
            if self.loop_chk.isChecked():
                self._playback_t = 0.0
                self._clock.restart()
            else:
                self._playback_t = mpr.duration()
                self._preview_fsm.transition(PreviewState.READY)
                self.play_btn.setText("▶ Play")
                self._play_timer.stop()
                self._stop_preview_audio()
        self._render_preview_now()

    def _on_scrub(self, pct):
        self._preview_fraction = pct / 100.0
        mpr = self._cached_panes
        if mpr is not None and \
                self._preview_fsm.state is not PreviewState.PLAYING:
            self._playback_t = mpr.duration() * self._preview_fraction
            self._clock.restart()
            self._render_preview_now()

    def preview_timestamp(self, total_duration: float) -> float:
        return total_duration * self._preview_fraction

    def refresh_preview(self):
        self._failed_fingerprint = None
        if self._preview_fsm.state is PreviewState.ERROR:
            self._preview_fsm.transition(PreviewState.EMPTY)
        self.preview_info.setText("Rendering…")
        self._debounce_timer.start()

    def invalidate(self):
        self._debounce_timer.start()

    def _on_quality(self, idx):
        self.PREVIEW_SCALE = self._QUALITY_SCALES[min(idx, 2)]
        self._preview_dirty = True
        self._debounce_timer.start()

    # ── preview audio (synced with wall-clock playback) ──────────────────
    def _start_preview_audio(self, mpr):
        if not self.config.sound_enabled:
            return
        try:
            cfg = self.config
            if cfg.mode == StudioMode.JR_VS_SR:
                presets = [cfg.jr_sound, cfg.sr_sound]
            else:
                presets = [cfg.sound_preset] * max(1, len(mpr.panes))
            n = int(AUDIO_SAMPLE_RATE * (mpr.duration() + 0.5))
            master_l = np.zeros(n, dtype=np.float64)
            master_r = np.zeros(n, dtype=np.float64)
            used = 0
            for i, (_r, animator, _t) in enumerate(mpr.panes):
                try:
                    sg = SimpleSoundGen(
                        preset=presets[i % len(presets)],
                        stereo=cfg.stereo)
                except Exception:
                    continue
                audible = [(ts, ch)
                           for ts, ch in animator.char_timestamps()
                           if ch != PAUSE_TOKEN]
                pcm = sg.generate_pcm(audible, cfg.volume / 100.0)
                if len(pcm) == 0:
                    continue
                if cfg.stereo and len(pcm) % 2 == 0:
                    l = pcm[0::2].astype(np.float64)
                    r = pcm[1::2].astype(np.float64)
                else:
                    l = r = pcm.astype(np.float64)
                l = l[:n]
                r = r[:n]
                master_l[:len(l)] += l
                master_r[:len(r)] += r
                used += 1
            if used > 0 and master_l.any():
                master_l /= max(1, used)
                master_r /= max(1, used)
            bgm_l, bgm_r = generate_bgm_track(cfg, mpr.duration(), n)
            if bgm_l is not None:
                master_l[:len(bgm_l)] += bgm_l
                master_r[:len(bgm_r)] += bgm_r
            if not master_l.any():
                return
            st = np.empty(n * 2, dtype=np.int16)
            st[0::2] = DSP.to_int16(master_l)
            st[1::2] = DSP.to_int16(master_r)
            buf = io.BytesIO()
            with wave.open(buf, "w") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(AUDIO_SAMPLE_RATE)
                wf.writeframes(st.tobytes())
            self._play_buffer(buf.getvalue())
        except Exception:
            logger.debug("Preview audio skipped (non-fatal)")

    def _stop_preview_audio(self):
        if hasattr(self, "_audio_player"):
            self._audio_player.stop()

    # ── panels ───────────────────────────────────────────────────────────
    def _build_settings_panel(self):
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(self.SETTINGS_MIN_W)
        self.left_panel.setMaximumWidth(self.SETTINGS_MAX_W)
        lay = QVBoxLayout(self.left_panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(40)
        header.setStyleSheet(
            f"QFrame {{ background: {CAT['base']}; "
            f"border-bottom: 1px solid {CAT['crust']}; }}")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 8, 0)
        lbl = QLabel("⚙️  SETTINGS")
        lbl.setStyleSheet(
            f"font-weight: bold; color: {CAT['text']}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addStretch()
        lay.addWidget(header)

        # ── Unified tab widget: Global tab + Files tab + mode settings tabs ──
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.settings_tabs.setMovable(False)

        # 1. Global Settings tab (Auto-saving/loading input/output folders)
        self.settings_tabs.addTab(self._build_global_settings_tab(), "⚙️ Global")

        # 2. Files tab
        self.file_panel = FileSelectionPanel(
            title=self.FILE_PANEL_TITLE, max_files=self.FILE_PANEL_MAX,
            name_filter=self.FILE_PANEL_FILTER, hint=self.FILE_PANEL_HINT)
        self.file_panel.selection_changed.connect(self._on_file_selection)
        self.file_panel.set_scan_options(
            recursive=self.config.recursive_scan,
            max_depth=self.config.scan_depth,
            extensions=SUPPORTED_EXTENSIONS,
        )
        self.settings_tabs.addTab(self.file_panel, "📁 Files")

        lay.addWidget(self.settings_tabs, 1)
        self.splitter.addWidget(self.left_panel)
        
        # Trigger auto-scan of input folder shortly after UI loads
        QTimer.singleShot(100, self._auto_scan_input_dir)

    def _build_global_settings_tab(self) -> QWidget:
        """Creates the UI for Global Settings (Directories & Scan options)."""
        tab = QWidget()
        fl = QFormLayout(tab)
        fl.setContentsMargins(12, 12, 12, 12)
        fl.setSpacing(8)
        
        # Input Dir
        in_row = QHBoxLayout()
        in_row.setContentsMargins(0, 0, 0, 0)
        self.input_dir_edit = QLineEdit(self.config.input_dir)
        in_btn = QPushButton("Browse")
        in_btn.clicked.connect(self._browse_input_dir)
        in_row.addWidget(self.input_dir_edit, 1)
        in_row.addWidget(in_btn)
        fl.addRow("Input Folder:", in_row)
        
        # Output Dir
        out_row = QHBoxLayout()
        out_row.setContentsMargins(0, 0, 0, 0)
        self.output_dir_edit = QLineEdit(self.config.output_dir)
        out_btn = QPushButton("Browse")
        out_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(self.output_dir_edit, 1)
        out_row.addWidget(out_btn)
        fl.addRow("Output Folder:", out_row)
        
        # Scan options
        self.recursive_chk = QCheckBox("Recursive Scan")
        self.recursive_chk.setChecked(self.config.recursive_scan)
        self.recursive_chk.toggled.connect(self._on_global_changed)
        fl.addRow(self.recursive_chk)
        
        self.scan_depth_sp = QSpinBox()
        self.scan_depth_sp.setRange(1, 20)
        self.scan_depth_sp.setValue(self.config.scan_depth)
        self.scan_depth_sp.valueChanged.connect(self._on_global_changed)
        fl.addRow("Max Scan Depth:", self.scan_depth_sp)
        
        self.input_dir_edit.textChanged.connect(self._on_global_changed)
        self.output_dir_edit.textChanged.connect(self._on_global_changed)
        return tab

    def _browse_input_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Input Directory",
                                             self.input_dir_edit.text() or str(CWD))
        if d:
            self.input_dir_edit.setText(d)

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory",
                                             self.output_dir_edit.text() or str(CWD))
        if d:
            self.output_dir_edit.setText(d)

    def _on_global_changed(self, *args):
        """Updates StudioConfig and triggers auto-save when global settings change."""
        self.config.input_dir = self.input_dir_edit.text()
        self.config.output_dir = self.output_dir_edit.text()
        self.config.recursive_scan = self.recursive_chk.isChecked()
        self.config.scan_depth = self.scan_depth_sp.value()
        
        # Update File Panel scan options dynamically
        if hasattr(self, "file_panel"):
            self.file_panel.set_scan_options(
                recursive=self.config.recursive_scan,
                max_depth=self.config.scan_depth,
                extensions=SUPPORTED_EXTENSIONS,
            )
        # Trigger auto-save (debounced)
        self._save_timer.start()

    def _auto_scan_input_dir(self):
        """Automatically scans the configured input directory on launch."""
        in_dir = Path(self.config.input_dir)
        if in_dir.exists() and in_dir.is_dir():
            self.statusBar().showMessage(f"Auto-scanning input folder: {in_dir}...", 3000)
            # Trigger the background scan without opening a dialog
            self.file_panel._scan_directory(str(in_dir))

    def _on_file_selection(self):
        paths = self.file_panel.checked_paths()
        if self.FILE_PANEL_STRICT_ORDER:
            paths = paths[:2]
        if paths:
            self._items = [FileItem(path=p, checked=True) for p in paths]
            self.config.use_custom = False
            head = paths[0]
            if not self.config.recent_files or \
                    self.config.recent_files[0] != head:
                self._remember_recent(head)
        self._debounce_timer.start()

    def _build_preview_panel(self):
        self.preview_panel = QWidget()
        self.preview_panel.setAcceptDrops(True)
        lay = QVBoxLayout(self.preview_panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        toolbar = QHBoxLayout()
        self.preview_info = QLabel("Ready.")
        self.preview_info.setStyleSheet(f"color: {CAT['subtext']}; "
                                        f"font-size: 11px;")
        toolbar.addWidget(self.preview_info)
        toolbar.addStretch()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedHeight(26)
        self.play_btn.clicked.connect(self.toggle_playback)
        toolbar.addWidget(self.play_btn)
        self.loop_chk = QCheckBox("Loop")
        toolbar.addWidget(self.loop_chk)
        self.quality_cb = QComboBox()
        self.quality_cb.addItems(["Fast (½ res)", "Balanced (¾)", "Full"])
        self.quality_cb.currentIndexChanged.connect(self._on_quality)
        toolbar.addWidget(self.quality_cb)
        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.clicked.connect(self.refresh_preview)
        toolbar.addWidget(refresh_btn)
        lay.addLayout(toolbar)
        scrub_row = QHBoxLayout()
        self.scrub_slider = QSlider(Qt.Orientation.Horizontal)
        self.scrub_slider.setRange(0, 100)
        self.scrub_slider.setValue(20)
        self.scrub_lbl = QLabel("20%")
        self.scrub_lbl.setStyleSheet(f"color: {CAT['subtext']}; "
                                     f"font-size: 11px; min-width: 100px;")
        scrub_row.addWidget(QLabel("⏱"))
        scrub_row.addWidget(self.scrub_slider, 1)
        scrub_row.addWidget(self.scrub_lbl)
        lay.addLayout(scrub_row)
        self.scrub_slider.valueChanged.connect(self._on_scrub)
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet(
            f"QFrame {{ background: {CAT['crust']}; border: 1px solid "
            f"{CAT['surface1']}; border-radius: 8px; }}")
        self.preview_frame.setMinimumSize(480, 270)
        self.preview_label = QLabel("Rendering preview…")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(f"color: {CAT['subtext']}; "
                                         f"font-size: 13px; border: none;")
        pl = QVBoxLayout(self.preview_frame)
        pl.setContentsMargins(1, 1, 1, 1)
        pl.addWidget(self.preview_label)
        lay.addWidget(self.preview_frame, 1)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.setSizes([380, 1020])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        sc = QShortcut(QKeySequence("Space"), self.preview_panel,
                       activated=self.toggle_playback)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def _build_bottom_bar(self):
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"QWidget {{ background: {CAT['mantle']}; "
                          f"border-top: 1px solid {CAT['crust']}; }}")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 8, 12, 8)
        progress_box = QVBoxLayout()
        progress_box.setContentsMargins(0, 0, 0, 0)
        progress_box.setSpacing(2)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setFormat("%p%")
        progress_box.addWidget(self.progress_bar)
        self.progress_detail = QLabel("")
        self.progress_detail.setStyleSheet(f"color: {CAT['subtext']}; "
                                           f"font-size: 10px;")
        self.progress_detail.setVisible(False)
        self.progress_detail.setMinimumWidth(380)
        progress_box.addWidget(self.progress_detail)
        lay.addLayout(progress_box)
        self.export_btn = QPushButton("🎬  Export")
        self.export_btn.setObjectName("primary")
        self.export_btn.clicked.connect(self._start_export)
        lay.addWidget(self.export_btn)
        self.cancel_btn = QPushButton("✖")
        self.cancel_btn.setFixedWidth(36)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_export)
        lay.addWidget(self.cancel_btn)
        lay.addStretch()
        return bar

    def _install_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self._start_export)
        QShortcut(QKeySequence("Ctrl+R"), self,
                  activated=self.refresh_preview)
        QShortcut(QKeySequence("Ctrl+S"), self,
                  activated=self._save_settings_now)
        QShortcut(QKeySequence("Ctrl+O"), self,
                  activated=lambda: self.file_panel._add_files()
                  if hasattr(self, "file_panel") else None)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)
        QShortcut(QKeySequence("Esc"), self, activated=self._cancel_export)

    def dragEnterEvent(self, e):
        urls = e.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() \
                in SUPPORTED_EXTENSIONS:
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls()
                 if Path(u.toLocalFile()).suffix.lower()
                 in SUPPORTED_EXTENSIONS]
        if not paths:
            return
        if hasattr(self, "file_panel"):
            existing = {p: (self.file_panel.list_widget.item(i).checkState()
                            == Qt.CheckState.Checked)
                        for i, p in enumerate(self.file_panel.paths())}
            for p in paths:
                existing.setdefault(p, True)
            self.file_panel.set_paths(list(existing.keys()),
                                      states=existing)
        else:
            known = {it.path for it in self._items}
            for p in paths:
                if p not in known:
                    self._items.append(FileItem(path=p, checked=True))
            if hasattr(self, "_refresh_table"):
                self._refresh_table()
        self.config.use_custom = False
        self._remember_recent(paths[0])
        self._debounce_timer.start()

    def _show_preview_frame(self, img: QImage):
        self.preview_label.setPixmap(QPixmap.fromImage(img).scaled(
            self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.preview_info.setText(
            f"{img.width()}×{img.height()} · {self.config.resolution}")

    def _on_preview_failed(self, msg: str):
        self.preview_label.setText(
            f"⚠ Preview error:\n{msg}\n\nPress Ctrl+R to retry.")
        self.preview_info.setText("Preview failed — see studio.log")
        self.log.error("preview_failed: %s", msg)

    def _start_export(self):
        if not self._items and not self.config.use_custom:
            self.statusBar().showMessage(
                "Nothing to export — add a file or enable Custom Code.",
                5000)
            return
        log_mode_event(self.log, "export_start",
                       items=len(self._items), custom=self.config.use_custom,
                       mode=self.config.mode.name)
        self.export_manager.start(self._items)

    def _cancel_export(self):
        self.export_manager.cancel()

    def _load_path(self, path):
        self._items.clear()
        self._items.append(FileItem(path=path, checked=True))
        self.config.use_custom = False
        if hasattr(self, "file_panel"):
            self.file_panel.blockSignals(True)
            self.file_panel.set_paths([path])
            self.file_panel.blockSignals(False)
        self.statusBar().showMessage(f"Loaded {Path(path).name}", 4000)
        self._debounce_timer.start()

    def _remember_recent(self, path):
        rf = self.config.recent_files
        if path in rf:
            rf.remove(path)
        rf.insert(0, path)
        del rf[8:]
        if hasattr(self, "recent_btn"):
            old = self.recent_btn.menu()
            self.recent_btn.setMenu(self._build_recent_menu())
            if old is not None:
                old.deleteLater()

    def _build_recent_menu(self):
        m = QMenu(self)
        for pth in self.config.recent_files[:8]:
            if Path(pth).exists():
                m.addAction(Path(pth).name,
                            lambda checked=False, p=pth: self._load_path(p))
        if not m.actions():
            m.addAction("(empty)").setEnabled(False)
        return m

    def _load_demo_content(self):
        # Don't load dummy demo files if the user has a real input directory configured
        if Path(self.config.input_dir).exists() and Path(self.config.input_dir).is_dir():
            return 
            
        path, fallback = self.demo_content()
        p = Path(path) if path else None
        if p and p.exists():
            self._items.append(FileItem(path=str(p), checked=True))
        else:
            content = self.DEMO_FILES.get(path or "", fallback)
            demo_path = TEMP_DIR / (path or "demo_code.py")
            try:
                demo_path.parent.mkdir(parents=True, exist_ok=True)
                demo_path.write_text(content, encoding="utf-8")
                self._items.append(FileItem(path=str(demo_path),
                                            checked=True))
            except OSError:
                self.config.use_custom = True
                self.config.custom_code = fallback
        if hasattr(self, "file_panel"):
            self.file_panel.blockSignals(True)
            self.file_panel.set_paths([it.path for it in self._items])
            self.file_panel.blockSignals(False)

    def _save_settings_now(self):
        self.config.save(self.SETTINGS_PATH)
        self.statusBar().showMessage(
            f"Settings saved ({Path(self.SETTINGS_PATH).name})", 3000)

    def _on_settings_tab_changed(self, idx):
        if self._loading:
            return
        # Tab 0 = Global; Tab 1 = Files; mode settings tabs start at index 2
        mode_idx = idx - 2
        modes = list(self.STRATEGIES.keys())
        if 0 <= mode_idx < len(modes):
            self.config.mode = modes[mode_idx]
        self._debounce_timer.start()

    def _apply_target_duration(self, secs):
        idx = self.settings_tabs.currentIndex()
        if 1 < idx <= len(self.tabs) + 1:
            current = self.tabs[idx - 2]
            if hasattr(current, "apply_target_duration"):
                current.apply_target_duration(secs)
                self.statusBar().showMessage(
                    f"Adjusted WPM to hit ~{secs}s", 3000)

    def _play_buffer(self, data: bytes):
        if not hasattr(self, "_audio_player"):
            self._audio_out = QAudioOutput()
            self._audio_player = QMediaPlayer()
            self._audio_player.setAudioOutput(self._audio_out)
        self._audio_buf = QBuffer()
        self._audio_buf.setData(data)
        self._audio_buf.open(QIODevice.OpenModeFlag.ReadOnly)
        self._audio_player.setSourceDevice(self._audio_buf, QUrl())
        self._audio_out.setVolume(1.0)
        self._audio_player.play()

    def _restore_geometry(self):
        if self.config.win_geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(
                    self.config.win_geometry.encode()))
                self.splitter.restoreState(QByteArray.fromBase64(
                    self.config.win_state.encode()))
            except Exception:
                pass

    def closeEvent(self, event):
        em = self.export_manager
        if em.state.busy:
            em.cancel()
            em.stop_thread()
        if self._preview_fsm.state is PreviewState.PLAYING:
            self._play_timer.stop()
        self._stop_preview_audio()
        self.config.win_geometry = bytes(
            self.saveGeometry().toBase64()).decode()
        self.config.win_state = bytes(
            self.splitter.saveState().toBase64()).decode()
        self.config.save(self.SETTINGS_PATH)
        log_mode_event(self.log, "session_end")
        for h in self.log.logger.handlers:
            try:
                h.flush()
            except Exception:
                pass
        self.preview_worker.stop()
        super().closeEvent(event)


def run_studio(window_cls):
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    apply_theme(app)
    logger.info("=== launch: %s | ffmpeg=%s pygments=%s | python %s ===",
                window_cls.__name__, HAS_FFMPEG, _HAS_PYGMENTS,
                sys.version.split()[0])
    window = window_cls()
    window.show()
    sys.exit(app.exec())


# ═════════════════════════════════════════════════════════════════════════════
# §9  BASE MODE TAB
# ═════════════════════════════════════════════════════════════════════════════
class BaseModeTab(QWidget):
    """Declarative wiring: WIRING = [(widget_attr, config_key, kind), ...],
    kind ∈ {spin, dspin, check, combo, combo_data, text}. Subclasses set
    MODE, WPM_SPINBOX_ATTR, SHORTS_CHECK_ATTR."""
    TAB_LABEL = ""
    WIRING: list = []
    WPM_SPINBOX_ATTR = ""
    SHORTS_CHECK_ATTR = ""
    MODE = None

    _SIGNAL = {"spin": "valueChanged", "dspin": "valueChanged",
               "check": "toggled", "combo": "currentTextChanged",
               "combo_data": "currentIndexChanged",
               "text": "textChanged"}

    def __init__(self, main_window, mode=None):
        super().__init__()
        self.mw = main_window
        self.mode = mode if mode is not None else self.MODE
        if self.mode is None:
            raise TypeError(
                f"{type(self).__name__} must define MODE (StudioMode) "
                f"or be constructed with an explicit mode")
        self._form = None
        self._extra_widgets = []
        self._qt_pending: Optional[int] = None
        self.build_ui()

    def wire(self):
        u = self.update_config
        for attr, key, kind in self.WIRING:
            widget = getattr(self.mw, attr)
            sig = getattr(widget, self._SIGNAL[kind])
            if kind == "text":
                sig.connect(lambda key=key, w=widget: u(key,
                                                        w.toPlainText()))
            elif kind == "combo_data":
                sig.connect(lambda idx, key=key, w=widget: u(
                    key, w.itemData(idx)))
            else:
                sig.connect(lambda v, key=key: u(key, v))
        self._wiring_done = True
        if self.SHORTS_CHECK_ATTR:
            getattr(self.mw, self.SHORTS_CHECK_ATTR).toggled.connect(
                self._refresh_estimate)

    def load(self, config):
        for attr, key, kind in self.WIRING:
            widget = getattr(self.mw, attr)
            val = getattr(config, key)
            if kind in ("spin", "dspin"):
                widget.setValue(val)
            elif kind == "check":
                widget.setChecked(val)
            elif kind == "combo":
                widget.setCurrentText(val)
            elif kind == "combo_data":
                idx = widget.findData(val)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif kind == "text":
                widget.setPlainText(val)

    def update_config(self, key, value):
        setattr(self.mw.config, key, value)
        self.mw._debounce_timer.start()
        self.mw._save_timer.start()

    def load_settings(self, config):
        self.load(config)

    # ── WPM spinbox factory — derives range from the solver ────────────
    @staticmethod
    def create_wpm_spinbox(default: int = 100) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(TypingAnimator._WPM_MIN, TypingAnimator._WPM_MAX)
        sp.setValue(default)
        return sp

    # ── Quick Target (presets + custom seconds + slider) ───────────────
    def add_quick_target(self, form_layout: QFormLayout):
        """Auto Adjust Preset: preset buttons + custom seconds + slider +
        auto-adjust toggle. The slider/spinbox auto-applies via a 350ms
        debounce; no explicit Apply button needed."""
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        # Preset buttons
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        for label, secs in [("30s", 30), ("1m", 60), ("2m", 120),
                            ("3m", 180), ("⚡Shorts", 179)]:
            btn = QPushButton(label)
            btn.setFixedHeight(24)
            btn.setToolTip(f"Solve WPM for ~{secs}s target")
            btn.clicked.connect(
                lambda checked=False, s=secs: self._apply_quick_target(s))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        cl.addLayout(preset_row)

        # Custom seconds spinbox + slider (auto-applies via debounce)
        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setSpacing(6)
        self._qt_spin = QSpinBox()
        self._qt_spin.setRange(5, 3600)
        self._qt_spin.setValue(60)
        self._qt_spin.setSuffix("s")
        self._qt_spin.setFixedWidth(80)
        slider_row.addWidget(self._qt_spin)
        self._qt_slider = QSlider(Qt.Orientation.Horizontal)
        self._qt_slider.setRange(5, 600)
        self._qt_slider.setValue(60)
        slider_row.addWidget(self._qt_slider, 1)
        cl.addLayout(slider_row)

        # ── Auto-adjust toggle ──
        if self.SHORTS_CHECK_ATTR:
            shorts_row = QHBoxLayout()
            shorts_row.setContentsMargins(0, 0, 0, 0)
            shorts_chk = QCheckBox("Auto-adjust to preset")
            shorts_chk.setToolTip(
                "Caps effective WPM so the video fits within the "
                "preset duration (YouTube Shorts limit).")
            shorts_row.addWidget(shorts_chk)
            shorts_row.addStretch()
            cl.addLayout(shorts_row)
            setattr(self.mw, self.SHORTS_CHECK_ATTR, shorts_chk)

        form_layout.addRow("Auto Adjust Preset:", container)

        # Wiring: slider↔spin sync + debounced auto-apply
        self._qt_timer = QTimer(self)
        self._qt_timer.setSingleShot(True)
        self._qt_timer.setInterval(350)
        self._qt_timer.timeout.connect(self._qt_apply_debounced)

        self._qt_spin.valueChanged.connect(self._on_qt_spin_changed)
        self._qt_slider.valueChanged.connect(self._on_qt_slider_changed)

    def _on_qt_spin_changed(self, v: int):
        if not self._qt_slider.isSliderDown():
            self._qt_slider.blockSignals(True)
            self._qt_slider.setValue(min(v, self._qt_slider.maximum()))
            self._qt_slider.blockSignals(False)
        self._qt_pending = v
        self._qt_timer.start()

    def _on_qt_slider_changed(self, v: int):
        if not self._qt_spin.hasFocus():
            self._qt_spin.blockSignals(True)
            self._qt_spin.setValue(v)
            self._qt_spin.blockSignals(False)
        self._qt_pending = v
        self._qt_timer.start()

    def _qt_apply_debounced(self):
        if self._qt_pending is not None:
            self._apply_quick_target(self._qt_pending)

    def _apply_quick_target(self, secs: int):
        try:
            self.apply_target_duration(secs)
        except Exception:
            pass
        self._refresh_estimate()

    # ── BGM controls (procedural + file-based) ──────────────────────────
    def add_bgm_controls(self, form_layout: QFormLayout):
        """Background music: procedural soundscapes + files from music/.
        Dropdown shows both with icons; volume slider with live label."""
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        # Row 1: enable + dropdown + 3 action buttons
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(4)
        self.mw.bgm_chk = QCheckBox("On")
        self.mw.bgm_chk.setToolTip(
            "Ambient soundscape or music file under the typing SFX.")
        row1.addWidget(self.mw.bgm_chk)
        self.mw.bgm_cb = QComboBox()
        self.mw.bgm_cb.setMinimumWidth(180)
        row1.addWidget(self.mw.bgm_cb, 1)
        for icon, tip, slot in [
            ("📁", "Browse for an audio file…", self._browse_bgm_file),
            ("📂", "Open the music/ folder", self._open_music_folder),
            ("⟳",  "Re-scan music/ folder",    self._rescan_bgm)]:
            btn = QPushButton(icon)
            btn.setFixedSize(28, 28)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            row1.addWidget(btn)
        cl.addLayout(row1)

        # Row 2: volume slider with live percentage label
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)
        row2.addWidget(QLabel("Vol"))
        self.mw.bgm_vol_sp = QSlider(Qt.Orientation.Horizontal)
        self.mw.bgm_vol_sp.setRange(0, 100)
        self.mw.bgm_vol_sp.setValue(30)
        self.mw.bgm_vol_lbl = QLabel("30%")
        self.mw.bgm_vol_lbl.setFixedWidth(34)
        self.mw.bgm_vol_lbl.setStyleSheet(
            f"color: {CAT['subtext']}; font-size: 10px;")
        self.mw.bgm_vol_sp.valueChanged.connect(
            lambda v: self.mw.bgm_vol_lbl.setText(f"{v}%"))
        row2.addWidget(self.mw.bgm_vol_sp, 1)
        row2.addWidget(self.mw.bgm_vol_lbl)
        cl.addLayout(row2)

        form_layout.addRow("BGM:", container)

        # Populate the combo (procedural + files)
        self._populate_bgm_combo()

    def _populate_bgm_combo(self):
        """Fill the BGM dropdown: procedural types, separator, then files
        from music/ (scanned recursively via scan_directory_tree)."""
        cb = self.mw.bgm_cb
        cb.blockSignals(True)
        saved = cb.currentData()
        cb.clear()
        for s in SOUNDSCAPE_TYPES:
            icon = SOUNDSCAPE_ICONS.get(s, "🎵")
            cb.addItem(f"{icon}  {s}", s)
        files = scan_music_folder()
        if files:
            cb.insertSeparator(cb.count())
            for display, rel_path in files:
                cb.addItem(f"🎵  {display}", rel_path)
        if saved:
            idx = cb.findData(saved)
            if idx >= 0:
                cb.setCurrentIndex(idx)
        cb.blockSignals(False)

    def _browse_bgm_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self.mw, "Select Audio File", str(MUSIC_DIR),
            "Audio (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.opus "
            "*.wma *.aiff *.aif *.au *.snd);;All Files (*)")
        if not path:
            return
        src = Path(path)
        if MUSIC_DIR not in src.parents:
            dst = MUSIC_DIR / src.name
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
        rel = str((MUSIC_DIR / src.name).relative_to(CWD))
        self.update_config("bgm_source", rel)
        self._populate_bgm_combo()
        idx = self.mw.bgm_cb.findData(rel)
        if idx >= 0:
            self.mw.bgm_cb.setCurrentIndex(idx)
        self.mw.statusBar().showMessage(
            f"Added {src.name} to music/", 4000)

    def _open_music_folder(self):
        folder = str(MUSIC_DIR)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    def _rescan_bgm(self):
        self._populate_bgm_combo()
        n = len(scan_music_folder())
        self.mw.statusBar().showMessage(
            f"Music folder scanned — {n} file(s)", 4000)

    # ── Typing volume slider ────────────────────────────────────────────
    def add_typing_volume_slider(self, form_layout: QFormLayout):
        """Typing-SFX volume slider. Independent of the BGM volume slider
        added by `add_bgm_controls`. Wire it by including
            ("vol_sp", "volume", "spin")
        in the subclass's WIRING list."""
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addWidget(QLabel("Vol"))
        self.mw.vol_sp = QSlider(Qt.Orientation.Horizontal)
        self.mw.vol_sp.setRange(0, 100)
        self.mw.vol_sp.setValue(self.mw.config.volume)
        self.mw.vol_lbl = QLabel(f"{self.mw.config.volume}%")
        self.mw.vol_lbl.setFixedWidth(34)
        self.mw.vol_lbl.setStyleSheet(
            f"color: {CAT['subtext']}; font-size: 10px;")
        self.mw.vol_sp.valueChanged.connect(
            lambda v: self.mw.vol_lbl.setText(f"{v}%"))
        rl.addWidget(self.mw.vol_sp, 1)
        rl.addWidget(self.mw.vol_lbl)
        form_layout.addRow("Typing Vol:", row)

    # ── live duration estimate (effective WPM incl. Shorts cap) ─────────
    def attach_duration_label(self, wpm_attr: str, row_layout: QHBoxLayout):
        self._dur_lbl = QLabel("≈ 0s")
        self._dur_lbl.setStyleSheet(
            f"color: {CAT['subtext']}; font-size: 11px; "
            f"font-family: monospace;")
        self._dur_wpm_attr = wpm_attr
        row_layout.addWidget(self._dur_lbl)
        self._est_timer = QTimer(self)
        self._est_timer.setSingleShot(True)
        self._est_timer.setInterval(300)
        self._est_timer.timeout.connect(self._compute_estimate)
        getattr(self.mw, wpm_attr).valueChanged.connect(
            lambda *_: self._est_timer.start())

    def _refresh_estimate(self, *_, **__):
        if hasattr(self, "_est_timer"):
            self._est_timer.start()
        else:
            self._compute_estimate()

    def _compute_estimate(self):
        if not hasattr(self, "_dur_lbl"):
            return
        try:
            strategy = self.mw.strategies[self.mode]
            code, _, _ = strategy._get_code(
                self.mw.config, self.mw._items, self.mw.config.custom_code)
            is_text = (self.mode == StudioMode.TEXT_EMOJI)
            user_wpm = getattr(self.mw, self._dur_wpm_attr).value()
            shorts_on = False
            if self.SHORTS_CHECK_ATTR and hasattr(self.mw,
                                                self.SHORTS_CHECK_ATTR):
                shorts_on = getattr(self.mw,
                                    self.SHORTS_CHECK_ATTR).isChecked()
            eff = strategy._shorts_capped_wpm(code, user_wpm, shorts_on,
                                            is_text=is_text)
            d = estimate_duration_cached(code, eff, OVERHEAD_MIN,
                                        OVERHEAD_MAX, is_text=is_text)
            capped = (eff != user_wpm)
            self._dur_lbl.setText(
                f"≈ {format_duration(d)}" + ("  ⚡Shorts" if capped else ""))
        except Exception:
            pass

    def _solve_with_cursor(self, fn):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            return fn()
        finally:
            QApplication.restoreOverrideCursor()

    def apply_target_duration(self, secs):
        def solve():
            strategy = self.mw.strategies[self.mode]
            code, _, _ = strategy._get_code(
                self.mw.config, self.mw._items, self.mw.config.custom_code)
            is_text = (self.mode == StudioMode.TEXT_EMOJI)
            wpm = find_wpm_cached(code, secs, OVERHEAD_MIN, OVERHEAD_MAX,
                                  is_text=is_text)
            if self.WPM_SPINBOX_ATTR:
                getattr(self.mw, self.WPM_SPINBOX_ATTR).setValue(wpm)
            actual = estimate_duration_cached(code, wpm, OVERHEAD_MIN,
                                              OVERHEAD_MAX, is_text=is_text)
            if wpm in (TypingAnimator._WPM_MIN, TypingAnimator._WPM_MAX):
                self.mw.statusBar().showMessage(
                    f"Target {secs}s unreachable in "
                    f"{TypingAnimator._WPM_MIN}–{TypingAnimator._WPM_MAX} "
                    f"WPM — closest ≈{format_duration(actual)} at {wpm} "
                    f"WPM", 6000)
            else:
                self.mw.statusBar().showMessage(
                    f"WPM set to {wpm} → ≈{format_duration(actual)} "
                    f"(target {secs}s)", 4000)
        self._solve_with_cursor(solve)

    # ── form helpers ─────────────────────────────────────────────────────
    def add_settings_group(self, title: str) -> QFormLayout:
        grp = QGroupBox(title)
        self._form_host = grp
        self._form = QFormLayout(grp)
        self._form.setSpacing(6)
        self._form.setFormAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(grp)
        outer.addStretch()
        return self._form

    def add_custom_widget(self, widget):
        self._extra_widgets.append(widget)

    def finalize_layout(self):
        lay = self.layout()
        if lay is None:
            return
        anchor = lay.count() - 1 if lay.count() else None
        for w in reversed(self._extra_widgets):
            if anchor is not None:
                lay.insertWidget(anchor, w)
        self._extra_widgets.clear()

    def build_ui(self):
        raise NotImplementedError


def create_font_controls(prefix: str, main_window):
    cb = QComboBox()
    cb.addItems(get_font_families())
    row = QWidget()
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(6)
    auto = QCheckBox("Auto")
    auto.setToolTip("Derive size from video resolution.")
    sp = QSpinBox()
    sp.setRange(8, 72)
    sp.setValue(22)
    rl.addWidget(auto)
    rl.addWidget(sp)
    rl.addStretch()
    setattr(main_window, f"{prefix}_font_cb", cb)
    setattr(main_window, f"{prefix}_font_sz_auto", auto)
    setattr(main_window, f"{prefix}_font_sz_sp", sp)
    return cb, row


def create_font_group(prefix: str, label: str, main_window) -> QGroupBox:
    grp = QGroupBox(label)
    fl = QFormLayout(grp)
    cb, row = create_font_controls(prefix, main_window)
    fl.addRow("Font:", cb)
    fl.addRow("Size:", row)
    return grp


if __name__ == "__main__":
    print("studio_lib is a library. Launch a mode, e.g.:  python studio.py")