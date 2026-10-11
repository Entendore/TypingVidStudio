#!/usr/bin/env python3
"""
Launcher for all Typing Video Studio modes + headless CLI export.

Usage:
  python studio.py                     # Code YT (default)
  python studio.py text|jr|multi|all   # other modes
  python studio.py --export FILE [--mode MODE] [--wpm N] [--target SECS]
                   [--out-dir DIR]     # headless render, no GUI

Headless examples:
  python studio.py --export input/demo.py --wpm 150 --out-dir vids/
  python studio.py --export pair.json --mode jr --target 90
  for f in input/*.py; do python studio.py --export "$f" --out-dir out/; done
"""
import argparse
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(
        description="Typing Video Studio — keystroke animation renderer")
    ap.add_argument("mode", nargs="?", default="code",
                    choices=["code", "text", "jr", "multi", "all"],
                    help="code=Code YT, text=Text & Emoji, jr=Junior vs "
                         "Senior, multi=Multi-Window, all=Unified window")
    ap.add_argument("--export", metavar="FILE",
                    help="Render FILE to video and exit (no GUI)")
    ap.add_argument("--mode", dest="export_mode",
                    choices=["code", "text", "jr", "multi"],
                    help="Rendering mode for --export (default: code)")
    ap.add_argument("--wpm", type=int,
                    help="Override WPM (otherwise solved from --target)")
    ap.add_argument("--target", type=int, metavar="SECS",
                    help="Solve WPM to hit this duration (default: "
                         "saved settings, usually 60s)")
    ap.add_argument("--out-dir", help="Output directory")
    args = ap.parse_args()

    if args.export:
        return cli_export(args)

    return launch_gui(args)


def launch_gui(args):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    # DPI policy MUST precede QApplication creation:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    from studio_lib import apply_theme
    app = QApplication(sys.argv)
    apply_theme(app)

    if args.mode == "text":
        import text_emoji_mode
        W = text_emoji_mode.TextEmojiWindow
    elif args.mode == "jr":
        import jr_vs_sr_mode
        W = jr_vs_sr_mode.JrVsSrWindow
    elif args.mode == "multi":
        import multi_window_mode
        W = multi_window_mode.MultiWindowStudio
    elif args.mode == "all":
        import unified_main
        W = unified_main.UnifiedStudioWindow
    else:
        import code_yt_mode
        W = code_yt_mode.CodeYTWindow

    win = W()
    win.show()
    sys.exit(app.exec())


def cli_export(args):
    """Headless export: engine only, no window. Uses the same strategy
    pipeline as the GUI so output is identical."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop, QTimer
    # QApplication is required even headless — QImage/QPainter need it:
    app = QApplication(sys.argv)
    from studio_lib import (StudioConfig, StudioMode, FileItem, ExportManager,
                            TypingAnimator, read_text_file, detect_language,
                            OVERHEAD_MIN, OVERHEAD_MAX, logger,
                            log_mode_event)
    import code_yt_mode, text_emoji_mode, multi_window_mode, jr_vs_sr_mode

    src = Path(args.export)
    if not src.exists():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 1

    cfg = StudioConfig.load()
    if args.wpm:
        cfg.wpm_yt = cfg.wpm_txt = args.wpm
    if args.out_dir:
        cfg.output_dir = args.out_dir

    mode_map = {
        "code": (StudioMode.CODE_YT, code_yt_mode.CodeYTStrategy),
        "text": (StudioMode.TEXT_EMOJI, text_emoji_mode.TextEmojiStrategy),
        "multi": (StudioMode.MULTI_WINDOW,
                  multi_window_mode.MultiWindowStrategy),
        "jr": (StudioMode.JR_VS_SR, jr_vs_sr_mode.JrVsSrStrategy),
    }
    mode_key = args.export_mode or (
        "jr" if src.suffix.lower() == ".json"
        and "junior_code" in src.read_text(encoding="utf-8")[:2000]
        else "text" if src.suffix.lower() in (".txt", ".md", ".emoji")
        else "code")
    mode, strategy_cls = mode_map[mode_key]
    cfg.mode = mode
    log = __import__("studio_lib").get_mode_logger(
        {"code": "code_yt", "text": "text_emoji", "multi": "multi_window",
         "jr": "jr_vs_sr"}[mode_key])

    host = type("Host", (), {})()
    host.config = cfg
    host.strategies = {mode: strategy_cls()}

    item = FileItem(path=str(src), checked=True)
    if args.wpm:
        item.wpm_override = args.wpm
    else:
        target = float(args.target) if args.target else \
            float(cfg.target_duration)
        code = read_text_file(str(src), cfg.txt_clean)
        is_text = (mode == StudioMode.TEXT_EMOJI)
        item.wpm_override = TypingAnimator.find_wpm_for_target(
            code, target, OVERHEAD_MIN, OVERHEAD_MAX, is_text=is_text)
        print(f"solved WPM {item.wpm_override} for ~{target:.0f}s "
              f"({len(code)} chars, {mode_key} mode)")

    em = ExportManager(host)
    result = {}
    loop = QEventLoop()

    def on_started(total):
        print(f"exporting {total} item(s) → {cfg.output_dir}")

    def on_progress(done, name):
        print(f"  [{done}] {name}")

    def on_item_progress(frames_done, frames_total, phase):
        pct = int(100 * frames_done / max(1, frames_total))
        print(f"\r  {phase}: {frames_done}/{frames_total} ({pct}%)",
              end="", flush=True)

    def on_finished(ok, fail):
        result.update(ok=ok, fail=fail)
        print()                     # newline after the \r progress line
        loop.quit()

    em.batch_started.connect(on_started)
    em.batch_progress.connect(on_progress)
    em.item_progress.connect(on_item_progress)
    em.batch_finished.connect(on_finished)
    QTimer.singleShot(3600_000, loop.quit)   # 1h hard cap
    em.start([item])
    loop.exec()

    ok = result.get("ok", 0) == 1
    log_mode_event(log, "cli_export_done", file=src.name, ok=ok)
    print(f"done: ok={result.get('ok', 0)} failed={result.get('fail', 0)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)