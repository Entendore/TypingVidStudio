#!/usr/bin/env python3
"""Entry point: Text & Emoji mode."""
from studio_lib import *


class TextEmojiStrategy(BaseRenderStrategy):
    def build_panes(self, config, files, custom_code):
        w, h = self._output_size(config)
        code, lang, title = self._get_code(config, files, custom_code)
        wpm = self._shorts_capped_wpm(code, config.wpm_txt,
                                      config.shorts_txt, is_text=True)
        a = self._make_animator(code, wpm, is_text=True)
        return MultiPaneRenderer(
            [(self._make_renderer(config, w, h, code, title, lang), a,
              title)],
            w, h, 1, "Single", config=config)


class TextEmojiTab(BaseModeTab):
    TAB_LABEL = "Text & Emoji"
    MODE = StudioMode.TEXT_EMOJI
    WPM_SPINBOX_ATTR = "txt_wpm_sp"
    SHORTS_CHECK_ATTR = "txt_shorts_chk"
    WIRING = [
        ("txt_font_cb",      "font_txt",         "combo"),
        ("txt_font_sz_auto", "font_sz_auto_txt", "check"),
        ("txt_font_sz_sp",   "font_sz_txt",      "spin"),
        ("txt_wpm_sp",       "wpm_txt",          "spin"),
        ("txt_shorts_chk",   "shorts_txt",       "check"),
        ("ascii_chk",        "ascii_art",        "check"),
        ("txt_clean_chk",    "txt_clean",        "check"),
        ("txt_markdown_chk", "txt_markdown",     "check"),
        ("txt_crt_chk",      "txt_crt",          "check"),
        ("txt_bubbles_chk",  "txt_bubbles",      "check"),
        ("txt_cursor_chk",   "show_cursor",     "check"),
        ("txt_sound_cb",     "sound_preset",    "combo"),
        ("bgm_chk",         "bgm_enabled",      "check"),
        ("bgm_cb",          "bgm_source",       "combo_data"),
        ("bgm_vol_sp",      "bgm_volume",       "spin"),
    ]

    def build_ui(self):
        fl = self.add_settings_group("Text & Emoji Settings")
        font_cb, fs_row = create_font_controls("txt", self.mw)
        fl.addRow("Font:", font_cb)
        fl.addRow("Font Size:", fs_row)

        wpm_row = QHBoxLayout()
        wpm_row.setContentsMargins(0, 0, 0, 0)
        self.mw.txt_wpm_sp = self.create_wpm_spinbox(default=100)
        wpm_row.addWidget(self.mw.txt_wpm_sp)
        fl.addRow("WPM:", wpm_row)

        self.add_quick_target(fl)

        self.mw.ascii_chk = QCheckBox("ASCII Art Mode (Centered)")
        fl.addRow(self.mw.ascii_chk)
        self.mw.txt_clean_chk = QCheckBox("Clean Text Spacing")
        self.mw.txt_clean_chk.setChecked(True)
        fl.addRow(self.mw.txt_clean_chk)
        self.mw.txt_markdown_chk = QCheckBox(
            "Markdown Support (**bold**, *italic*)")
        fl.addRow(self.mw.txt_markdown_chk)
        self.mw.txt_crt_chk = QCheckBox("CRT / Terminal Filter")
        fl.addRow(self.mw.txt_crt_chk)
        self.mw.txt_bubbles_chk = QCheckBox("Chat Bubble Mode")
        fl.addRow(self.mw.txt_bubbles_chk)
        self.mw.txt_cursor_chk = QCheckBox("Show Typing Cursor")
        fl.addRow(self.mw.txt_cursor_chk)

        self.mw.txt_sound_cb = QComboBox()
        self.mw.txt_sound_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        fl.addRow("SFX:", self.mw.txt_sound_cb)

        self.add_bgm_controls(fl)

        self.finalize_layout()
        self.wire()
        self.attach_duration_label("txt_wpm_sp", wpm_row)
        self._refresh_estimate()


class TextEmojiWindow(StudioMainWindow):
    WINDOW_TITLE = "Typing Video Studio — Text & Emoji"
    STRATEGIES = {StudioMode.TEXT_EMOJI: TextEmojiStrategy()}
    MODE_LOG_NAME = "text_emoji"
    DEMO_FILES = {"demo_text.txt":
                  "Hello 👋\n"
                  "Welcome to the studio ✨\n"
                  "**Bold** and *italic* and `code`\n"
                  "Skin tones 👍🏽 and flags 🇺🇸 type as one key\n"
                  "Ship it 🚀🔥"}
    FILE_PANEL_TITLE = "Input Text File"
    FILE_PANEL_MAX = 1
    FILE_PANEL_FILTER = ("Text (*.txt *.md *.markdown *.csv *.tsv *.asc "
                         "*.ascii *.art *.nfo *.diz *.emoji *.emo)")
    FILE_PANEL_HINT = ("One text/emoji file. Shortcodes like :rocket: "
                       "convert automatically. Check = export.")

    def make_tabs(self):
        return [TextEmojiTab(self)]

    def demo_content(self):
        return "demo_text.txt", "Hello 👋\nAdd files!\n🚀✨"


register_mode("text", TextEmojiStrategy, TextEmojiTab, TextEmojiWindow)

if __name__ == "__main__":
    run_studio(TextEmojiWindow)