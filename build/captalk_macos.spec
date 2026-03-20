# PyInstaller spec for macOS
# Run from project root: pyinstaller build/captalk_macos.spec

block_cipher = None

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "captalk",
        "captalk.listener_macos",
        "captalk.led_macos",
        "captalk.hotkey",
        "captalk.tray",
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        "Quartz",
        "AppKit",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["captalk.listener_windows"],
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
    name="CapTalk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=True,
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
    name="CapTalk",
)

app = BUNDLE(
    coll,
    name="CapTalk.app",
    icon=None,  # replace with path to a .icns file when you have one
    bundle_identifier="com.captalk.app",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        # Required for Accessibility + Input Monitoring
        "NSAppleEventsUsageDescription": "CapTalk needs Accessibility access to intercept Caps Lock.",
        "com.apple.security.temporary-exception.apple-events": True,
    },
)
