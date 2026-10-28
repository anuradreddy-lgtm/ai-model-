# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for building JARVIS AI Windows Executable."""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = []
hiddenimports = [
    "jarvis",
    "jarvis.config",
    "jarvis.core.state",
    "jarvis.core.events",
    "jarvis.llm.ollama_client",
    "jarvis.llm.prompts",
    "jarvis.conversation.manager",
    "jarvis.tools",
    "jarvis.tools.registry",
    "jarvis.tools.system_tools",
    "jarvis.tools.app_launcher",
    "jarvis.tools.browser_tools",
    "jarvis.tools.filesystem_tools",
    "jarvis.tools.notes_tools",
    "jarvis.tools.memory_tools",
    "jarvis.storage.db",
    "jarvis.storage.memory",
    "jarvis.voice.audio_capture",
    "jarvis.voice.stt",
    "jarvis.voice.tts",
    "jarvis.voice.wake_word",
    "jarvis.ui.theme",
    "jarvis.ui.main_window",
    "jarvis.ui.widgets.visualizer",
    "jarvis.ui.widgets.chat_view",
    "jarvis.ui.widgets.status_bar",
    "jarvis.ui.widgets.settings_dialog",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "win32com",
    "win32com.client",
    "pythoncom",
]

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JARVIS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed desktop application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JARVIS',
)
