# PyInstaller spec for Windows
# Run from project root: pyinstaller build\captalk_windows.spec

block_cipher = None

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "captalk",
        "captalk.listener_windows",
        "captalk.hotkey",
        "captalk.tray",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "keyboard",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "captalk.listener_macos",
        "captalk.led_macos",
        "Quartz",
        "AppKit",
        "pyobjc",
    ],
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
    name="CapTalk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no cmd window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Request admin rights so the keyboard hook works reliably
    uac_admin=True,
)
