# PyInstaller spec for Windows
# Run from project root: pyinstaller build\captalk_windows.spec

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[
        # capstalk sub-modules imported dynamically (platform detection, tray)
        "capstalk",
        "capstalk.listener_windows",
        "capstalk.hotkey",
        "capstalk.tray",
        # pynput always needs both platform backends bundled
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        # pystray Windows backend
        "pystray._win32",
        # low-level keyboard hook
        "keyboard",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # macOS-only modules — not needed on Windows
        "capstalk.listener_macos",
        "capstalk.led_macos",
        "Quartz",
        "AppKit",
        "pyobjc",
        "pyobjc_framework_Quartz",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Windows builds as a single self-contained .exe (no COLLECT/BUNDLE needed).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CapsTalk",
    icon="../assets/CapsTalk.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # no cmd window
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Request admin rights so the WH_KEYBOARD_LL hook works across all apps
    uac_admin=True,
)
