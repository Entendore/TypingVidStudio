"""
conftest.py — shared fixtures and helpers for both test suites.

Provides:
  qapp                — session-scoped QApplication (offscreen via env var)
  window_factory      — makes mode windows, tears them down cleanly
  isolated_settings   — redirects SETTINGS_FILE/TEMP_DIR per test
  _host_with          — minimal ExportManager host stub with strategies
  _wait_batch         — QEventLoop wait for batch_finished
  wait_for            — signal-capture helper with timeout

Run:  QT_QPA_PLATFORM=offscreen pytest -v
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication


# ── session Qt app ───────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


# ── studio_lib + mode modules (imported AFTER qapp exists) ──────────────────
@pytest.fixture(scope="session")
def studio(qapp):
    import studio_lib
    return studio_lib


@pytest.fixture(scope="session")
def modes(qapp):
    import code_yt_mode, text_emoji_mode, multi_window_mode, jr_vs_sr_mode
    from types import SimpleNamespace
    return SimpleNamespace(
        code=code_yt_mode,
        text=text_emoji_mode,
        multi=multi_window_mode,
        jr=jr_vs_sr_mode,
    )


# ── window lifecycle ─────────────────────────────────────────────────────────
@pytest.fixture
def window_factory(qapp):
    """Make mode windows; all are stopped/closed on teardown so preview
    timers and the (inert) worker never outlive the test."""
    made = []

    def make(module, cls_name):
        win = getattr(module, cls_name)()
        made.append(win)
        return win

    yield make
    for win in made:
        try:
            win._play_timer.stop()
        except AttributeError:
            pass
        try:
            win.preview_worker.stop()
        except AttributeError:
            pass
        win.close()


# ── settings isolation ───────────────────────────────────────────────────────
@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    """Redirect settings + temp so tests never touch the user's real
    settings.json and parallel runs can't corrupt each other."""
    import studio_lib
    monkeypatch.setattr(studio_lib, "SETTINGS_FILE",
                        tmp_path / "settings.json")
    monkeypatch.setattr(studio_lib, "TEMP_DIR", tmp_path / "temp")
    (tmp_path / "temp").mkdir(exist_ok=True)
    # windows read StudioMainWindow.SETTINGS_PATH at class level — patch it
    # too so freshly constructed windows write inside tmp_path:
    monkeypatch.setattr("studio_lib.StudioMainWindow.SETTINGS_PATH",
                        tmp_path / "settings.json")
    yield tmp_path


# ── export host stub ─────────────────────────────────────────────────────────
@pytest.fixture
def _host_with(qapp):
    """Minimal ExportManager parent: .config + .strategies only."""
    import studio_lib
    import code_yt_mode, text_emoji_mode, multi_window_mode, jr_vs_sr_mode

    def make(cfg):
        host = type("Host", (), {})()
        host.config = cfg
        host.strategies = {
            studio_lib.StudioMode.CODE_YT: code_yt_mode.CodeYTStrategy(),
            studio_lib.StudioMode.TEXT_EMOJI:
                text_emoji_mode.TextEmojiStrategy(),
            studio_lib.StudioMode.MULTI_WINDOW:
                multi_window_mode.MultiWindowStrategy(),
            studio_lib.StudioMode.JR_VS_SR:
                jr_vs_sr_mode.JrVsSrStrategy(),
        }
        return host

    return make


@pytest.fixture
def _wait_batch(qapp):
    """Block until batch_finished (or timeout). Returns nothing —
    inspect the manager/results afterwards."""
    def wait(em, timeout_ms=120_000):
        loop = QEventLoop()
        em.batch_finished.connect(lambda *_: loop.quit())
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
    return wait


# ── generic signal wait ──────────────────────────────────────────────────────
def wait_for(signal, timeout_ms=15000):
    """Connect, start an event loop, capture the first emission.
    Returns the captured args (single arg unwrapped) or [] on timeout."""
    loop = QEventLoop()
    got = []

    def capture(*args):
        got.append(args[0] if len(args) == 1 else args)
        loop.quit()

    signal.connect(capture)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    return got


# expose as fixture too, for injection into tests:
@pytest.fixture
def _wait_for(qapp):
    return wait_for


# ── shared test content ──────────────────────────────────────────────────────
BASE_CODE = "def hello():\n    print('world')\n"
LONG_CODE = "\n".join(f"x_{i} = {i}  # line {i}" for i in range(200))
DEMO_JR = ("def calc(x):\n    if x == 1:\n        return 1\n"
           "    else:\n        return x * calc(x - 1)")
DEMO_SR = ("import math\n\ndef calc(x):\n"
           "    return math.prod(range(1, x + 1))")


@pytest.fixture
def base_code():
    return BASE_CODE


@pytest.fixture
def long_code():
    return LONG_CODE