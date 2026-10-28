"""Settings, voice configuration, diagnostics, and privacy dialog for JARVIS."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QTabWidget,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from jarvis.config import config
from jarvis.llm.ollama_client import OllamaClient, test_ai_connection
from jarvis.storage.memory import memory_manager
from jarvis.voice.diagnostics import get_audio_input_devices, get_tts_voices, test_microphone_capture, run_full_voice_diagnostics
from jarvis.core.events import bus


class SettingsDialog(QDialog):
    """Configuration dialog for models, voice hardware, memory inspection, and diagnostics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS - Settings & Diagnostics")
        self.resize(650, 580)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #F8FAFC;
            }
            QTabWidget::pane {
                border: 1px solid #1E293B;
                border-radius: 8px;
                background-color: #111827;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #1E293B;
                color: #94A3B8;
                padding: 8px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: #111827;
                color: #00E5FF;
                border-bottom: 2px solid #00E5FF;
            }
            QGroupBox {
                border: 1px solid #1E293B;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                color: #00E5FF;
            }
            QLabel {
                color: #E2E8F0;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #1E293B;
                border: 1px solid #38BDF8;
                border-radius: 6px;
                padding: 6px 14px;
                color: #F8FAFC;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #0284C7;
            }
            QTableWidget {
                background-color: #0B0F19;
                border: 1px solid #1E293B;
                gridline-color: #1E293B;
                color: #F8FAFC;
                border-radius: 6px;
            }
            QHeaderView::section {
                background-color: #162032;
                color: #38BDF8;
                padding: 4px;
                border: 1px solid #1E293B;
                font-weight: bold;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        self.tabs = QTabWidget(self)

        # ----------------- Tab 1: General & LLM -----------------
        general_tab = QWidget()
        gen_layout = QVBoxLayout(general_tab)
        gen_layout.setSpacing(12)

        ollama_group = QGroupBox("Ollama LLM Configuration")
        form_ollama = QFormLayout(ollama_group)

        self.url_edit = QLineEdit(config.ollama.base_url)
        form_ollama.addRow("API Base URL:", self.url_edit)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItem(config.ollama.model)
        for fb in config.ollama.fallback_models:
            if fb != config.ollama.model:
                self.model_combo.addItem(fb)
        form_ollama.addRow("Active Model:", self.model_combo)

        test_ai_btn = QPushButton("⚡ Test AI Connection (Ollama)")
        test_ai_btn.setToolTip("Verify Ollama daemon, model availability, and run live inference test.")
        test_ai_btn.clicked.connect(self._test_ollama)
        form_ollama.addRow("", test_ai_btn)

        gen_layout.addWidget(ollama_group)

        sec_group = QGroupBox("Security & Execution Policy")
        form_sec = QFormLayout(sec_group)
        sec_label = QLabel(
            "• Subprocess execution uses strictly allowlisted argument lists without shell wrappers.\n"
            "• Consequential actions (file deletion, changes) require explicit confirmation."
        )
        sec_label.setWordWrap(True)
        sec_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        form_sec.addRow(sec_label)

        gen_layout.addWidget(sec_group)
        gen_layout.addStretch(1)
        self.tabs.addTab(general_tab, "General & LLM")

        # ----------------- Tab 2: Voice & Speech Engine -----------------
        voice_tab = QWidget()
        voice_layout = QVBoxLayout(voice_tab)
        voice_layout.setSpacing(12)

        # Microphone Input Selection
        mic_group = QGroupBox("Microphone Hardware Selection")
        form_mic = QFormLayout(mic_group)

        self.mic_combo = QComboBox()
        self.input_devices = get_audio_input_devices()
        current_dev_idx = config.voice.input_device_index

        for dev in self.input_devices:
            is_def_str = " (Windows Default)" if dev["is_default"] else ""
            self.mic_combo.addItem(
                f"[{dev['index']}] {dev['name']} ({dev['channels']}ch, {dev['default_samplerate']}Hz){is_def_str}",
                userData=dev["index"],
            )
            if current_dev_idx == dev["index"]:
                self.mic_combo.setCurrentIndex(self.mic_combo.count() - 1)

        form_mic.addRow("Input Device:", self.mic_combo)

        test_mic_btn = QPushButton("🎤 Test Selected Microphone")
        test_mic_btn.clicked.connect(self._test_microphone)
        form_mic.addRow("", test_mic_btn)

        voice_layout.addWidget(mic_group)

        # Speech-to-Text Configuration
        stt_group = QGroupBox("Speech-To-Text (faster-whisper Local)")
        form_stt = QFormLayout(stt_group)

        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems([
            "base.en (Balanced Accuracy - Recommended)",
            "tiny.en (Fastest - Ultra-low Latency)",
            "small.en (High Accuracy)",
            "base (Multilingual)",
        ])
        # Match current model
        if "tiny" in config.voice.whisper_model:
            self.whisper_model_combo.setCurrentIndex(1)
        elif "small" in config.voice.whisper_model:
            self.whisper_model_combo.setCurrentIndex(2)
        elif config.voice.whisper_model == "base":
            self.whisper_model_combo.setCurrentIndex(3)
        else:
            self.whisper_model_combo.setCurrentIndex(0)
        form_stt.addRow("Whisper Model:", self.whisper_model_combo)

        self.vad_check = QCheckBox("Enable Voice Activity Detection (VAD) & Silence Trimming")
        self.vad_check.setChecked(config.voice.vad_enabled)
        form_stt.addRow("", self.vad_check)

        voice_layout.addWidget(stt_group)

        # Text-to-Speech Configuration
        tts_group = QGroupBox("Text-To-Speech (Natural Speech Delivery)")
        form_tts = QFormLayout(tts_group)

        self.voice_combo = QComboBox()
        self.installed_voices = get_tts_voices()
        for v in self.installed_voices:
            self.voice_combo.addItem(v["name"], userData=v["id"])
            if config.voice.tts_voice_id and config.voice.tts_voice_id == v["id"]:
                self.voice_combo.setCurrentIndex(self.voice_combo.count() - 1)
        form_tts.addRow("TTS Voice:", self.voice_combo)

        self.tts_rate_spin = QSpinBox()
        self.tts_rate_spin.setRange(100, 300)
        self.tts_rate_spin.setValue(config.voice.tts_rate)
        form_tts.addRow("Speaking Rate (WPM):", self.tts_rate_spin)

        self.tts_vol_spin = QSpinBox()
        self.tts_vol_spin.setRange(10, 100)
        self.tts_vol_spin.setValue(int(config.voice.tts_volume * 100))
        form_tts.addRow("Volume (%):", self.tts_vol_spin)

        test_tts_btn = QPushButton("🔊 Test Voice Output")
        test_tts_btn.clicked.connect(self._test_tts_voice)
        form_tts.addRow("", test_tts_btn)

        voice_layout.addWidget(tts_group)

        # Diagnostics button
        diag_btn_row = QHBoxLayout()
        btn_full_diag = QPushButton("🔍 Run Full Voice Diagnostics")
        btn_full_diag.clicked.connect(self._show_voice_diagnostics)
        diag_btn_row.addWidget(btn_full_diag)
        diag_btn_row.addStretch(1)
        voice_layout.addLayout(diag_btn_row)

        voice_layout.addStretch(1)
        self.tabs.addTab(voice_tab, "Voice & Speech")

        # ----------------- Tab 3: Memory & Privacy -----------------
        privacy_tab = QWidget()
        priv_layout = QVBoxLayout(privacy_tab)
        priv_layout.setSpacing(10)

        priv_banner = QLabel("🔒 Privacy Guarantee: All models, speech, and memories operate locally. No data leaves this device.")
        priv_banner.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        priv_layout.addWidget(priv_banner)

        mem_group = QGroupBox("User-Approved Memories (Persistent in SQLite)")
        mem_layout = QVBoxLayout(mem_group)

        self.table_memories = QTableWidget(0, 3)
        self.table_memories.setHorizontalHeaderLabels(["Memory Key", "Value", "Last Updated"])
        self.table_memories.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table_memories.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_memories.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table_memories.setSelectionBehavior(QTableWidget.SelectRows)
        mem_layout.addWidget(self.table_memories)

        mem_btn_row = QHBoxLayout()
        btn_refresh_mem = QPushButton("Refresh")
        btn_refresh_mem.clicked.connect(self._load_memories)
        mem_btn_row.addWidget(btn_refresh_mem)

        btn_del_mem = QPushButton("Delete Selected")
        btn_del_mem.clicked.connect(self._delete_selected_memory)
        mem_btn_row.addWidget(btn_del_mem)

        btn_purge_mem = QPushButton("Purge All Memories")
        btn_purge_mem.setStyleSheet("background-color: #7F1D1D; border: 1px solid #EF4444; color: #FCA5A5;")
        btn_purge_mem.clicked.connect(self._purge_all_memories)
        mem_btn_row.addWidget(btn_purge_mem)

        mem_layout.addLayout(mem_btn_row)
        priv_layout.addWidget(mem_group)

        hist_group = QGroupBox("Conversation Log Storage")
        hist_layout = QHBoxLayout(hist_group)
        hist_label = QLabel("Clear all logged conversation turns stored in local SQLite database.")
        hist_label.setStyleSheet("color: #94A3B8; font-size: 12px;")
        hist_layout.addWidget(hist_label, stretch=1)

        btn_clear_hist = QPushButton("Clear Database Logs")
        btn_clear_hist.setStyleSheet("background-color: #7F1D1D; border: 1px solid #EF4444; color: #FCA5A5;")
        btn_clear_hist.clicked.connect(self._clear_database_logs)
        hist_layout.addWidget(btn_clear_hist)

        priv_layout.addWidget(hist_group)
        self.tabs.addTab(privacy_tab, "Memory & Privacy")

        main_layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #0284C7; font-weight: bold;")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        main_layout.addLayout(btn_layout)

        # Load memories on dialog open
        self._load_memories()

    def _test_microphone(self) -> None:
        """Capture a brief sample on the selected microphone to verify levels."""
        dev_idx = self.mic_combo.currentData()
        res = test_microphone_capture(device_index=dev_idx, duration_seconds=0.6)
        if res["success"]:
            msg = (
                f"✅ Microphone Test Successful!\n\n"
                f"• Device Index: {res['device_index']}\n"
                f"• Sample Rate: {res['sample_rate']} Hz\n"
                f"• RMS Level: {res['rms_level']}\n"
                f"• Peak Amplitude: {res['peak_amplitude']}\n"
                f"• Status: {'Audio detected' if not res['is_silent'] else 'Silence detected (speak to test levels)'}"
            )
            QMessageBox.information(self, "Microphone Verified", msg)
        else:
            QMessageBox.warning(self, "Microphone Test Failed", f"❌ {res['message']}")

    def _test_tts_voice(self) -> None:
        """Play a quick voice sample with the selected settings."""
        voice_id = self.voice_combo.currentData()
        rate = self.tts_rate_spin.value()
        try:
            import pyttsx3
            engine = pyttsx3.init()
            if voice_id:
                engine.setProperty("voice", voice_id)
            engine.setProperty("rate", rate)
            engine.say("Greetings. JARVIS voice engine test complete. All speech systems are functioning normally.")
            engine.runAndWait()
        except Exception as exc:
            QMessageBox.warning(self, "TTS Error", f"Could not play test speech: {exc}")

    def _show_voice_diagnostics(self) -> None:
        """Display full voice diagnostics summary."""
        diag = run_full_voice_diagnostics()
        summary = (
            f"🔍 VOICE SUBSYSTEM DIAGNOSTICS\n"
            f"Generated: {diag['timestamp']}\n\n"
            f"• Available Input Devices: {diag['input_devices_count']}\n"
            f"• Selected Mic Index: {diag['selected_device_index']}\n"
            f"• STT Engine: {diag['stt_engine']} ({diag['stt_model']})\n"
            f"• TTS Engine: {diag['tts_engine']} (Rate: {diag['tts_rate']} WPM)\n"
            f"• Installed TTS Voices: {diag['tts_voices_count']}\n\n"
            f"Hardware Capture Test: {diag['mic_capture_test']['message']}"
        )
        QMessageBox.information(self, "Voice Diagnostics Report", summary)

    def _load_memories(self) -> None:
        """Load stored facts into table."""
        facts = memory_manager.list_all_facts()
        self.table_memories.setRowCount(len(facts))
        for row, f in enumerate(facts):
            item_key = QTableWidgetItem(f["key"])
            item_val = QTableWidgetItem(f["value"])
            item_date = QTableWidgetItem(f["updated_at"])

            item_key.setFlags(item_key.flags() ^ Qt.ItemIsEditable)
            item_val.setFlags(item_val.flags() ^ Qt.ItemIsEditable)
            item_date.setFlags(item_date.flags() ^ Qt.ItemIsEditable)

            self.table_memories.setItem(row, 0, item_key)
            self.table_memories.setItem(row, 1, item_val)
            self.table_memories.setItem(row, 2, item_date)

    def _delete_selected_memory(self) -> None:
        """Delete currently selected row from SQLite."""
        selected = self.table_memories.currentRow()
        if selected < 0:
            QMessageBox.information(self, "No Selection", "Please select a memory to delete.")
            return

        key_item = self.table_memories.item(selected, 0)
        if not key_item:
            return

        key = key_item.text()
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete memory '{key}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            memory_manager.delete_fact(key)
            self._load_memories()

    def _purge_all_memories(self) -> None:
        """Purge all facts after confirmation."""
        confirm = QMessageBox.warning(
            self,
            "Confirm Purge",
            "This will permanently delete all user memories. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            count = memory_manager.clear_all_facts()
            self._load_memories()
            QMessageBox.information(self, "Purged", f"Deleted {count} stored memories.")

    def _clear_database_logs(self) -> None:
        """Clear conversation history table."""
        confirm = QMessageBox.warning(
            self,
            "Confirm Clear Logs",
            "This will delete all saved conversation transcripts from the local SQLite database. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            count = memory_manager.clear_history()
            QMessageBox.information(self, "Cleared", f"Cleared {count} stored conversation turns.")

    def _test_ollama(self) -> None:
        target_url = self.url_edit.text().strip()
        target_model = self.model_combo.currentText().strip()
        result = test_ai_connection(base_url=target_url, model=target_model)

        if result["success"]:
            self.model_combo.clear()
            for m in result.get("available_models", []):
                self.model_combo.addItem(m)
            self.model_combo.setCurrentText(result["model"])

            sample = result.get("sample_response", "")
            sample_str = f"\n\nModel Verification Response:\n\"{sample}\"" if sample else ""

            QMessageBox.information(
                self,
                "AI Connection Verified",
                f"✅ {result['message']}{sample_str}",
            )
        else:
            QMessageBox.warning(
                self,
                "AI Connection Failed",
                f"❌ {result['message']}",
            )

    def _save_settings(self) -> None:
        # LLM Settings
        config.ollama.base_url = self.url_edit.text().strip()
        config.ollama.model = self.model_combo.currentText().strip()

        # Voice Input & STT Settings
        config.voice.input_device_index = self.mic_combo.currentData()
        config.voice.vad_enabled = self.vad_check.isChecked()

        whisper_idx = self.whisper_model_combo.currentIndex()
        if whisper_idx == 1:
            config.voice.whisper_model = "tiny.en"
        elif whisper_idx == 2:
            config.voice.whisper_model = "small.en"
        elif whisper_idx == 3:
            config.voice.whisper_model = "base"
        else:
            config.voice.whisper_model = "base.en"

        # TTS Settings
        config.voice.tts_voice_id = self.voice_combo.currentData()
        config.voice.tts_rate = self.tts_rate_spin.value()
        config.voice.tts_volume = self.tts_vol_spin.value() / 100.0

        bus.ollama_status_changed.emit(True, config.ollama.model)
        self.accept()
