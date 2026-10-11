#!/usr/bin/env python3
"""
Unified window: file batch + global settings (Video/Audio/Keyboard/Custom)
+ all four modes in one window. Batch export with per-file auto-WPM,
live batch progress (frame-level), and per-item status column.

Run:  python unified_main.py   or   python studio.py all
"""
import wave
import io
from studio_lib import *
import code_yt_mode, text_emoji_mode, multi_window_mode, jr_vs_sr_mode

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMenu, QPlainTextEdit, QPushButton,
                               QSplitter, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget,
                               QInputDialog)


class UnifiedStudioWindow(StudioMainWindow):
    WINDOW_TITLE = "Unified Typing Video Studio"
    STRATEGIES = {
        StudioMode.MULTI_WINDOW: multi_window_mode.MultiWindowStrategy(),
        StudioMode.JR_VS_SR:     jr_vs_sr_mode.JrVsSrStrategy(),
        StudioMode.CODE_YT:      code_yt_mode.CodeYTStrategy(),
        StudioMode.TEXT_EMOJI:   text_emoji_mode.TextEmojiStrategy(),
    }
    MODE_LOG_NAME = "unified"
    SETTINGS_MIN_W, SETTINGS_MAX_W = 460, 620
    TAB_ORDER = [StudioMode.MULTI_WINDOW, StudioMode.JR_VS_SR,
                 StudioMode.CODE_YT, StudioMode.TEXT_EMOJI]

    def make_tabs(self):
        return [multi_window_mode.MultiWindowTab(self),
                jr_vs_sr_mode.JrVsSrTab(self),
                code_yt_mode.CodeYTTab(self),
                text_emoji_mode.TextEmojiTab(self)]

    def build_main_splitter(self):
        """Three-part settings column: file batch on top, global tabs +
        mode tabs below. The batch table supersedes the per-mode file
        panel (intentionally not created here — dropEvent handles it)."""
        container = QSplitter(Qt.Orientation.Vertical)
        container.addWidget(self._build_batch_panel())
        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        self.global_tabs = QTabWidget()
        self.global_tabs.addTab(self._build_video_tab(), "Video")
        self.global_tabs.addTab(self._build_audio_tab(), "Audio")
        self.global_tabs.addTab(self._build_keyboard_tab(), "Keyboard")
        self.global_tabs.addTab(self._build_custom_tab(), "Custom")
        wl.addWidget(self.global_tabs)
        wl.addWidget(self.mode_tabs)
        container.addWidget(wrap)
        container.setSizes([220, 480])
        container.setStretchFactor(1, 1)
        return container

    def demo_content(self):
        return None, "print('Add files above, or enable Custom Code.')"

    def _set_cfg(self, key, value, rerender=False):
        """All global-tab writes go through here so the auto-save timer
        fires (crash-safe) and rerender is explicit."""
        setattr(self.config, key, value)
        self._save_timer.start()
        if rerender:
            self._debounce_timer.start()

    def _post_load_settings(self):
        c = self.config
        self.theme_cb.setCurrentText(c.theme)
        self.res_cb.setCurrentText(c.resolution)
        self.fps_sp.setValue(c.fps)
        self.encoder_cb.setCurrentText(c.encoder)
        self.yt_extras_chk.setChecked(c.yt_extras)
        self.gen_metadata_chk.setChecked(c.gen_metadata)
        self.output_template_edit.setText(c.output_template)
        self.sound_chk.setChecked(c.sound_enabled)
        self.preset_cb.setCurrentText(c.sound_preset)
        self.stereo_chk.setChecked(c.stereo)
        self.vol_sp.setValue(c.volume)
        self.kb_enabled_chk.setChecked(c.kb_enabled)
        self.kb_layout_cb.setCurrentText(c.kb_layout)
        self.kb_position_cb.setCurrentText(c.kb_position)
        self.kb_opacity_sp.setValue(c.kb_opacity)
        self.use_custom_chk.setChecked(c.use_custom)
        self.custom_editor.setPlainText(c.custom_code)
        self.batch_auto_wpm_chk.setChecked(c.batch_auto_wpm)
        self.target_dur_sp.setValue(c.target_duration)
        self.cursor_chk.setChecked(c.show_cursor)
        if c.mode in self.TAB_ORDER:
            self.mode_tabs.setCurrentIndex(self.TAB_ORDER.index(c.mode))
        self._refresh_table()

    # ── file batch panel ─────────────────────────────────────────────────
    def _build_batch_panel(self):
        grp = QWidget()
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        for label, slot in [("🔄 Scan", self._scan_dir),
                            ("➕ Add", self._add_files),
                            ("✖ Clear", self._clear_list)]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btns.addWidget(b)
        btns.addStretch()
        self.batch_auto_wpm_chk = QCheckBox("Auto WPM per file")
        self.batch_auto_wpm_chk.setToolTip(
            "Solve WPM per file to hit Target Duration exactly.")
        btns.addWidget(self.batch_auto_wpm_chk)
        self.batch_auto_wpm_chk.toggled.connect(
            lambda v: self._set_cfg('batch_auto_wpm', v))
        lay.addLayout(btns)

        sel_row = QHBoxLayout()
        sel_row.setContentsMargins(0, 0, 0, 0)
        for label, slot in [("☑ All", lambda: self._set_all_checks(True)),
                            ("☐ None", lambda: self._set_all_checks(False)),
                            ("⇄ Invert", self._invert_checks)]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            sel_row.addWidget(b)
        sel_row.addWidget(QLabel("Match:"))
        self.batch_pattern_edit = QLineEdit()
        self.batch_pattern_edit.setPlaceholderText("*.py, chapter_*, *.md")
        self.batch_pattern_edit.setToolTip(
            "Comma-separated wildcards; Enter checks matching files only.")
        self.batch_pattern_edit.returnPressed.connect(self._check_matching)
        sel_row.addWidget(self.batch_pattern_edit, 1)
        go = QPushButton("Go")
        go.setFixedWidth(36)
        go.clicked.connect(self._check_matching)
        sel_row.addWidget(go)
        sel_row.addStretch()
        lay.addLayout(sel_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["", "File", "Status"])
        self.table.setSelectionBehavior(
            QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.resizeSection(0, 28)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.resizeSection(2, 130)
        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._table_context_menu)
        lay.addWidget(self.table, 1)

        dur = QHBoxLayout()
        dur.addWidget(QLabel("Target:"))
        self.target_dur_sp = QSpinBox()
        self.target_dur_sp.setRange(5, 7200)
        self.target_dur_sp.setValue(60)
        self.target_dur_sp.setSuffix("s")
        self.target_dur_sp.valueChanged.connect(
            lambda v: self._set_cfg('target_duration', v))
        dur.addWidget(self.target_dur_sp)
        self.batch_count_lbl = QLabel("0 / 0 files")
        self.batch_count_lbl.setStyleSheet(
            f"color: {CAT['subtext']}; font-size: 11px; min-width: 80px;")
        dur.addWidget(self.batch_count_lbl)
        self.batch_export_btn = QPushButton("🎬 Export Batch")
        self.batch_export_btn.setObjectName("primary")
        self.batch_export_btn.clicked.connect(self._start_batch_export)
        dur.addWidget(self.batch_export_btn)
        lay.addLayout(dur)
        return grp

    def _on_table_item_changed(self, item):
        row = item.row()
        if 0 <= row < len(self._items) and item.column() == 0:
            self._items[row].checked = (
                item.checkState() == Qt.CheckState.Checked)
            self._update_batch_count()
            self._debounce_timer.start()

    def _table_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        ext = Path(self._items[row].path).suffix.lower() or "(no ext)"
        menu = QMenu(self)
        act_load = menu.addAction("Load into Preview")
        act_solo = menu.addAction("Export This File Only")
        menu.addSeparator()
        act_ext = menu.addAction(f"Check all *{ext}")
        act_ext_off = menu.addAction(f"Uncheck all *{ext}")
        act_only_ext = menu.addAction(f"Check ONLY *{ext}")
        choice = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if choice == act_load:
            self._items = [FileItem(path=self._items[row].path,
                                    checked=True)]
            self._refresh_table()
            self._debounce_timer.start()
        elif choice == act_solo:
            for it in self._items:
                it.checked = False
            self._items[row].checked = True
            self._refresh_table()
            self._start_batch_export()
        elif choice == act_ext:
            for it in self._items:
                if Path(it.path).suffix.lower() == ext:
                    it.checked = True
            self._refresh_table()
        elif choice == act_ext_off:
            for it in self._items:
                if Path(it.path).suffix.lower() == ext:
                    it.checked = False
            self._refresh_table()
        elif choice == act_only_ext:
            for it in self._items:
                it.checked = Path(it.path).suffix.lower() == ext
            self._refresh_table()

    def _add_files(self):
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Files", str(CWD / "input"),
            f"Supported ({exts});;All Files (*)")
        added = 0
        known = {it.path for it in self._items}
        for p in paths:
            if p not in known:
                self._items.append(FileItem(path=p, checked=True))
                known.add(p)
                added += 1
        self._refresh_table()
        if added:
            self.statusBar().showMessage(f"Added {added} file(s)", 4000)
        self._debounce_timer.start()

    def _scan_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Scan Directory",
                                             str(CWD / "input"))
        if not d:
            return
        known = {it.path for it in self._items}
        added = 0
        for p in sorted(Path(d).rglob("*")):
            if (p.is_file()
                    and p.suffix.lower() in SUPPORTED_EXTENSIONS
                    and SCAN_SKIP_DIRS.isdisjoint(p.parts)
                    and str(p) not in known):
                self._items.append(FileItem(path=str(p), checked=True))
                known.add(str(p))
                added += 1
        self._refresh_table()
        self.statusBar().showMessage(
            f"Found {added} new file(s) in {d}", 5000)

    def _clear_list(self):
        self._items.clear()
        self._refresh_table()
        self._debounce_timer.start()

    def _set_all_checks(self, state: bool):
        for it in self._items:
            it.checked = state
        self._refresh_table()

    def _invert_checks(self):
        for it in self._items:
            it.checked = not it.checked
        self._refresh_table()

    def _check_matching(self, patterns_str: str = None):
        raw = (patterns_str if patterns_str is not None
               else self.batch_pattern_edit.text())
        patterns = [p.strip() for p in raw.split(",") if p.strip()]
        if not patterns:
            self._set_all_checks(False)
            return
        for it in self._items:
            name = Path(it.path).name.lower()
            it.checked = any(fnmatch.fnmatch(name, p.lower())
                             for p in patterns)
        self._refresh_table()
        n = sum(1 for it in self._items if it.checked)
        self.statusBar().showMessage(
            f"Checked {n} matching file(s)", 4000)

    def _update_batch_count(self):
        checked = sum(1 for it in self._items if it.checked)
        self.batch_count_lbl.setText(
            f"{checked} / {len(self._items)} files")
        if checked:
            total = 0.0
            for it in self._items:
                if not it.checked:
                    continue
                try:
                    code = read_text_file(it.path, self.config.txt_clean)
                except OSError:
                    continue
                wpm = it.wpm_override or self.config.wpm_yt
                total += estimate_duration_cached(
                    code, wpm, OVERHEAD_MIN, OVERHEAD_MAX,
                    is_text=(self.config.mode == StudioMode.TEXT_EMOJI))
            self.batch_count_lbl.setToolTip(
                f"Estimated output: {format_duration(total)} total "
                f"(+ render time)")
        else:
            self.batch_count_lbl.setToolTip("")

    def _refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._items))
        for r, it in enumerate(self._items):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                         | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if it.checked
                              else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, chk)
            self.table.setItem(r, 1, QTableWidgetItem(Path(it.path).name))
            self.table.setItem(r, 2, QTableWidgetItem(it.status))
        self.table.blockSignals(False)
        self._update_batch_count()

    # ── global tabs ──────────────────────────────────────────────────────
    def _form_tab(self):
        w = QWidget()
        fl = QFormLayout(w)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        return w, fl

    def _build_video_tab(self):
        w, fl = self._form_tab()
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(list(THEMES.keys()))
        self.theme_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('theme', v, rerender=True))
        fl.addRow("Theme:", self.theme_cb)
        self.res_cb = QComboBox()
        self.res_cb.addItems(list(RESOLUTIONS.keys()))
        self.res_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('resolution', v, rerender=True))
        fl.addRow("Resolution:", self.res_cb)
        self.fps_sp = QSpinBox()
        self.fps_sp.setRange(30, 60)
        self.fps_sp.setValue(30)
        self.fps_sp.valueChanged.connect(
            lambda v: self._set_cfg('fps', v))
        fl.addRow("FPS:", self.fps_sp)
        self.encoder_cb = QComboBox()
        self.encoder_cb.addItems(ENCODERS)
        self.encoder_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('encoder', v))
        fl.addRow("Encoder:", self.encoder_cb)
        self.yt_extras_chk = QCheckBox(
            "Generate YT Thumbnails (25/50/75%)")
        self.yt_extras_chk.setChecked(True)
        self.yt_extras_chk.toggled.connect(
            lambda v: self._set_cfg('yt_extras', v))
        fl.addRow(self.yt_extras_chk)
        self.gen_metadata_chk = QCheckBox("Generate YT Metadata (.txt)")
        self.gen_metadata_chk.setChecked(True)
        self.gen_metadata_chk.toggled.connect(
            lambda v: self._set_cfg('gen_metadata', v))
        fl.addRow(self.gen_metadata_chk)
        self.cursor_chk = QCheckBox("Show Typing Cursor (all modes)")
        self.cursor_chk.toggled.connect(
            lambda v: self._set_cfg('show_cursor', v, rerender=True))
        fl.addRow(self.cursor_chk)
        self.output_template_edit = QLineEdit(self.config.output_template)
        self.output_template_edit.setToolTip(
            "Placeholders: {name}, {date}, {lang}")
        self.output_template_edit.textChanged.connect(
            lambda v: self._set_cfg('output_template', v))
        fl.addRow("Output Name:", self.output_template_edit)
        return w

    def _build_audio_tab(self):
        w, fl = self._form_tab()
        self.sound_chk = QCheckBox(
            "Enable Typing Audio (muxed into export)")
        self.sound_chk.setChecked(True)
        self.sound_chk.toggled.connect(
            lambda v: self._set_cfg('sound_enabled', v))
        fl.addRow(self.sound_chk)
        self.preset_cb = QComboBox()
        self.preset_cb.addItems(list(MODULAR_SOUND_PRESETS.keys()))
        self.preset_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('sound_preset', v))
        fl.addRow("Preset:", self.preset_cb)
        self.stereo_chk = QCheckBox("Binaural ASMR (stereo pan)")
        self.stereo_chk.toggled.connect(
            lambda v: self._set_cfg('stereo', v))
        fl.addRow(self.stereo_chk)
        self.vol_sp = QSpinBox()
        self.vol_sp.setRange(0, 100)
        self.vol_sp.setValue(50)
        self.vol_sp.setSuffix("%")
        self.vol_sp.valueChanged.connect(
            lambda v: self._set_cfg('volume', v))
        fl.addRow("Volume:", self.vol_sp)
        test = QPushButton("🔊 Test Sound")
        test.setObjectName("primary")
        test.clicked.connect(self._test_sound)
        fl.addRow("Preview:", test)
        return w

    def _build_keyboard_tab(self):
        w, fl = self._form_tab()
        self.kb_enabled_chk = QCheckBox("Show Keyboard Overlay")
        self.kb_enabled_chk.toggled.connect(
            lambda v: self._set_cfg('kb_enabled', v, rerender=True))
        fl.addRow(self.kb_enabled_chk)
        self.kb_layout_cb = QComboBox()
        self.kb_layout_cb.addItems(list(KEYBOARD_LAYOUTS.keys()))
        self.kb_layout_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('kb_layout', v, rerender=True))
        fl.addRow("KB Layout:", self.kb_layout_cb)
        self.kb_position_cb = QComboBox()
        self.kb_position_cb.addItems(["Bottom Center", "Bottom Right",
                                      "Bottom Left", "Top Center",
                                      "Top Right", "Top Left"])
        self.kb_position_cb.currentTextChanged.connect(
            lambda v: self._set_cfg('kb_position', v, rerender=True))
        fl.addRow("KB Position:", self.kb_position_cb)
        self.kb_opacity_sp = QDoubleSpinBox()
        self.kb_opacity_sp.setRange(0.1, 1.0)
        self.kb_opacity_sp.setSingleStep(0.05)
        self.kb_opacity_sp.setValue(0.82)
        self.kb_opacity_sp.valueChanged.connect(
            lambda v: self._set_cfg('kb_opacity', v))
        fl.addRow("KB Opacity:", self.kb_opacity_sp)
        return w

    def _build_custom_tab(self):
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setContentsMargins(8, 8, 8, 8)
        self.use_custom_chk = QCheckBox(
            "Use Custom Code (ignores file list)")
        self.use_custom_chk.toggled.connect(
            lambda v: self._set_cfg('use_custom', v, rerender=True))
        vl.addWidget(self.use_custom_chk)
        self.custom_editor = QPlainTextEdit()
        self.custom_editor.setPlaceholderText(
            "Supports shortcodes: :rocket: → 🚀")
        self.custom_editor.textChanged.connect(
            lambda: (setattr(self.config, 'custom_code',
                             self.custom_editor.toPlainText()),
                     self._debounce_timer.start(),
                     self._save_timer.start()))
        vl.addWidget(self.custom_editor)
        return w

    # ── batch export ─────────────────────────────────────────────────────
    def _start_batch_export(self):
        checked = [it for it in self._items if it.checked]
        if not checked and not self.config.use_custom:
            self.statusBar().showMessage("No files checked.", 5000)
            return
        if self.config.batch_auto_wpm:
            QApplication.setOverrideCursor(
                Qt.CursorShape.WaitCursor)
            try:
                for it in checked:
                    code = read_text_file(it.path, self.config.txt_clean)
                    it.wpm_override = TypingAnimator.find_wpm_for_target(
                        code, self.config.target_duration,
                        OVERHEAD_MIN, OVERHEAD_MAX,
                        is_text=(self.config.mode
                                 == StudioMode.TEXT_EMOJI))
            finally:
                QApplication.restoreOverrideCursor()
        else:
            for it in checked:
                it.wpm_override = None
        self._refresh_table()      # count label now exact post-solve
        log_mode_event(self.log, "batch_export_start",
                       files=len(checked),
                       auto_wpm=self.config.batch_auto_wpm)
        self.export_manager.start(self._items)

    def _test_sound(self):
        try:
            sg = SimpleSoundGen(preset=self.config.sound_preset,
                                stereo=self.config.stereo)
            timestamps, t = [], 0.0
            for ch in "hello world 123":
                timestamps.append((t, ch))
                t += 0.10 if ch == ' ' else 0.06
            pcm = sg.generate_pcm(timestamps, self.config.volume / 100.0)
            buf = io.BytesIO()
            with wave.open(buf, "w") as wf:
                wf.setnchannels(2 if sg.stereo else 1)
                wf.setsampwidth(2)
                wf.setframerate(sg.sr)
                wf.writeframes(pcm.tobytes())
            self._play_buffer(buf.getvalue())
        except Exception as e:
            logger.error("Audio test failed", exc_info=True)
            self.statusBar().showMessage(f"Audio test failed: {e}", 5000)


if __name__ == "__main__":
    run_studio(UnifiedStudioWindow)