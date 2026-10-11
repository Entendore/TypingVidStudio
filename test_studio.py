#!/usr/bin/env python3
"""
Unit tests: engine, modes, audio, keyboard, renderer, config, FSMs,
registry, estimates. No windows except where tab wiring is under test.

Run:  QT_QPA_PLATFORM=offscreen pytest test_studio.py -v --timeout=60
"""
import json
import os
import shutil
import sys
from dataclasses import fields
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

from conftest import (BASE_CODE, LONG_CODE, DEMO_JR, DEMO_SR, wait_for)

from studio_lib import (
    StudioConfig, StudioMode, FileItem, TypingProfile, TypingAnimator,
    StudioRenderer, MultiPaneRenderer, KeyboardOverlay, SimpleSoundGen,
    SoundscapeGenerator, ExportManager, StateMachine, ExportState,
    PreviewState, InvalidStateTransition, _EXPORT_FSM, _PREVIEW_FSM,
    THEMES, RESOLUTIONS, KEYBOARD_LAYOUTS, MODULAR_SOUND_PRESETS,
    MULTI_WINDOW_LAYOUTS, JR_VS_SR_LAYOUTS, SUPPORTED_EXTENSIONS,
    ENCODERS, ENCODER_ARGS, MODE_REGISTRY, SCAN_SKIP_DIRS,
    split_graphemes, convert_shortcodes, read_text_file, detect_language,
    find_wpm_cached, estimate_duration_cached, is_emoji, format_duration,
    _text_key, _SOLVER_CACHE, _EST_CACHE, _CLICK_BANK_CACHE,
    MAX_INPUT_CHARS, PAUSE_TOKEN, OVERHEAD_MIN, OVERHEAD_MAX,
    SHORTS_TARGET_SECS, FileSelectionPanel,
)


# ═════════════════════════════════════════════════════════════════════════════
# ENGINE UNITS
# ═════════════════════════════════════════════════════════════════════════════
class TestGraphemes:
    def test_ascii_fast_path(self):
        assert split_graphemes("abc") == ["a", "b", "c"]

    def test_skin_tone(self):
        assert split_graphemes("👍🏽") == ["👍🏽"]
        assert split_graphemes("👩🏽‍🚀") == ["👩🏽‍🚀"]

    def test_flags(self):
        assert split_graphemes("🇺🇸🇯🇵") == ["🇺🇸", "🇯🇵"]

    def test_zwj(self):
        assert split_graphemes("👨‍👩‍👧") == ["👨‍👩‍👧"]

    def test_vs16(self):
        assert split_graphemes("❤️") == ["❤️"]

    def test_mixed(self):
        assert split_graphemes("a🚀b") == ["a", "🚀", "b"]

    def test_empty(self):
        assert split_graphemes("") == []


class TestShortcodesAndLang:
    def test_shortcodes(self):
        assert convert_shortcodes("go :rocket: now") == "go 🚀 now"
        assert convert_shortcodes(":check::fire:") == "✅🔥"

    def test_plain_passthrough(self):
        assert convert_shortcodes("no codes") == "no codes"

    @pytest.mark.parametrize("fn,lang", [
        ("a.py", "python"), ("b.tsx", "typescript"), ("Dockerfile", "docker"),
        ("Makefile", "makefile"), ("e.unknown", "text")])
    def test_detect(self, fn, lang):
        assert detect_language(fn) == lang

    def test_skip_dirs_constant(self):
        assert "__pycache__" in SCAN_SKIP_DIRS
        assert ".git" in SCAN_SKIP_DIRS


class TestFileReading:
    def test_clean(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("a = 1   \n\t\nb = 2  \n")
        assert read_text_file(str(f)) == "a = 1\n\nb = 2"

    def test_nfo_preserved(self, tmp_path):
        f = tmp_path / "x.nfo"
        f.write_text("  ####  \n")
        assert read_text_file(str(f)) == "  ####  \n"

    def test_shortcode_in_file(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text(":rocket:")
        assert read_text_file(str(f)) == "🚀"


class TestMisc:
    def test_is_emoji_pinned(self):
        assert is_emoji("🚀") and is_emoji("❤️") and not is_emoji("a")

    def test_format_duration(self):
        assert format_duration(47) == "47s"
        assert format_duration(107) == "1m 47s"
        assert format_duration(3723) == "1h 02m 03s"

    def test_text_key_distinguishes_lengths(self):
        assert _text_key("ab") != _text_key("abc")


# ═════════════════════════════════════════════════════════════════════════════
# ANIMATION + SOLVER
# ═════════════════════════════════════════════════════════════════════════════
class TestAnimator:
    def test_duration_inversely_scales(self):
        d_slow = TypingAnimator(BASE_CODE, TypingProfile(wpm=30)).duration()
        d_fast = TypingAnimator(BASE_CODE, TypingProfile(wpm=300)).duration()
        assert d_slow > d_fast > 0

    def test_deterministic_seed(self):
        a1 = TypingAnimator(LONG_CODE, TypingProfile(wpm=100), seed=42)
        a2 = TypingAnimator(LONG_CODE, TypingProfile(wpm=100), seed=42)
        assert a1.char_timestamps() == a2.char_timestamps()

    def test_pause_tokens_add_time(self):
        with_p = TypingAnimator("a\x01\x01b", TypingProfile(wpm=100))
        without = TypingAnimator("ab", TypingProfile(wpm=100))
        assert with_p.duration() >= without.duration() + 0.9

    def test_text_visible_backspaces(self):
        a = TypingAnimator("abc\b\bX", TypingProfile(wpm=300))
        assert a.text_visible_at(a.duration()) == "aX"

    def test_text_visible_pauses(self):
        a = TypingAnimator("a\x01\x01b", TypingProfile(wpm=300))
        assert a.text_visible_at(a.duration()) == "ab"

    def test_replay_matches_naive(self):
        a = TypingAnimator("abc\b\bX\ndef\b", TypingProfile(wpm=300))
        buf = []
        cutoff = a.duration() * 0.7
        for ts, ch in a.timeline:
            if ts > cutoff:
                break
            if ch == '\b' and buf:
                buf.pop()
            elif ch != '\x01':
                buf.append(ch)
        assert a.text_visible_at(cutoff) == "".join(buf)

    def test_replay_skippable(self):
        a = TypingAnimator(BASE_CODE, TypingProfile(wpm=100),
                           build_replay=False)
        assert a._replay == []
        b = TypingAnimator(BASE_CODE, TypingProfile(wpm=100))
        assert abs(a.duration() - b.duration()) < 1e-9

    def test_grapheme_text_mode(self):
        a = TypingAnimator("👍🏽🇺🇸x", TypingProfile(wpm=100, is_text=True))
        chars = [c for _, c in a.char_timestamps()
                 if c not in ('\b', '\x01')]
        assert "👍🏽" in chars and "🇺🇸" in chars


class TestCursor:
    def test_cursor_tracks_typing(self):
        a = TypingAnimator("ab\ncd", TypingProfile(wpm=300))
        idx_nl = next(i for i, (_, c) in enumerate(a.char_timestamps())
                      if c == "\n")
        t_after = a.char_timestamps()[idx_nl][0] + 0.01
        assert a.cursor_at(t_after) == (1, 0)
        assert a.cursor_at(a.duration()) == (1, 2)

    def test_cursor_back_on_backspace(self):
        a = TypingAnimator("abc\b\bX", TypingProfile(wpm=300))
        assert a.cursor_at(a.duration()) == (0, 2)

    def test_cursor_at_start(self):
        a = TypingAnimator("xyz", TypingProfile(wpm=300))
        assert a.cursor_at(0.0) == (0, 0)

    def test_per_pane_independent(self):
        short = TypingAnimator("x = 1\n", TypingProfile(wpm=100))
        long_ = TypingAnimator(LONG_CODE, TypingProfile(wpm=100))
        mid_t = short.duration() * 0.9
        assert short.cursor_at(mid_t) != long_.cursor_at(mid_t)


class TestWPMSolver:
    @pytest.mark.parametrize("target", [30, 60, 120, 300])
    def test_exact_hits_target(self, target):
        wpm = TypingAnimator.find_wpm_for_target(
            LONG_CODE, target, OVERHEAD_MIN, OVERHEAD_MAX)
        actual = TypingAnimator.estimate_duration(
            LONG_CODE, wpm, OVERHEAD_MIN, OVERHEAD_MAX)
        assert abs(actual - target) <= max(1.0, target * 0.02)

    def test_punctuated_text(self):
        code = "Wait.\n" * 100
        wpm = TypingAnimator.find_wpm_for_target(
            code, 60, OVERHEAD_MIN, OVERHEAD_MAX)
        actual = TypingAnimator.estimate_duration(
            code, wpm, OVERHEAD_MIN, OVERHEAD_MAX)
        assert abs(actual - 60) <= 2.0

    def test_monotonic(self):
        wpms = [TypingAnimator.find_wpm_for_target(BASE_CODE, t, 0.5, 1.5)
                for t in (30, 60, 120, 240)]
        assert wpms == sorted(wpms, reverse=True)

    def test_clamps(self):
        assert TypingAnimator.find_wpm_for_target(
            "x" * 50000, 5, 0.5, 1.5) == 300
        assert TypingAnimator.find_wpm_for_target(
            "hi", 3600, 0.5, 1.5) == 30

    def test_pause_tokens_not_counted(self):
        assert TypingAnimator.find_wpm_for_target(
            "\x01" * 100, 60, 0.5, 1.5) == 30

    def test_refactor_string_priced(self, modes):
        s = modes.jr.JrVsSrStrategy()
        refactor = s.build_refactor_string(DEMO_JR, DEMO_SR)
        wpm = TypingAnimator.find_wpm_for_target(refactor, 60, 0.5, 1.5)
        actual = TypingAnimator.estimate_duration(refactor, wpm, 0.5, 1.5)
        assert abs(actual - 60) <= 2.0

    def test_solver_cache(self):
        a = find_wpm_cached(BASE_CODE, 60, 0.5, 1.5)
        assert a == find_wpm_cached(BASE_CODE, 60, 0.5, 1.5)
        assert len(_SOLVER_CACHE) >= 1

    def test_estimate_cache(self):
        a = estimate_duration_cached(BASE_CODE, 100)
        assert a == estimate_duration_cached(BASE_CODE, 100)
        assert len(_EST_CACHE) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG PERSISTENCE
# ═════════════════════════════════════════════════════════════════════════════
class TestConfig:
    def test_round_trip(self, tmp_path):
        p = tmp_path / "s.json"
        cfg = StudioConfig()
        cfg.wpm_yt = 222
        cfg.theme = "One Dark"
        cfg.mode = StudioMode.JR_VS_SR
        cfg.recent_files = ["/a.py", "/b.py"]
        cfg.show_cursor = False
        cfg.save(p)
        c2 = StudioConfig.load(p)
        assert c2.wpm_yt == 222 and c2.mode == StudioMode.JR_VS_SR
        assert c2.recent_files == ["/a.py", "/b.py"]
        assert c2.show_cursor is False

    def test_missing_file_defaults(self, tmp_path):
        assert StudioConfig.load(tmp_path / "nope.json") == StudioConfig()

    def test_corrupt_defaults(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text("{bad")
        assert StudioConfig.load(p).wpm_yt == 100

    def test_coercion(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"wpm_yt": "55", "yt_zoom": 1,
                                 "fps": 59.7}))
        cfg = StudioConfig.load(p)
        assert cfg.wpm_yt == 55 and cfg.yt_zoom is True and cfg.fps == 59

    def test_stale_keys_ignored(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"wpm_yt": 111, "ghost": 1,
                                 "typo_yt": 0.5,
                                 "preview_size": [10, 10]}))
        cfg = StudioConfig.load(p)
        assert cfg.wpm_yt == 111
        assert not hasattr(cfg, "ghost") and not hasattr(cfg, "typo_yt")
        assert cfg.preview_size is None

    def test_preview_fields_not_saved(self, tmp_path):
        p = tmp_path / "s.json"
        cfg = StudioConfig()
        cfg.preview_size = (480, 270)
        cfg.save(p)
        assert "preview_size" not in json.loads(p.read_text())

    def test_typo_fields_removed(self):
        cfg = StudioConfig()
        for legacy in ("typo_mw", "typo_jr", "typo_yt", "typo_txt"):
            assert not hasattr(cfg, legacy)
        assert not any(f.name == "typo_rate"
                       for f in fields(TypingProfile))


# ═════════════════════════════════════════════════════════════════════════════
# STATE MACHINES
# ═════════════════════════════════════════════════════════════════════════════
class TestExportFSM:
    def test_legal_happy_path(self):
        fsm = StateMachine("x", ExportState.IDLE, _EXPORT_FSM)
        fsm.transition(ExportState.STARTING)
        fsm.transition(ExportState.RUNNING)
        fsm.transition(ExportState.FINISHED)
        fsm.transition(ExportState.IDLE)
        assert fsm.state is ExportState.IDLE

    def test_illegal_reentry_raises(self):
        fsm = StateMachine("x", ExportState.IDLE, _EXPORT_FSM)
        fsm.transition(ExportState.STARTING)
        with pytest.raises(InvalidStateTransition):
            fsm.transition(ExportState.STARTING)

    def test_cancel_only_from_busy(self):
        fsm = StateMachine("x", ExportState.IDLE, _EXPORT_FSM)
        with pytest.raises(InvalidStateTransition):
            fsm.transition(ExportState.CANCELLING)

    def test_every_busy_state_reaches_terminal(self):
        for busy in (ExportState.STARTING, ExportState.RUNNING,
                     ExportState.CANCELLING):
            reachable = set(_EXPORT_FSM[busy])
            if ExportState.FINISHED in reachable:
                continue
            two_hop = set().union(
                *(_EXPORT_FSM.get(s, set()) for s in reachable))
            assert ExportState.FINISHED in reachable | two_hop, \
                f"{busy} cannot reach FINISHED"

    def test_only_starting_skips_finished(self):
        for state in ExportState:
            if state in (ExportState.IDLE, ExportState.STARTING,
                         ExportState.FINISHED):
                continue
            assert ExportState.IDLE not in _EXPORT_FSM.get(state, set()), \
                f"{state} → IDLE bypasses FINISHED accounting"

    def test_subscriber_notified(self):
        fsm = StateMachine("x", ExportState.IDLE, _EXPORT_FSM)
        seen = []
        fsm.subscribe(lambda o, n: seen.append((o, n)))
        fsm.transition(ExportState.STARTING)
        assert seen == [(ExportState.IDLE, ExportState.STARTING)]

    def test_subscriber_error_does_not_break_transition(self):
        fsm = StateMachine("x", ExportState.IDLE, _EXPORT_FSM)
        fsm.subscribe(lambda o, n: 1 / 0)
        fsm.transition(ExportState.STARTING)   # must not raise
        assert fsm.state is ExportState.STARTING


class TestPreviewFSM:
    def test_cycle(self):
        fsm = StateMachine("p", PreviewState.EMPTY, _PREVIEW_FSM)
        fsm.transition(PreviewState.READY)
        fsm.transition(PreviewState.PLAYING)
        fsm.transition(PreviewState.READY)
        fsm.transition(PreviewState.ERROR)
        fsm.transition(PreviewState.EMPTY)
        assert fsm.state is PreviewState.EMPTY


# ═════════════════════════════════════════════════════════════════════════════
# MODE SMOKE MATRIX
# ═════════════════════════════════════════════════════════════════════════════
ALL_MODES = None    # resolved lazily in fixture below (needs qapp first)


@pytest.fixture(scope="module")
def all_modes(qapp, modes):
    from studio_lib import StudioMode as SM
    return [
        (modes.code.CodeYTStrategy, SM.CODE_YT, "CODE_YT"),
        (modes.text.TextEmojiStrategy, SM.TEXT_EMOJI, "TEXT_EMOJI"),
        (modes.multi.MultiWindowStrategy, SM.MULTI_WINDOW, "MULTI_WINDOW"),
        (modes.jr.JrVsSrStrategy, SM.JR_VS_SR, "JR_VS_SR"),
    ]


def frame_ok(mpr, t=1.0):
    img = mpr.render_frame(t, scratch=False)
    assert img is not None and not img.isNull()
    return img


@pytest.mark.usefixtures("qapp")
class TestAllModesSmoke:
    def _cfg(self, mode, **over):
        cfg = StudioConfig()
        cfg.mode = mode
        cfg.use_custom = True
        cfg.custom_code = BASE_CODE
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    def test_build_and_render(self, all_modes):
        for cls, mode, _ in all_modes:
            mpr = cls().build_panes(self._cfg(mode), [], BASE_CODE)
            frame_ok(mpr, 0.5)
            frame_ok(mpr, mpr.duration() * 0.95)

    def test_file_path(self, all_modes, tmp_path):
        f = tmp_path / "s.py"
        f.write_text(BASE_CODE)
        for cls, mode, _ in all_modes:
            cfg = self._cfg(mode, use_custom=False)
            frame_ok(cls().build_panes(
                cfg, [FileItem(path=str(f), checked=True)], ""))

    def test_resolutions(self, all_modes):
        for cls, mode, _ in all_modes:
            for res, (w, h) in RESOLUTIONS.items():
                cfg = self._cfg(mode, resolution=res)
                img = frame_ok(cls().build_panes(cfg, [], BASE_CODE))
                assert (img.width(), img.height()) == (w, h), \
                    f"{mode.name} {res}"

    def test_themes(self, all_modes):
        for cls, mode, _ in all_modes:
            for theme in THEMES:
                frame_ok(cls().build_panes(self._cfg(mode, theme=theme),
                                           [], BASE_CODE))

    def test_unicode_and_empty(self, all_modes):
        for cls, mode, _ in all_modes:
            frame_ok(cls().build_panes(
                self._cfg(mode,
                          custom_code="s = 'héllo 👍🏽 🇺🇸 :rocket:'"),
                [], ""))
            frame_ok(cls().build_panes(self._cfg(mode, custom_code=""),
                                       [], ""))


# ═════════════════════════════════════════════════════════════════════════════
# MODE SPECIFICS
# ═════════════════════════════════════════════════════════════════════════════
class TestCodeYT:
    def test_shorts_caps(self):
        cfg = StudioConfig(use_custom=True, custom_code=LONG_CODE,
                           wpm_yt=30, shorts_yt=True)
        d = __import__("code_yt_mode").CodeYTStrategy().build_panes(
            cfg, [], LONG_CODE).duration()
        assert d <= SHORTS_TARGET_SECS + 10

    def test_zoom_first_frame_identity(self):
        cfg = StudioConfig(use_custom=True, custom_code=BASE_CODE,
                           preview_size=(480, 270))
        s = __import__("code_yt_mode").CodeYTStrategy()
        off = s.build_panes(cfg, [], BASE_CODE).render_frame(0.0,
                                                             scratch=False)
        cfg.yt_zoom = True
        on = s.build_panes(cfg, [], BASE_CODE).render_frame(0.0,
                                                            scratch=False)
        assert bytes(off.constBits()) == bytes(on.constBits())

    def test_zoom_changes_later_frames(self):
        cfg = StudioConfig(use_custom=True, custom_code=BASE_CODE,
                           preview_size=(480, 270))
        s = __import__("code_yt_mode").CodeYTStrategy()
        off = s.build_panes(cfg, [], BASE_CODE).render_frame(8.0,
                                                             scratch=False)
        cfg.yt_zoom = True
        on = s.build_panes(cfg, [], BASE_CODE).render_frame(8.0,
                                                            scratch=False)
        assert bytes(off.constBits()) != bytes(on.constBits())

    def test_cursor_visibility_changes_pixels(self):
        cfg = StudioConfig(use_custom=True, custom_code=BASE_CODE,
                           preview_size=(480, 270))
        s = __import__("code_yt_mode").CodeYTStrategy()
        # t inside blink-on phase:
        t = StudioRenderer.CURSOR_BLINK * 0.25 \
            if hasattr(StudioRenderer, "CURSOR_BLINK") else 0.13
        on = s.build_panes(cfg, [], BASE_CODE).render_frame(t,
                                                            scratch=False)
        cfg.show_cursor = False
        off = s.build_panes(cfg, [], BASE_CODE).render_frame(t,
                                                             scratch=False)
        assert bytes(on.constBits()) != bytes(off.constBits())


class TestTextEmoji:
    def _cfg(self, **over):
        cfg = StudioConfig(mode=StudioMode.TEXT_EMOJI, use_custom=True,
                           custom_code="**Hello** *world* 🚀\n`code` line")
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    def test_shorts_cap(self):
        s = __import__("text_emoji_mode").TextEmojiStrategy()
        d = s.build_panes(self._cfg(wpm_txt=30, shorts_txt=True), [],
                          "").duration()
        assert d <= SHORTS_TARGET_SECS + 10

    def test_shorts_respects_fast(self):
        s = __import__("text_emoji_mode").TextEmojiStrategy()
        d = s.build_panes(self._cfg(wpm_txt=300, shorts_txt=True), [],
                          "").duration()
        assert d < SHORTS_TARGET_SECS

    @pytest.mark.parametrize("flag", ["ascii_art", "txt_markdown",
                                      "txt_crt", "txt_bubbles"])
    def test_flags_change_pixels(self, flag):
        s = __import__("text_emoji_mode").TextEmojiStrategy()
        off = s.build_panes(self._cfg(), [], "").render_frame(2.0,
                                                              scratch=False)
        on = s.build_panes(self._cfg(**{flag: True}), [], "").render_frame(
            2.0, scratch=False)
        assert bytes(off.constBits()) != bytes(on.constBits()), flag

    def test_all_flags_combined(self):
        s = __import__("text_emoji_mode").TextEmojiStrategy()
        cfg = self._cfg(txt_markdown=True, txt_crt=True, txt_bubbles=True,
                        ascii_art=True)
        frame_ok(s.build_panes(cfg, [], ""), 1.0)

    def test_markdown_tokenizer(self):
        r = StudioRenderer(400, 300, is_text=True)
        segs = r._tokenize_markdown("**hi** there *pal* `x=1`")
        assert segs[0] == ("hi", "bold")
        assert ("pal", "italic") in segs and ("x=1", "code") in segs


class TestMultiWindow:
    def _cfg(self, **over):
        cfg = StudioConfig(mode=StudioMode.MULTI_WINDOW, use_custom=True,
                           custom_code=BASE_CODE)
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    @pytest.mark.parametrize("layout", list(MULTI_WINDOW_LAYOUTS.keys()))
    def test_every_layout(self, layout):
        s = __import__("multi_window_mode").MultiWindowStrategy()
        mpr = s.build_panes(self._cfg(layout_mw=layout), [], BASE_CODE)
        img = frame_ok(mpr, 1.0)
        assert img.width() == 1920 and img.height() == 1080

    def test_diff_with_two_files(self, tmp_path):
        a = tmp_path / "a.py"
        a.write_text(BASE_CODE)
        b = tmp_path / "b.py"
        b.write_text("def hello():\n    print('changed')\n")
        s = __import__("multi_window_mode").MultiWindowStrategy()
        cfg = self._cfg(layout_mw="2 Windows (Split)",
                        diff_highlight_mw=True, use_custom=False)
        frame_ok(s.build_panes(cfg, [FileItem(path=str(a), checked=True),
                                     FileItem(path=str(b), checked=True)],
                               ""))

    def test_sync_uniform_speed_and_staggered_start(self, tmp_path):
        p1 = tmp_path / "s.py"
        p1.write_text("x = 1\n")
        p2 = tmp_path / "l.py"
        p2.write_text(LONG_CODE)
        s = __import__("multi_window_mode").MultiWindowStrategy()
        cfg = self._cfg(use_custom=False, sync_mw=True)
        mpr = s.build_panes(cfg, [FileItem(path=str(p1), checked=True),
                                  FileItem(path=str(p2), checked=True)], "")
        wpms = {a.profile.wpm for _, a, _ in mpr.panes}
        assert len(wpms) == 1                      # uniform speed
        ends = [a.duration() for _, a, _ in mpr.panes]
        assert max(ends) - min(ends) < 0.5         # finish together
        starts = [a.timeline[0][0] for _, a, _ in mpr.panes]
        assert max(starts) - min(starts) > 0.5     # short pane starts later

    def test_shorts_mw(self):
        cfg = self._cfg(wpm_mw=30, shorts_mw=True)
        d = __import__("multi_window_mode").MultiWindowStrategy() \
            .build_panes(cfg, [], LONG_CODE).duration()
        assert d <= SHORTS_TARGET_SECS + 10

    def test_git_titles(self):
        mpr = __import__("multi_window_mode").MultiWindowStrategy() \
            .build_panes(self._cfg(layout_mw="Git Conflict (3-Pane)"), [],
                         BASE_CODE)
        titles = [t for _, _, t in mpr.panes]
        assert any("Base" in t for t in titles)
        assert any("Incoming" in t for t in titles)
        assert any("Resolved" in t for t in titles)


class TestJrVsSr:
    def _cfg(self, **over):
        cfg = StudioConfig(mode=StudioMode.JR_VS_SR,
                           jr_custom_code=DEMO_JR, sr_custom_code=DEMO_SR)
        for k, v in over.items():
            setattr(cfg, k, v)
        return cfg

    @pytest.mark.parametrize("layout", JR_VS_SR_LAYOUTS)
    def test_every_layout(self, layout):
        frame_ok(__import__("jr_vs_sr_mode").JrVsSrStrategy().build_panes(
            self._cfg(layout_jr=layout), [], ""), 1.0)

    def test_diff_mode(self):
        mpr = __import__("jr_vs_sr_mode").JrVsSrStrategy().build_panes(
            self._cfg(jr_diff_mode=True), [], "")
        frame_ok(mpr, mpr.duration() * 0.9)

    def test_refactor_string_structure(self):
        tl = __import__("jr_vs_sr_mode").JrVsSrStrategy() \
            .build_refactor_string(DEMO_JR, DEMO_SR)
        assert tl.startswith("def calc") and "\x01" in tl and "\b" in tl

    def test_json_source(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text(json.dumps({"title": "Factorial",
                                 "language": "python",
                                 "junior_code": DEMO_JR,
                                 "senior_code": DEMO_SR}))
        s = __import__("jr_vs_sr_mode").JrVsSrStrategy()
        code1, code2, lang, t1, _ = s.get_codes(
            self._cfg(use_custom=False),
            [FileItem(path=str(f), checked=True)], "")
        assert lang == "python" and code1 == DEMO_JR and "Junior" in t1

    def test_two_file_source(self, tmp_path):
        a = tmp_path / "j.py"
        a.write_text(DEMO_JR)
        b = tmp_path / "s.py"
        b.write_text(DEMO_SR)
        s = __import__("jr_vs_sr_mode").JrVsSrStrategy()
        code1, code2, _, t1, t2 = s.get_codes(
            self._cfg(use_custom=False),
            [FileItem(path=str(a), checked=True),
             FileItem(path=str(b), checked=True)], "")
        assert code1 == DEMO_JR and code2 == DEMO_SR
        assert t1 == "j.py" and t2 == "s.py"

    def test_json_corrupt_fallback(self, tmp_path):
        f = tmp_path / "p.json"
        f.write_text("{bad")
        s = __import__("jr_vs_sr_mode").JrVsSrStrategy()
        code1, _, _, _, _ = s.get_codes(
            self._cfg(use_custom=False),
            [FileItem(path=str(f), checked=True)], "")
        assert code1


# ═════════════════════════════════════════════════════════════════════════════
# AUDIO
# ═════════════════════════════════════════════════════════════════════════════
class TestAudio:
    TS = [(i * 0.08, ch) for i, ch in enumerate("hello world\n")]

    @pytest.mark.parametrize("preset", list(MODULAR_SOUND_PRESETS.keys()))
    def test_presets(self, preset):
        pcm = SimpleSoundGen(preset=preset).generate_pcm(self.TS, 0.5)
        assert len(pcm) > 0 and pcm.dtype.name == "int16"
        assert 0 < abs(pcm.max()) <= 32767

    @pytest.mark.parametrize("preset", list(MODULAR_SOUND_PRESETS.keys()))
    def test_stereo(self, preset):
        pcm = SimpleSoundGen(preset=preset, stereo=True).generate_pcm(
            self.TS, 0.5)
        assert len(pcm) % 2 == 0
        assert (pcm[0::2].astype(int) != pcm[1::2].astype(int)).any()

    def test_empty(self):
        assert len(SimpleSoundGen().generate_pcm([], 0.5)) == 0

    def test_bank_cache(self):
        SimpleSoundGen(preset="Mechanical")
        assert ("Mechanical", 48000) in _CLICK_BANK_CACHE

    @pytest.mark.parametrize("kind", ["Rain", "Wind", "Ocean", "Drone",
                                      "Forest"])
    def test_soundscapes(self, kind):
        assert len(SoundscapeGenerator().generate_pcm(1.0, kind)) == 48000

    def test_unknown_soundscape_silence(self):
        assert (SoundscapeGenerator().generate_pcm(0.5, "Nope") == 0).all()

    def test_tiny_duration(self):
        assert len(SoundscapeGenerator().generate_pcm(0.001, "Rain")) == 48


# ═════════════════════════════════════════════════════════════════════════════
# KEYBOARD OVERLAY
# ═════════════════════════════════════════════════════════════════════════════
class TestKeyboard:
    @pytest.mark.parametrize("layout", list(KEYBOARD_LAYOUTS.keys()))
    def test_layouts_build(self, layout):
        kb = KeyboardOverlay(1920, 1080, layout_name=layout)
        assert kb.key_rects and kb._kb_w > 0

    @pytest.mark.parametrize("pos", ["bottom_center", "bottom_right",
                                     "bottom_left", "top_center",
                                     "top_right", "top_left"])
    def test_positions(self, pos):
        kb = KeyboardOverlay(1920, 1080, position=pos)
        kb.reposition()
        assert 0 <= kb._kb_x <= 1920 and 0 <= kb._kb_y <= 1080

    def test_key_resolution(self):
        kb = KeyboardOverlay(1920, 1080)
        for ch in "abcXY019 .\n\t\b!@#":
            assert kb.resolve_key(ch) is not None, ch

    def test_draw(self):
        kb = KeyboardOverlay(1920, 1080)
        img = QImage(1920, 1080, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        kb.draw(p, active_key=kb.resolve_key('a'), flash=1.0)
        kb.draw(p, flash=0.0)
        p.end()


# ═════════════════════════════════════════════════════════════════════════════
# RENDERER
# ═════════════════════════════════════════════════════════════════════════════
class TestRenderer:
    @pytest.mark.parametrize("theme", list(THEMES.keys()))
    def test_theme_key_completeness(self, theme):
        required = {"background", "foreground", "comment", "keyword",
                    "string", "number", "function", "builtin", "decorator",
                    "operator", "class_name", "line_number", "current_line",
                    "cursor", "title_bar", "title_text", "window_border",
                    "junior_accent", "senior_accent"}
        assert not (required - THEMES[theme].keys())

    def test_token_cache_bounded(self):
        r = StudioRenderer(800, 600, language="python")
        for i in range(400):
            r._tokenize_pygments(f"def f{i}(): pass")
        assert len(r._token_cache) <= 256

    def test_regex_fallback_finds_keywords(self):
        r = StudioRenderer(400, 300, language="python")
        toks = r._tokenize("def f(): return 42")
        assert any("def" in t for _, t in toks)

    def test_tab_adv(self):
        r = StudioRenderer(800, 600, tab_size=4)
        assert r._tab_adv == r.char_w * 4

    def test_content_cache_pixel_budget(self):
        small = StudioRenderer(1280, 720)
        big = StudioRenderer(3840, 2160)
        assert small._cache_limit == 8
        assert big._cache_limit <= 2
        assert small._cache_limit * 1280 * 720 * 4 <= 100 * 1024 * 1024
        assert big._cache_limit * 3840 * 2160 * 4 <= 100 * 1024 * 1024

    def test_content_cache_bounded_in_practice(self):
        r = StudioRenderer(400, 300, code="x", title="t")
        for i in range(20):
            p = QPainter(QImage(400, 300, QImage.Format.Format_ARGB32))
            r.render_frame(p, "t", f"state {i}", 1.0)
            p.end()
        assert len(r._frame_cache) <= r._cache_limit

    def test_long_line_no_crash(self):
        r = StudioRenderer(400, 300)
        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        r.render_frame(p, "t", "x" * 5000, 0.1)
        p.end()

    def test_diff_colors_render(self):
        r = StudioRenderer(400, 300, line_diffs={0: "removed", 1: "added"})
        img = QImage(400, 300, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        r.render_frame(p, "t", "old\nnew\n", 0.5)
        p.end()


class TestEncoderArgs:
    def test_all_encoders_covered(self):
        assert set(ENCODERS) == set(ENCODER_ARGS.keys())


class TestRegistry:
    def test_complete(self):
        assert set(MODE_REGISTRY) >= {"code", "text", "multi", "jr"}
        for k, m in MODE_REGISTRY.items():
            assert all(m.values()), f"mode {k} incomplete"


class TestInputClamp:
    def test_truncated_with_marker(self):
        cfg = StudioConfig(use_custom=True, custom_code="x" * 250_000)
        code, _, _ = __import__("code_yt_mode").CodeYTStrategy()._get_code(
            cfg, [], cfg.custom_code)
        assert len(code) <= MAX_INPUT_CHARS + 50
        assert "truncated" in code

    def test_normal_input_untouched(self):
        cfg = StudioConfig(use_custom=True, custom_code=BASE_CODE)
        code, _, _ = __import__("code_yt_mode").CodeYTStrategy()._get_code(
            cfg, [], cfg.custom_code)
        assert code == BASE_CODE


# ═════════════════════════════════════════════════════════════════════════════
# FILE SELECTION PANEL
# ═════════════════════════════════════════════════════════════════════════════
class TestFileSelectionPanel:
    def _panel(self, paths, max_files=8):
        p = FileSelectionPanel(max_files=max_files)
        p.set_paths(paths)
        return p

    def test_max_enforced(self, qapp):
        p = self._panel(["/a.py", "/b.py", "/c.py"], max_files=2)
        assert p.paths() == ["/a.py", "/b.py"]

    def test_checked_paths_responds(self, qapp):
        p = self._panel(["/a.py", "/b.py", "/c.py"])
        assert p.checked_paths() == ["/a.py", "/b.py", "/c.py"]
        p.list_widget.item(1).setCheckState(Qt.CheckState.Unchecked)
        assert p.checked_paths() == ["/a.py", "/c.py"]

    def test_highlight_does_not_affect_export_set(self, qapp):
        p = self._panel(["/a.py", "/b.py"])
        p.list_widget.item(0).setSelected(True)
        assert p.checked_paths() == ["/a.py", "/b.py"]

    def test_select_matching_toggles_checks(self, qapp):
        p = self._panel(["/test_a.py", "/b.py"])
        p.select_matching("test_*.py")
        assert p.checked_paths() == ["/test_a.py"]

    def test_multiple_patterns_case_insensitive(self, qapp):
        p = self._panel(["/X.PY", "/y.py", "/c.spec.js"])
        p.select_matching("*.py, *.spec.js")
        assert sorted(p.checked_paths()) == ["/X.PY", "/c.spec.js",
                                             "/y.py"]

    def test_empty_pattern_selects_none(self, qapp):
        p = self._panel(["/a.py"])
        p.select_all()
        p.select_matching("")
        assert p.checked_paths() == []

    def test_set_paths_preserves_states(self, qapp):
        p = FileSelectionPanel(max_files=8)
        p.set_paths(["/a.py", "/b.py"])
        p.list_widget.item(0).setCheckState(Qt.CheckState.Unchecked)
        p.set_paths(["/a.py", "/b.py", "/c.py"],
                    states={"/a.py": False, "/b.py": True, "/c.py": True})
        assert p.checked_paths() == ["/b.py", "/c.py"]

    def test_no_signal_storm_on_batch_op(self, qapp):
        p = self._panel([f"/f{i}.py" for i in range(200)])
        hits = []
        p.selection_changed.connect(lambda: hits.append(1))
        p._set_all_checks(False)
        assert len(hits) == 1            # exactly one emit, not 200

    def test_invert(self, qapp):
        p = self._panel(["/a.py", "/b.py"])
        p.list_widget.item(0).setCheckState(Qt.CheckState.Unchecked)
        p.invert_selection()
        assert p.checked_paths() == ["/a.py", "/b.py"]


# ═════════════════════════════════════════════════════════════════════════════
# TAB WIRING (needs real windows)
# ═════════════════════════════════════════════════════════════════════════════
class TestTabsAndWindows:
    WINDOW_SPECS = [
        ("code_yt_mode", "CodeYTWindow"),
        ("text_emoji_mode", "TextEmojiWindow"),
        ("multi_window_mode", "MultiWindowStudio"),
        ("jr_vs_sr_mode", "JrVsSrWindow"),
    ]

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_window_constructs(self, isolated_settings, window_factory,
                               module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        assert win.windowTitle() == win.WINDOW_TITLE
        assert len(win.tabs) >= 1
        assert win.mode_tabs.count() == len(win.tabs)

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_tab_has_mode_and_wiring(self, isolated_settings,
                                     window_factory, module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        tab = win.tabs[0]
        assert tab.mode is not None, f"{cls_name} tab missing MODE"
        assert tab.WIRING, "WIRING table must be non-empty"
        for attr, key, kind in tab.WIRING:
            assert hasattr(win, attr), f"missing widget {attr}"
            assert hasattr(win.config, key), f"missing config key {key}"
            assert kind in ("spin", "dspin", "check", "combo", "text")

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_wiring_updates_config(self, isolated_settings,
                                   window_factory, module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        for attr, key, kind in win.tabs[0].WIRING:
            if kind == "spin" and "wpm" in key:
                getattr(win, attr).setValue(211)
                assert getattr(win.config, key) == 211
                return
        pytest.fail("no wpm spinbox found in WIRING")

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_load_settings_populates(self, isolated_settings,
                                     window_factory, module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        win.config.wpm_yt = win.config.wpm_txt = \
            win.config.wpm_mw = win.config.jr_wpm = 211
        win.tabs[0].load_settings(win.config)
        for attr, key, kind in win.tabs[0].WIRING:
            if kind == "spin" and "wpm" in key:
                assert getattr(win, attr).value() == 211
                return

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_quick_target_changes_wpm(self, isolated_settings,
                                      window_factory, module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        wpm_attr = win.tabs[0].WPM_SPINBOX_ATTR
        before = getattr(win, wpm_attr).value()
        win._apply_target_duration(120)
        assert getattr(win, wpm_attr).value() != before or before in (30,
                                                                      300)

    @pytest.mark.parametrize("module_name,cls_name", WINDOW_SPECS,
                             ids=["code", "text", "multi", "jr"])
    def test_preview_frame_seam(self, isolated_settings, window_factory,
                                module_name, cls_name):
        import importlib
        win = window_factory(importlib.import_module(module_name), cls_name)
        frames = wait_for(win.preview_worker.frame_ready, timeout_ms=10000)
        assert frames and not frames[0].isNull()

    def test_estimate_timer_interval_fixed(self, isolated_settings,
                                           window_factory):
        win = window_factory(__import__("code_yt_mode"), "CodeYTWindow")
        assert win.tabs[0]._est_timer.interval() == 300
        win.yt_wpm_sp.setValue(200)
        assert win.tabs[0]._est_timer.interval() == 300   # not the WPM value

    def test_shorts_marker_in_label(self, isolated_settings, window_factory):
        win = window_factory(__import__("code_yt_mode"), "CodeYTWindow")
        win.config.shorts_yt = True
        win.config.wpm_yt = 300          # above cap → must show marker
        win._dispatch_preview()
        win.tabs[0]._refresh_estimate()
        win.tabs[0]._est_timer.isActive() and None
        # force synchronous compute for assertion:
        win.tabs[0]._compute_estimate()
        assert "⚡" in win._dur_lbl.text()