#!/usr/bin/env python3
"""Entry point: Junior vs Senior Dev mode."""
import json
import difflib
from studio_lib import *

DEMO_JR = ("def calc(x):\n"
           "    if x == 1:\n"
           "        return 1\n"
           "    else:\n"
           "        return x * calc(x - 1)")
DEMO_SR = ("import math\n\n"
           "def calc(x):\n"
           "    return math.prod(range(1, x + 1))")


class JrVsSrStrategy(BaseRenderStrategy):
    def get_codes(self, config, files, custom_code):
        if config.use_custom or (config.jr_custom_code
                                 and config.sr_custom_code):
            code1 = (convert_shortcodes(config.jr_custom_code)
                     if config.jr_custom_code
                     else "def junior():\n    pass")
            code2 = (convert_shortcodes(config.sr_custom_code)
                     if config.sr_custom_code
                     else "def senior():\n    pass")
            return code1, code2, "python", "junior.py", "senior.py"

        checked = [f for f in files if f.checked]
        if not checked:
            c, l, t = self._get_code(config, files, custom_code)
            return c, c, l, t, t

        it = checked[0]
        if Path(it.path).suffix.lower() == ".json":
            try:
                with open(it.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                code1 = convert_shortcodes(data.get("junior_code", ""))
                code2 = convert_shortcodes(data.get("senior_code", ""))
                lang = data.get("language", "python")
                title = data.get("title", Path(it.path).name)
                if not code1.strip():
                    code1 = "# Junior code missing in JSON"
                if not code2.strip():
                    code2 = "# Senior code missing in JSON"
                return (self._clamp(code1), self._clamp(code2), lang,
                        f"{title} (Junior)", f"{title} (Senior)")
            except Exception:
                logger.warning("JSON pair unreadable: %s — falling back",
                               it.path)

        if len(checked) >= 2:
            code1 = self._clamp(read_text_file(checked[0].path,
                                               config.txt_clean))
            code2 = self._clamp(read_text_file(checked[1].path,
                                               config.txt_clean))
            return (code1, code2,
                    detect_language(checked[0].path),
                    Path(checked[0].path).name,
                    Path(checked[1].path).name)

        c, l, t = self._get_code(config, files, custom_code)
        return c, c, l, t, t

    def build_refactor_string(self, jr, sr):
        sm = difflib.SequenceMatcher(None, jr, sr)
        timeline = ""
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == 'equal':
                timeline += jr[i1:i2]
            elif tag == 'replace':
                timeline += jr[i1:i2] + PAUSE_TOKEN * 3
                timeline += '\b' * len(jr[i1:i2]) + PAUSE_TOKEN * 2 \
                    + sr[j1:j2]
            elif tag == 'delete':
                timeline += jr[i1:i2] + PAUSE_TOKEN * 3 \
                    + '\b' * len(jr[i1:i2])
            elif tag == 'insert':
                timeline += PAUSE_TOKEN * 2 + sr[j1:j2]
        return timeline

    def build_panes(self, config, files, custom_code):
        w, h = self._output_size(config)
        gap = 20
        code1, code2, lang, t1, t2 = self.get_codes(config, files,
                                                    custom_code)

        if config.jr_diff_mode:
            refactor = self.build_refactor_string(code1, code2)
            title = f"Refactoring: {t1} → {t2}"
            animator = self._make_animator(refactor, config.jr_wpm)
            renderer = self._make_renderer(config, w, h, refactor, title,
                                           lang, 0)
            return MultiPaneRenderer([(renderer, animator, title)],
                                     w, h, 1, "Single", config=config)

        rects = MultiPaneRenderer.compute_pane_rects(w, h, 2,
                                                     config.layout_jr,
                                                     gap, config)
        if getattr(config, "sync_mw", False):
            d1 = TypingAnimator.estimate_duration(code1, config.jr_wpm)
            d2 = TypingAnimator.estimate_duration(code2, config.sr_wpm)
            finish = max(d1, d2)
            delay1 = max(0.0, finish - d1)
            delay2 = max(0.0, finish - d2)
            a1 = TypingAnimator(code1, TypingProfile(
                wpm=config.jr_wpm, start_pause=delay1 + OVERHEAD_MIN,
                end_pause=OVERHEAD_MAX))
            a2 = TypingAnimator(code2, TypingProfile(
                wpm=config.sr_wpm, start_pause=delay2 + OVERHEAD_MIN,
                end_pause=OVERHEAD_MAX))
        else:
            a1 = self._make_animator(code1, config.jr_wpm)
            a2 = self._make_animator(code2, config.sr_wpm)
        r1 = self._make_renderer(config, rects[0].width(),
                                 rects[0].height(), code1, t1, lang, 0)
        r2 = self._make_renderer(config, rects[1].width(),
                                 rects[1].height(), code2, t2, lang, 1)
        return MultiPaneRenderer(
            [(r1, a1, f"👶 Junior — {t1}"), (r2, a2, f"🧓 Senior — {t2}")],
            w, h, 2, config.layout_jr, gap=gap, config=config)


class JrVsSrTab(BaseModeTab):
    TAB_LABEL = "Junior vs Senior"
    MODE = StudioMode.JR_VS_SR
    WPM_SPINBOX_ATTR = "jr_wpm_sp"
    WIRING = [
        ("jr_diff_mode_chk", "jr_diff_mode",    "check"),
        ("jr_font_cb",       "font_jr",         "combo"),
        ("jr_font_sz_auto",  "font_sz_auto_jr", "check"),
        ("jr_font_sz_sp",    "font_sz_jr",      "spin"),
        ("sr_font_cb",       "font_sr",         "combo"),
        ("sr_font_sz_auto",  "font_sz_auto_sr", "check"),
        ("sr_font_sz_sp",    "font_sz_sr",      "spin"),
        ("jr_layout_cb",     "layout_jr",       "combo"),
        ("jr_wpm_sp",        "jr_wpm",          "spin"),
        ("sr_wpm_sp",        "sr_wpm",          "spin"),
        ("jr_sound_cb",      "jr_sound",        "combo"),
        ("sr_sound_cb",      "sr_sound",        "combo"),
        ("jr_custom_editor", "jr_custom_code",  "text"),
        ("sr_custom_editor", "sr_custom_code",  "text"),
        ("jr_cursor_chk",    "show_cursor",     "check"),
        ("bgm_chk",         "bgm_enabled",      "check"),
        ("bgm_cb",          "bgm_source",       "combo_data"),
        ("bgm_vol_sp",      "bgm_volume",       "spin"),
    ]

    def build_ui(self):
        fl = self.add_settings_group("Junior vs Senior Settings")

        self.mw.jr_diff_mode_chk = QCheckBox(
            "Diff Animation (Transform Jr → Sr)")
        self.mw.jr_diff_mode_chk.toggled.connect(
            self._update_diff_mode_visibility)
        fl.addRow(self.mw.jr_diff_mode_chk)

        font_cb_jr, fs_row_jr = create_font_controls("jr", self.mw)
        fl.addRow("Junior Font:", font_cb_jr)
        fl.addRow("Junior Size:", fs_row_jr)
        font_cb_sr, fs_row_sr = create_font_controls("sr", self.mw)
        fl.addRow("Senior Font:", font_cb_sr)
        fl.addRow("Senior Size:", fs_row_sr)

        self.mw.jr_layout_cb = QComboBox()
        self.mw.jr_layout_cb.addItems(JR_VS_SR_LAYOUTS)
        fl.addRow("Layout:", self.mw.jr_layout_cb)

        jw = QHBoxLayout()
        jw.setContentsMargins(0, 0, 0, 0)
        self.mw.jr_wpm_sp = self.create_wpm_spinbox(default=90)
        jw.addWidget(self.mw.jr_wpm_sp)
        fl.addRow("Junior WPM:", jw)
        sw = QHBoxLayout()
        sw.setContentsMargins(0, 0, 0, 0)
        self.mw.sr_wpm_sp = self.create_wpm_spinbox(default=130)
        sw.addWidget(self.mw.sr_wpm_sp)
        fl.addRow("Senior WPM:", sw)

        self.add_quick_target(fl)

        self.mw.jr_sound_cb = QComboBox()
        self.mw.jr_sound_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        fl.addRow("Junior Sound:", self.mw.jr_sound_cb)
        self.mw.sr_sound_cb = QComboBox()
        self.mw.sr_sound_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        fl.addRow("Senior Sound:", self.mw.sr_sound_cb)

        self.mw.jr_cursor_chk = QCheckBox("Show Typing Cursor")
        fl.addRow(self.mw.jr_cursor_chk)

        custom_grp = QGroupBox("Dual Custom Code (Overrides JSON/File)")
        cl = QVBoxLayout(custom_grp)
        cl.setSpacing(4)
        cl.addWidget(QLabel("Junior Code:"))
        self.mw.jr_custom_editor = QPlainTextEdit()
        self.mw.jr_custom_editor.setMaximumHeight(150)
        self.mw.jr_custom_editor.setPlaceholderText("def junior():\n    ...")
        cl.addWidget(self.mw.jr_custom_editor)
        cl.addWidget(QLabel("Senior Code:"))
        self.mw.sr_custom_editor = QPlainTextEdit()
        self.mw.sr_custom_editor.setMaximumHeight(150)
        self.mw.sr_custom_editor.setPlaceholderText("def senior():\n    ...")
        cl.addWidget(self.mw.sr_custom_editor)
        self.add_custom_widget(custom_grp)

        self.add_bgm_controls(fl)

        self.finalize_layout()
        self.wire()
        self.attach_duration_label("jr_wpm_sp", jw)
        self.mw.sr_wpm_sp.valueChanged.connect(
            lambda *_: self._est_timer.start())
        self.mw.jr_diff_mode_chk.toggled.connect(
            lambda *_: self._est_timer.start())
        self._refresh_estimate()

    def _update_diff_mode_visibility(self, checked):
        for w in (self.mw.jr_layout_cb, self.mw.sr_wpm_sp,
                  self.mw.sr_font_cb, self.mw.sr_font_sz_auto,
                  self.mw.sr_font_sz_sp, self.mw.sr_sound_cb):
            w.setEnabled(not checked)

    def load_settings(self, config):
        self.load(config)
        self._update_diff_mode_visibility(config.jr_diff_mode)

    def _compute_estimate(self):
        if not hasattr(self, "_dur_lbl"):
            return
        try:
            s = self.mw.strategies[StudioMode.JR_VS_SR]
            code1, code2, *_ = s.get_codes(
                self.mw.config, self.mw._items, self.mw.config.custom_code)
            if self.mw.config.jr_diff_mode:
                refactor = s.build_refactor_string(code1, code2)
                d = estimate_duration_cached(
                    refactor, self.mw.jr_wpm_sp.value(),
                    OVERHEAD_MIN, OVERHEAD_MAX)
                self._dur_lbl.setText(
                    f"≈ {format_duration(d)}  (refactor)")
            else:
                d1 = estimate_duration_cached(
                    code1, self.mw.jr_wpm_sp.value(),
                    OVERHEAD_MIN, OVERHEAD_MAX)
                d2 = estimate_duration_cached(
                    code2, self.mw.sr_wpm_sp.value(),
                    OVERHEAD_MIN, OVERHEAD_MAX)
                self._dur_lbl.setText(
                    f"Jr ≈ {format_duration(d1)} · "
                    f"Sr ≈ {format_duration(d2)}")
        except Exception:
            pass

    def apply_target_duration(self, secs):
        def solve():
            s = self.mw.strategies[StudioMode.JR_VS_SR]
            code1, code2, *_ = s.get_codes(
                self.mw.config, self.mw._items,
                self.mw.config.custom_code)
            if self.mw.config.jr_diff_mode:
                code1 = s.build_refactor_string(code1, code2)
            self.mw.jr_wpm_sp.setValue(
                find_wpm_cached(code1, secs, OVERHEAD_MIN, OVERHEAD_MAX))
            self.mw.sr_wpm_sp.setValue(
                find_wpm_cached(code2, secs, OVERHEAD_MIN, OVERHEAD_MAX))
        self._solve_with_cursor(solve)


class JrVsSrWindow(StudioMainWindow):
    WINDOW_TITLE = "Typing Video Studio — Junior vs Senior"
    STRATEGIES = {StudioMode.JR_VS_SR: JrVsSrStrategy()}
    MODE_LOG_NAME = "jr_vs_sr"
    DEMO_FILES = {"demo_jr_sr.json": json.dumps({
        "title": "refactor_example",
        "language": "python",
        "junior_code": DEMO_JR,
        "senior_code": DEMO_SR,
    }, indent=2)}
    FILE_PANEL_TITLE = "Input: JSON Pair or Two Files"
    FILE_PANEL_MAX = 2
    FILE_PANEL_FILTER = ("Junior/Senior (*.json *.py *.pyw *.js *.ts "
                         "*.java *.kt *.c *.cpp *.cs *.go *.rs *.rb "
                         "*.php)")
    FILE_PANEL_HINT = ("One .json with junior_code/senior_code keys — or "
                       "two files in order (1st = Junior, 2nd = Senior). "
                       "Order matters; only the first two checked files "
                       "are used.")
    FILE_PANEL_STRICT_ORDER = True

    def make_tabs(self):
        return [JrVsSrTab(self)]

    def demo_content(self):
        return "demo_jr_sr.json", "def junior():\n    pass"


register_mode("jr", JrVsSrStrategy, JrVsSrTab, JrVsSrWindow)

if __name__ == "__main__":
    run_studio(JrVsSrWindow)