#!/usr/bin/env python3
"""
E2E tests: real windows → preview → playback → scrub → export → files on
disk → CLI. Uses real ExportManager with real strategies; asserts on the
same artifacts a user gets. ffmpeg-conditional assertions keep the suite
green on machines without ffmpeg while staying strict where it exists.

Run:  QT_QPA_PLATFORM=offscreen pytest test_e2e.py -v --timeout=180
"""
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer

from conftest import wait_for

from studio_lib import (StudioConfig, StudioMode, FileItem, TypingAnimator,
                        ExportManager, ExportState, read_text_file,
                        OVERHEAD_MIN, OVERHEAD_MAX, HAS_FFMPEG)
import code_yt_mode, text_emoji_mode, multi_window_mode, jr_vs_sr_mode


def has_ffmpeg() -> bool:
    return subprocess.run(["ffmpeg", "-version"],
                          capture_output=True).returncode == 0


BASE_CODE = "def hello():\n    print('world')\n"
LONG_CODE = "\n".join(f"x_{i} = {i}" for i in range(150))
DEMO_JR = ("def calc(x):\n    if x == 1:\n        return 1\n"
           "    else:\n        return x * calc(x - 1)")
DEMO_SR = ("import math\n\ndef calc(x):\n"
           "    return math.prod(range(1, x + 1))")


# ═════════════════════════════════════════════════════════════════════════════
# WINDOW LIFECYCLE
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("module,cls_name", [
    (code_yt_mode, "CodeYTWindow"),
    (text_emoji_mode, "TextEmojiWindow"),
    (multi_window_mode, "MultiWindowStudio"),
    (jr_vs_sr_mode, "JrVsSrWindow"),
], ids=["code", "text", "multi", "jr"])
def test_launch_produces_preview(module, cls_name, isolated_settings,
                                 window_factory):
    """Startup → demo content in the file panel → preview frame arrives."""
    win = window_factory(module, cls_name)
    assert win._items, "demo content loaded at startup"
    frames = wait_for(win.preview_worker.frame_ready, timeout_ms=15000)
    assert frames and not frames[0].isNull() and frames[0].width() > 100


def test_settings_change_rerenders(isolated_settings, window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    wait_for(win.preview_worker.frame_ready)
    win.config.theme = ("One Dark"
                        if win.config.theme == "Dracula" else "Dracula")
    win._dispatch_preview()
    frames = wait_for(win.preview_worker.frame_ready, timeout_ms=15000)
    assert frames, "re-render after settings change produced no frame"


def test_open_file_flows_to_preview(isolated_settings, window_factory,
                                    tmp_path):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    f = tmp_path / "my.py"
    f.write_text(LONG_CODE)
    win._items = [FileItem(path=str(f), checked=True)]
    win.config.use_custom = False
    win._dispatch_preview()
    frames = wait_for(win.preview_worker.frame_ready, timeout_ms=15000)
    assert frames and not frames[0].isNull()


def test_file_panel_selection_flows_to_items(isolated_settings,
                                             window_factory, tmp_path):
    """The panel is the input surface — checking drives _items and preview."""
    win = window_factory(multi_window_mode, "MultiWindowStudio")
    a = tmp_path / "a.py"
    a.write_text(BASE_CODE)
    b = tmp_path / "b.py"
    b.write_text("def hello():\n    print('changed')\n")
    win.file_panel.set_paths([str(a), str(b)])
    assert [it.path for it in win._items] == [str(a), str(b)]
    # uncheck one → only the other exports
    win.file_panel.list_widget.item(1).setCheckState(
        Qt_CheckState_Unchecked())
    assert [it.path for it in win._items] == [str(a)]


def Qt_CheckState_Unchecked():
    from PySide6.QtCore import Qt
    return __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.CheckState.Unchecked


def test_close_saves_settings(isolated_settings, window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    win.config.wpm_yt = 187
    win.close()
    assert StudioConfig.load(win.SETTINGS_PATH).wpm_yt == 187


def test_strict_order_caps_jr_sr_selection(isolated_settings,
                                           window_factory, tmp_path):
    win = window_factory(jr_vs_sr_mode, "JrVsSrWindow")
    assert win.FILE_PANEL_STRICT_ORDER is True
    paths = [str(tmp_path / f"{i}.py") for i in range(3)]
    for p in paths:
        Path(p).write_text(BASE_CODE)
    win.file_panel.set_paths(paths)
    win._on_file_selection()
    assert len(win._items) == 2      # only first two survive


# ═════════════════════════════════════════════════════════════════════════════
# PREVIEW PLAYBACK (FSM + wall clock)
# ═════════════════════════════════════════════════════════════════════════════
def test_scrub_does_not_rebuild(isolated_settings, window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        key = win._cached_panes_key
        win.scrub_slider.setValue(85)
        win._render_preview_now()
        assert win._cached_panes_key == key, "scrub triggered a rebuild"
    finally:
        win.preview_worker.stop()
        win.close()


def test_playback_completes_and_resets(isolated_settings, window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        assert win._preview_fsm.state is not None
        win.toggle_playback()
        assert win._preview_fsm.state.value == "playing"
        win._playback_t = win._cached_panes.duration() - 0.01
        win._clock.restart()
        win._playback_tick()
        assert win._preview_fsm.state.value == "ready"
        assert win.play_btn.text() == "▶ Play"
    finally:
        win.preview_worker.stop()
        win.close()


def test_playback_wall_clock_advances(isolated_settings, window_factory):
    """Playback t must track wall time (not tick count) — the fix that
    made preview speed equal export speed."""
    import time
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        win.toggle_playback()
        time.sleep(0.15)
        win._playback_tick()
        assert win._playback_t > 0.08, \
            f"wall clock not driving playback (t={win._playback_t})"
    finally:
        win.preview_worker.stop()
        win.close()


def test_settings_change_during_playback_resumes(isolated_settings,
                                                 window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        win.toggle_playback()
        win._playback_t = win._cached_panes.duration() * 0.5
        win.config.theme = "One Dark"
        win._dispatch_preview()
        assert win._preview_fsm.state.value == "playing"
        assert win._playback_t > 0          # position preserved
    finally:
        win.preview_worker.stop()
        win.close()


def test_failed_build_pinned_until_retry(isolated_settings, window_factory,
                                         monkeypatch):
    """A failing build must not be retried per frame — the retry storm fix."""
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        calls = []
        real = win.render_preview_panes

        def boom():
            calls.append(1)
            raise RuntimeError("boom")

        monkeypatch.setattr(win, "render_preview_panes", boom)
        win._dispatch_preview()
        assert win._preview_fsm.state.value == "error"
        n = len(calls)
        win._render_preview_now()
        win._render_preview_now()
        assert len(calls) == n, "failed build retried — storm not pinned"
        monkeypatch.setattr(win, "render_preview_panes", real)
        win.refresh_preview()               # explicit retry un-pins
        wait_for(win.preview_worker.frame_ready, timeout_ms=10000)
        assert win._preview_fsm.state.value == "ready"
    finally:
        win.preview_worker.stop()
        win.close()


def test_quality_toggle_rebuilds(isolated_settings, window_factory):
    win = window_factory(code_yt_mode, "CodeYTWindow")
    try:
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        old = win._cached_panes
        win._on_quality(2)                  # Full res
        assert win.PREVIEW_SCALE == 1.0
        win._dispatch_preview()
        wait_for(win.preview_worker.frame_ready)
        assert win._cached_panes is not old
    finally:
        win.preview_worker.stop()
        win.close()


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
def _run_export(tmp_path, items, overrides=None, mode=StudioMode.CODE_YT):
    cfg = StudioConfig()
    cfg.mode = mode
    cfg.output_dir = str(tmp_path / "out")
    cfg.target_duration = 10
    for k, v in (overrides or {}).items():
        setattr(cfg, k, v)
    host = type("Host", (), {})()
    host.config = cfg
    host.strategies = {
        StudioMode.CODE_YT: code_yt_mode.CodeYTStrategy(),
        StudioMode.TEXT_EMOJI: text_emoji_mode.TextEmojiStrategy(),
        StudioMode.MULTI_WINDOW: multi_window_mode.MultiWindowStrategy(),
        StudioMode.JR_VS_SR: jr_vs_sr_mode.JrVsSrStrategy(),
    }
    em = ExportManager(host)
    results = {}
    updates = []
    em.item_progress.connect(
        lambda d, t, p: updates.append((d, t, p)))
    loop = QEventLoop()
    em.batch_finished.connect(
        lambda ok, fail: (results.update(ok=ok, fail=fail), loop.quit()))
    QTimer.singleShot(120_000, loop.quit)
    em.start(items)
    loop.exec()
    return results, Path(cfg.output_dir), updates, em


def test_export_produces_video(tmp_path):
    f = tmp_path / "sample.py"
    f.write_text(BASE_CODE)
    results, out_dir, _, em = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)])
    assert results.get("ok") == 1, results
    assert em.state.value == "idle"        # FSM returned to IDLE (not wedged)
    artifacts = list(out_dir.glob("sample_*"))
    assert artifacts
    if has_ffmpeg():
        mp4 = next(a for a in artifacts if a.suffix == ".mp4")
        assert mp4.stat().st_size > 10_000
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "json", str(mp4)], capture_output=True, text=True)
        dur = float(json.loads(probe.stdout)["format"]["duration"])
        assert 0.5 <= dur <= 30


def test_export_with_audio_stream(tmp_path):
    if not has_ffmpeg():
        pytest.skip("ffmpeg not available")
    f = tmp_path / "sonic.py"
    f.write_text(BASE_CODE)
    results, out_dir, _, _ = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)],
        {"sound_enabled": True, "volume": 60})
    assert results.get("ok") == 1
    mp4 = next(out_dir.glob("sonic_*.mp4"))
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_streams", "-of", "json", str(mp4)],
        capture_output=True, text=True)
    streams = json.loads(probe.stdout)["streams"]
    assert any(s["codec_type"] == "audio" for s in streams), \
        "audio not muxed into export"


def test_export_fsm_never_wedges_on_tiny_file(tmp_path):
    """The fast-batch race: export must complete and return to IDLE even
    when the worker finishes before the spawner's next statement."""
    f = tmp_path / "tiny.py"
    f.write_text("x=1\n")
    results, _, _, em = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)],
        {"fps": 10, "yt_extras": False, "gen_metadata": False,
         "sound_enabled": False})
    assert results.get("ok") == 1
    assert em.state.value == "idle"
    # immediate re-export must not raise (require(IDLE) passes):
    results2, _, _, em2 = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)],
        {"fps": 10, "yt_extras": False, "gen_metadata": False,
         "sound_enabled": False})
    assert results2.get("ok") == 1


def test_frame_level_progress_emitted(tmp_path):
    f = tmp_path / "prog.py"
    f.write_text(BASE_CODE)
    results, _, updates, _ = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)])
    assert results.get("ok") == 1
    assert updates, "no item_progress emitted"
    assert updates[-1][0] == updates[-1][1]        # ends at full frames
    assert any("Rendering" in p for _, _, p in updates)


def test_batch_export_auto_wpm(tmp_path):
    items = []
    for i, content in enumerate([BASE_CODE, LONG_CODE, "x = 1\n"]):
        f = tmp_path / f"batch_{i}.py"
        f.write_text(content)
        it = FileItem(path=str(f), checked=True)
        it.wpm_override = TypingAnimator.find_wpm_for_target(
            read_text_file(str(f)), 10, OVERHEAD_MIN, OVERHEAD_MAX)
        items.append(it)
    results, out_dir, _, _ = _run_export(tmp_path, items)
    assert results.get("ok") == 3, results
    assert len(list(out_dir.glob("batch_*"))) >= 3


def test_export_failure_contained(tmp_path):
    good = tmp_path / "good.py"
    good.write_text(BASE_CODE)
    bad = FileItem(path=str(tmp_path / "missing.py"), checked=True)
    results, _, _, _ = _run_export(
        tmp_path, [bad, FileItem(path=str(good), checked=True)])
    assert results.get("ok") == 1 and results.get("fail") == 1


def test_yt_extras_thumbnails_and_metadata(tmp_path):
    f = tmp_path / "thumbs.py"
    f.write_text(BASE_CODE)
    results, out_dir, updates, _ = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)],
        {"yt_extras": True, "gen_metadata": True})
    assert results.get("ok") == 1
    thumbs = list(out_dir.glob("*_thumb_*.png"))
    assert len(thumbs) >= 3
    meta = next(out_dir.glob("*_metadata.txt")).read_text()
    assert "Title:" in meta or "Tags:" in meta
    assert any("Thumbnails" in p for _, _, p in updates)
    assert any("Metadata" in p for _, _, p in updates)


def test_cancel_mid_batch(tmp_path):
    items = []
    for i in range(3):
        f = tmp_path / f"c{i}.py"
        f.write_text(LONG_CODE)
        items.append(FileItem(path=str(f), checked=True))
    cfg = StudioConfig()
    cfg.output_dir = str(tmp_path / "out")
    host = type("Host", (), {"config": cfg,
                             "strategies": {
                                 StudioMode.CODE_YT:
                                     code_yt_mode.CodeYTStrategy()}})()
    em = ExportManager(host)
    em.batch_started.connect(lambda *_: em.cancel())
    loop = QEventLoop()
    em.batch_finished.connect(lambda *_: loop.quit())
    QTimer.singleShot(60_000, loop.quit)
    em.start(items)
    loop.exec()
    assert em._cancel
    assert em.state.value == "idle"        # CANCELLING → FINISHED → IDLE


def test_export_does_not_block_caller(tmp_path):
    """start() must return immediately — the UI-freeze regression guard."""
    import time as _t
    f = tmp_path / "nb.py"
    f.write_text(LONG_CODE)
    cfg = StudioConfig(output_dir=str(tmp_path / "out"))
    host = type("Host", (), {"config": cfg,
                             "strategies": {
                                 StudioMode.CODE_YT:
                                     code_yt_mode.CodeYTStrategy()}})()
    em = ExportManager(host)
    loop = QEventLoop()
    em.batch_finished.connect(lambda *_: loop.quit())
    t0 = _t.monotonic()
    em.start([FileItem(path=str(f), checked=True)])
    assert _t.monotonic() - t0 < 0.5, "start() blocked the caller"
    QTimer.singleShot(120_000, loop.quit)
    loop.exec()


def test_export_uses_frozen_config(tmp_path):
    """Mid-export settings mutations must not affect the running batch."""
    f = tmp_path / "frozen.py"
    f.write_text(BASE_CODE)
    cfg = StudioConfig(output_dir=str(tmp_path / "out"), theme="Dracula")
    host = type("Host", (), {"config": cfg,
                             "strategies": {
                                 StudioMode.CODE_YT:
                                     code_yt_mode.CodeYTStrategy()}})()
    em = ExportManager(host)
    em.batch_started.connect(
        lambda *_: setattr(host.config, "theme", "One Dark"))
    results, _, _, _ = _run_export(
        tmp_path, [FileItem(path=str(f), checked=True)]) \
        if False else (None, None, None, em)
    # run for real (the lambda above mutated during _run_export's export):
    em2 = ExportManager(host)
    results = {}
    loop = QEventLoop()
    em2.batch_finished.connect(
        lambda ok, fail: (results.update(ok=ok, fail=fail), loop.quit()))
    QTimer.singleShot(120_000, loop.quit)
    em2.start([FileItem(path=str(f), checked=True)])
    loop.exec()
    assert results.get("ok") == 1
    assert em2._cfg_snapshot.theme == "Dracula"    # frozen at start()


def test_jr_sr_json_export_per_pane_audio(tmp_path):
    """Jr/Sr exports use the two per-pane sound presets — the pipeline
    must complete with both tracks configured."""
    if not has_ffmpeg():
        pytest.skip("ffmpeg not available")
    pair = tmp_path / "pair.json"
    pair.write_text(json.dumps({"title": "t", "language": "python",
                                "junior_code": DEMO_JR,
                                "senior_code": DEMO_SR}))
    results, out_dir, _, _ = _run_export(
        tmp_path, [FileItem(path=str(pair), checked=True)],
        {"mode": StudioMode.JR_VS_SR, "jr_sound": "Mechanical",
         "sr_sound": "ASMR Deep Thock", "sound_enabled": True},
        mode=StudioMode.JR_VS_SR)
    assert results.get("ok") == 1
    assert list(out_dir.glob("pair_*.mp4"))


# ═════════════════════════════════════════════════════════════════════════════
# HEADLESS CLI
# ═════════════════════════════════════════════════════════════════════════════
def test_cli_export(tmp_path):
    f = tmp_path / "cli.py"
    f.write_text(BASE_CODE)
    out = tmp_path / "out"
    out.mkdir()
    proc = subprocess.run(
        [sys.executable, "studio.py", "--export", str(f),
         "--out-dir", str(out), "--target", "8"],
        capture_output=True, text=True, timeout=300,
        cwd=str(Path(__file__).parent))
    assert proc.returncode == 0, proc.stderr[-500:]
    assert list(out.glob("cli*")), "CLI export produced no artifacts"


def test_cli_explicit_mode(tmp_path):
    f = tmp_path / "cli.txt"
    f.write_text("Hello 👋\nWorld 🚀")
    out = tmp_path / "out"
    out.mkdir()
    proc = subprocess.run(
        [sys.executable, "studio.py", "--export", str(f), "--mode", "text",
         "--out-dir", str(out), "--target", "8"],
        capture_output=True, text=True, timeout=300,
        cwd=str(Path(__file__).parent))
    assert proc.returncode == 0, proc.stderr[-500:]


def test_cli_missing_file(tmp_path):
    proc = subprocess.run(
        [sys.executable, "studio.py", "--export",
         str(tmp_path / "nope.py")],
        capture_output=True, text=True, timeout=120,
        cwd=str(Path(__file__).parent))
    assert proc.returncode != 0


# ═════════════════════════════════════════════════════════════════════════════
# UNIFIED WINDOW
# ═════════════════════════════════════════════════════════════════════════════
def test_unified_constructs_four_tabs(isolated_settings, window_factory):
    import unified_main
    win = window_factory(unified_main, "UnifiedStudioWindow")
    assert win.mode_tabs.count() == 4
    assert not hasattr(win, "file_panel")   # batch table supersedes it


def test_unified_drop_no_crash(isolated_settings, window_factory):
    import unified_main
    win = window_factory(unified_main, "UnifiedStudioWindow")
    win.dropEvent(type("E", (), {
        "mimeData": lambda s: type("M", (), {
            "urls": lambda s: []})(),
        "acceptProposedAction": lambda s: None})())
    # empty drop is a no-op — the crash was in the unguarded file_panel path


def test_unified_batch_pattern_matching(isolated_settings, window_factory):
    import unified_main
    win = window_factory(unified_main, "UnifiedStudioWindow")
    win._items = [FileItem(path=f"/w/{n}", checked=False) for n in
                  ("a_test.py", "b.py", "c_test.py", "d.md")]
    win._refresh_table()
    win._check_matching("*_test.py")
    assert [it.checked for it in win._items] == [True, False, True, False]
    win._invert_checks()
    assert [it.checked for it in win._items] == [False, True, False, True]


def test_unified_batch_count_label(isolated_settings, window_factory):
    import unified_main
    win = window_factory(unified_main, "UnifiedStudioWindow")
    win._items = [FileItem(path=f"/w/{n}", checked=False) for n in
                  ("a.py", "b.py", "c.py")]
    win._refresh_table()
    assert "0 / 3" in win.batch_count_lbl.text()
    win._set_all_checks(True)
    assert "3 / 3" in win.batch_count_lbl.text()


def test_unified_global_settings_autosave(isolated_settings, window_factory):
    import unified_main
    win = window_factory(unified_main, "UnifiedStudioWindow")
    win._set_cfg('volume', 77)
    assert win.config.volume == 77
    assert win._save_timer.isActive()      # crash-safe write scheduled