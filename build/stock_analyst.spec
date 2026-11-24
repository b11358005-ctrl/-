# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Stock Multi-Agent Desktop (.exe / .app)."""

import importlib.util
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve().parent

hidden_imports = [
    "feedparser",
    "bs4",
    "markdown",
    "httpx",
    "sqlite3",
    "dotenv",
]
datas = []
binaries = []

for pkg in ("yfinance", "pydantic", "cryptography", "ddgs", "certifi", "curl_cffi", "primp", "lxml"):
    if importlib.util.find_spec(pkg) is not None:
        pkg_datas, pkg_bins, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_bins
        hidden_imports += pkg_hidden

for mod in ("markdown.extensions.tables", "markdown.extensions.fenced_code", "markdown.extensions.nl2br"):
    hidden_imports.append(mod)

hidden_imports += collect_submodules("src") if (PROJECT_ROOT / "src").exists() else []

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(dict.fromkeys(hidden_imports)),
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="StockMultiAgent.app",
        icon=None,
        bundle_identifier="com.alphapulse.stockmultiagent",
    )
