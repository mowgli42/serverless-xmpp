# PyInstaller spec for serverless-xmpp distribution bundle.
# Run via: scripts/build-release.sh

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parents[1]

block_cipher = None

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        (str(ROOT / "src" / "xmpp_p2p_chat" / "share" / "addressbook.json"), "xmpp_p2p_chat/share"),
        (str(ROOT / "web_ui" / "dist"), "web_ui/dist"),
    ],
    hiddenimports=[
        "xmpp_p2p_chat.connection_service",
        "xmpp_p2p_chat.text_ui",
        "textual",
        "slixmpp",
        "zeroconf",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="xmpp-p2p-chat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
