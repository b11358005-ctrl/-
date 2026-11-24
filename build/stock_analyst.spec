# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Stock Multi-Agent Desktop (.exe / .app)."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve().parent

hidden_imports = (
    collect_submodules("yfinance")
    + collect_submodules("pydantic")
    + collect_submodules("cryptography")
    + collect_submodules("ddgs")
    + ["feedparser", "bs4", "markdown", "httpx"]
)

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StockMultiAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# macOS .app bundle configuration
app = BUNDLE(
    exe,
    name="StockMultiAgent.app",
    icon=None,
    bundle_identifier="com.alphapulse.stockmultiagent",
)
