#!/usr/bin/env python3
"""Entry point: Single Code Editor mode (Code YT)."""
from studio_lib import *


class CodeYTStrategy(BaseRenderStrategy):
    def build_panes(self, config, files, custom_code):
        w, h = self._output_size(config)
        code, lang, title = self._get_code(config, files, custom_code)
        wpm = self._shorts_capped_wpm(code, config.wpm_yt, config.shorts_yt)
        a = self._make_animator(code, wpm)
        return MultiPaneRenderer(
            [(self._make_renderer(config, w, h, code, title, lang), a,
              title)],
            w, h, 1, "Single", config=config)


class CodeYTTab(BaseModeTab):
    TAB_LABEL = "Code YT"
    MODE = StudioMode.CODE_YT
    WPM_SPINBOX_ATTR = "yt_wpm_sp"
    SHORTS_CHECK_ATTR = "yt_shorts_chk"
    WIRING = [
        ("yt_font_cb",      "font_yt",         "combo"),
        ("yt_font_sz_auto", "font_sz_auto_yt", "check"),
        ("yt_font_sz_sp",   "font_sz_yt",      "spin"),
        ("yt_wpm_sp",       "wpm_yt",          "spin"),
        ("yt_shorts_chk",   "shorts_yt",       "check"),
        ("yt_zoom_chk",     "yt_zoom",         "check"),
        ("yt_focus_chk",    "yt_focus",        "check"),
        ("yt_cursor_chk",   "show_cursor",     "check"),
        ("yt_sound_cb",     "sound_preset",    "combo"),
        ("bgm_chk",         "bgm_enabled",     "check"),
        ("bgm_cb",          "bgm_source",      "combo_data"),
        ("bgm_vol_sp",      "bgm_volume",      "spin"),
    ]

    def build_ui(self):
        fl = self.add_settings_group("Code YT Settings")
        font_cb, fs_row = create_font_controls("yt", self.mw)
        fl.addRow("Font:", font_cb)
        fl.addRow("Font Size:", fs_row)

        wpm_row = QHBoxLayout()
        wpm_row.setContentsMargins(0, 0, 0, 0)
        self.mw.yt_wpm_sp = self.create_wpm_spinbox(default=100)
        wpm_row.addWidget(self.mw.yt_wpm_sp)
        fl.addRow("WPM:", wpm_row)

        self.add_quick_target(fl)

        fl.addRow(self.mw.yt_shorts_chk)
        self.mw.yt_zoom_chk = QCheckBox("Cinematic Ken Burns Zoom")
        fl.addRow(self.mw.yt_zoom_chk)
        self.mw.yt_focus_chk = QCheckBox("Code Block Focus (Dimming)")
        fl.addRow(self.mw.yt_focus_chk)
        self.mw.yt_cursor_chk = QCheckBox("Show Typing Cursor")
        fl.addRow(self.mw.yt_cursor_chk)

        self.mw.yt_sound_cb = QComboBox()
        self.mw.yt_sound_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        fl.addRow("SFX:", self.mw.yt_sound_cb)

        self.add_bgm_controls(fl)

        self.finalize_layout()
        self.wire()
        self.attach_duration_label("yt_wpm_sp", wpm_row)
        self._refresh_estimate()


class CodeYTWindow(StudioMainWindow):
    WINDOW_TITLE = "Typing Video Studio — Code YT"
    STRATEGIES = {StudioMode.CODE_YT: CodeYTStrategy()}
    MODE_LOG_NAME = "code_yt"
    DEMO_FILES = {"demo_code.py":
                  "def fibonacci(n):\n"
                  "    a, b = 0, 1\n"
                  "    for _ in range(n):\n"
                  "        yield a\n"
                  "        a, b = b, a + b\n"
                  "\n"
                  "print(list(fibonacci(10)))\n"}
    FILE_PANEL_TITLE = "Input Code File"
    FILE_PANEL_MAX = 1
    FILE_PANEL_FILTER = ("Code (*.py *.pyw *.pyi *.js *.mjs *.jsx *.ts "
                         "*.tsx *.java *.kt *.c *.h *.cpp *.cs *.go *.rs "
                         "*.rb *.php *.swift *.sh *.sql *.json *.yaml "
                         "*.yml *.toml *.md)")
    FILE_PANEL_HINT = ("One code file. Check = export; use the Custom tab "
                       "to type code directly instead.")

    def make_tabs(self):
        return [CodeYTTab(self)]

    def demo_content(self):
        return "demo_code.py", "def hello_world():\n    print('Hello, Studio!')"


register_mode("code", CodeYTStrategy, CodeYTTab, CodeYTWindow)

if __name__ == "__main__":
    run_studio(CodeYTWindow)