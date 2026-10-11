#!/usr/bin/env python3
"""Entry point: Multi-Window comparison mode."""
import difflib
from studio_lib import *


def get_line_diffs(code1, code2):
    lines1, lines2 = code1.splitlines(), code2.splitlines()
    sm = difflib.SequenceMatcher(None, lines1, lines2)
    diffs1, diffs2 = {}, {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('replace', 'delete'):
            for i in range(i1, i2):
                diffs1[i] = 'removed'
        if tag in ('replace', 'insert'):
            for j in range(j1, j2):
                diffs2[j] = 'added'
    return diffs1, diffs2


class MultiWindowStrategy(BaseRenderStrategy):
    def build_panes(self, config, files, custom_code):
        w, h = self._output_size(config)
        n_panes = MULTI_WINDOW_LAYOUTS[config.layout_mw]
        gap = 20
        rects = MultiPaneRenderer.compute_pane_rects(w, h, n_panes, "Grid",
                                                     gap, config)
        codes = []
        checked = [] if config.use_custom else [f for f in files
                                                if f.checked]
        if not checked:
            c, l, t = self._get_code(config, files, custom_code)
            codes = [(c, l, t)] * n_panes
        else:
            for i in range(n_panes):
                if i < len(checked):
                    it = checked[i]
                    codes.append((self._clamp(
                        read_text_file(it.path, config.txt_clean)),
                        detect_language(it.path), Path(it.path).name))
                else:
                    codes.append(codes[0])
        diffs = [None] * n_panes
        if config.diff_highlight_mw and n_panes >= 2:
            for i in range(1, n_panes):
                d_prev, d_cur = get_line_diffs(codes[i - 1][0],
                                               codes[i][0])
                diffs[i - 1] = {**(diffs[i - 1] or {}), **d_prev}
                diffs[i] = {**(diffs[i] or {}), **d_cur}
        target = SHORTS_TARGET_SECS if config.shorts_mw else None
        panes = []
        if config.sync_mw:
            longest = max((c for c, _, _ in codes), key=len)
            base_dur = TypingAnimator.estimate_duration(longest,
                                                        config.wpm_mw)
            solve_to = min(base_dur, target) if target else base_dur
            wpm = find_wpm_cached(longest, solve_to - OVERHEAD_MIN,
                                  OVERHEAD_MIN, OVERHEAD_MAX)
            durations = [TypingAnimator.estimate_duration(c, wpm)
                         for c, _, _ in codes]
            finish_target = max(durations)
            for i, (code, lang, title) in enumerate(codes):
                delay = max(0.0, finish_target - durations[i])
                animator = TypingAnimator(code, TypingProfile(
                    wpm=wpm, start_pause=delay + OVERHEAD_MIN,
                    end_pause=OVERHEAD_MAX))
                renderer = self._make_renderer(
                    config, rects[i].width(), rects[i].height(),
                    code, title, lang, i, diffs[i])
                panes.append((renderer, animator, title))
        elif target:
            for i, (code, lang, title) in enumerate(codes):
                wpm = find_wpm_cached(code, target, OVERHEAD_MIN,
                                      OVERHEAD_MAX)
                panes.append((self._make_renderer(
                    config, rects[i].width(), rects[i].height(),
                    code, title, lang, i, diffs[i]),
                    self._make_animator(code, wpm), title))
        else:
            for i, (code, lang, title) in enumerate(codes):
                panes.append((self._make_renderer(
                    config, rects[i].width(), rects[i].height(),
                    code, title, lang, i, diffs[i]),
                    self._make_animator(code, config.wpm_mw), title))
        if n_panes == 3 and config.layout_mw == "Git Conflict (3-Pane)":
            git_titles = ["Base", "Incoming", "Resolved"]
            panes = [(r, a, f"{git_titles[i]} — {t}")
                     for i, (r, a, t) in enumerate(panes)]
        return MultiPaneRenderer(panes, w, h, n_panes, "Grid", gap=gap,
                                 config=config)


class MultiWindowTab(BaseModeTab):
    TAB_LABEL = "Multi-Window"
    MODE = StudioMode.MULTI_WINDOW
    WPM_SPINBOX_ATTR = "mw_wpm_sp"
    SHORTS_CHECK_ATTR = "mw_shorts_chk"
    WIRING = [
        ("mw_layout_cb",          "layout_mw",         "combo"),
        ("mw_font_cb",            "font_mw",           "combo"),
        ("mw_font_sz_auto",       "font_sz_auto_mw",   "check"),
        ("mw_font_sz_sp",         "font_sz_mw",        "spin"),
        ("mw_2_font_cb",          "font_mw_2",         "combo"),
        ("mw_2_font_sz_auto",     "font_sz_auto_mw_2", "check"),
        ("mw_2_font_sz_sp",       "font_sz_mw_2",      "spin"),
        ("mw_3_font_cb",          "font_mw_3",         "combo"),
        ("mw_3_font_sz_auto",     "font_sz_auto_mw_3", "check"),
        ("mw_3_font_sz_sp",       "font_sz_mw_3",      "spin"),
        ("mw_4_font_cb",          "font_mw_4",         "combo"),
        ("mw_4_font_sz_auto",     "font_sz_auto_mw_4", "check"),
        ("mw_4_font_sz_sp",       "font_sz_mw_4",      "spin"),
        ("mw_wpm_sp",             "wpm_mw",            "spin"),
        ("mw_shorts_chk",         "shorts_mw",         "check"),
        ("diff_highlight_mw_chk", "diff_highlight_mw", "check"),
        ("sync_mw_chk",           "sync_mw",           "check"),
        ("mw_ratio_sp",           "mw_ratio",          "spin"),
        ("mw_cursor_chk",         "show_cursor",       "check"),
        ("mw_sound_cb",           "sound_preset",      "combo"),
        ("bgm_chk",               "bgm_enabled",       "check"),
        ("bgm_cb",                "bgm_source",        "combo_data"),
        ("bgm_vol_sp",            "bgm_volume",        "spin"),
    ]

    def build_ui(self):
        fl = self.add_settings_group("Multi-Window Settings")
        self.mw.mw_layout_cb = QComboBox()
        self.mw.mw_layout_cb.addItems(list(MULTI_WINDOW_LAYOUTS.keys()))
        fl.addRow("Layout:", self.mw.mw_layout_cb)

        self.mw.mw_font_grp1 = create_font_group("mw", "Window 1 Font:", self.mw)
        self.mw.mw_font_grp2 = create_font_group("mw_2", "Window 2 Font:", self.mw)
        self.mw.mw_font_grp3 = create_font_group("mw_3", "Window 3 Font:", self.mw)
        self.mw.mw_font_grp4 = create_font_group("mw_4", "Window 4 Font:", self.mw)
        for grp in (self.mw.mw_font_grp1, self.mw.mw_font_grp2,
                    self.mw.mw_font_grp3, self.mw.mw_font_grp4):
            fl.addRow(grp)

        wpm_row = QHBoxLayout()
        wpm_row.setContentsMargins(0, 0, 0, 0)
        self.mw.mw_wpm_sp = self.create_wpm_spinbox(default=100)
        wpm_row.addWidget(self.mw.mw_wpm_sp)
        fl.addRow("WPM:", wpm_row)

        self.add_quick_target(fl)

        self.mw.diff_highlight_mw_chk = QCheckBox("Dynamic Diff Highlighting")
        self.mw.diff_highlight_mw_chk.setChecked(True)
        fl.addRow(self.mw.diff_highlight_mw_chk)
        self.mw.sync_mw_chk = QCheckBox("Synchronized Typing Completion")
        fl.addRow(self.mw.sync_mw_chk)
        self.mw.mw_cursor_chk = QCheckBox("Show Typing Cursor")
        fl.addRow(self.mw.mw_cursor_chk)

        self.mw.mw_sound_cb = QComboBox()
        self.mw.mw_sound_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        fl.addRow("SFX:", self.mw.mw_sound_cb)

        self.mw.mw_ratio_container = QWidget()
        rl = QHBoxLayout(self.mw.mw_ratio_container)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addWidget(QLabel("Pane Ratio:"))
        self.mw.mw_ratio_sp = QSpinBox()
        self.mw.mw_ratio_sp.setRange(10, 90)
        self.mw.mw_ratio_sp.setValue(50)
        self.mw.mw_ratio_sp.setSuffix("%")
        rl.addWidget(self.mw.mw_ratio_sp)
        rl.addStretch()
        fl.addRow(self.mw.mw_ratio_container)

        self.add_bgm_controls(fl)

        self.finalize_layout()
        self.mw.mw_layout_cb.setCurrentText(self.mw.config.layout_mw)
        self.mw.mw_layout_cb.currentIndexChanged.connect(
            lambda: (self.update_config(
                'layout_mw', self.mw.mw_layout_cb.currentText()),
                self._update_layout_visibility()))
        self._update_layout_visibility(render=False)
        self.wire()
        self.attach_duration_label("mw_wpm_sp", wpm_row)
        self._refresh_estimate()

    def _update_layout_visibility(self, render=True):
        n = MULTI_WINDOW_LAYOUTS.get(
            self.mw.mw_layout_cb.currentText(), 1)
        self.mw.mw_font_grp1.setVisible(n >= 1)
        self.mw.mw_font_grp2.setVisible(n >= 2)
        self.mw.mw_font_grp3.setVisible(n >= 3)
        self.mw.mw_font_grp4.setVisible(n >= 4)
        self.mw.diff_highlight_mw_chk.setVisible(n >= 2)
        self.mw.sync_mw_chk.setVisible(n >= 2)
        self.mw.mw_ratio_container.setVisible(n == 2)
        if render and not self.mw._loading:
            self.mw._debounce_timer.start()

    def load_settings(self, config):
        self._loading = True
        try:
            self.load(config)
            self._update_layout_visibility(render=False)
        finally:
            self._loading = False

    def apply_target_duration(self, secs):
        def solve():
            checked = [f for f in self.mw._items if f.checked]
            if self.mw.config.use_custom or not checked:
                longest, _, _ = self.mw.strategies[
                    StudioMode.MULTI_WINDOW]._get_code(
                    self.mw.config, self.mw._items,
                    self.mw.config.custom_code)
            else:
                longest = max(
                    (read_text_file(it.path, self.mw.config.txt_clean)
                     for it in checked), key=len, default="")
            self.mw.mw_wpm_sp.setValue(
                find_wpm_cached(longest, secs, OVERHEAD_MIN, OVERHEAD_MAX))
        self._solve_with_cursor(solve)


class MultiWindowStudio(StudioMainWindow):
    WINDOW_TITLE = "Typing Video Studio — Multi-Window"
    STRATEGIES = {StudioMode.MULTI_WINDOW: MultiWindowStrategy()}
    MODE_LOG_NAME = "multi_window"
    DEMO_FILES = {
        "demo_a.py": "def add(a, b):\n    return a + b\n",
        "demo_b.py": ("def add(a: float, b: float) -> float:\n"
                      '    """Sum two numbers."""\n'
                      "    return a + b\n")}
    FILE_PANEL_TITLE = "Input Files (per Pane)"
    FILE_PANEL_MAX = 4
    FILE_PANEL_FILTER = ("Code (*.py *.pyw *.js *.mjs *.jsx *.ts *.tsx "
                         "*.java *.kt *.c *.h *.cpp *.cs *.go *.rs *.rb "
                         "*.php *.swift *.sh *.md)")
    FILE_PANEL_HINT = ("Checked files fill panes in list order "
                       "(top = pane 1). Uncheck to exclude. Fewer files "
                       "than panes repeats the first. Drag-drop up to 4 "
                       "files at once.")

    def make_tabs(self):
        return [MultiWindowTab(self)]

    def demo_content(self):
        return "demo_a.py", "# Compare code across panes\nprint('Hello')\n"


register_mode("multi", MultiWindowStrategy, MultiWindowTab, MultiWindowStudio)

if __name__ == "__main__":
    run_studio(MultiWindowStudio)