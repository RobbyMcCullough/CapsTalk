# PyInstaller spec for macOS
# Run from project root: pyinstaller build/captalk_macos.spec

a = Analysis(
    ["../main.py"],
    pathex=[".."],
    binaries=[],
    datas=[],
    hiddenimports=[
        # capstalk sub-modules imported dynamically (platform detection, tray)
        "capstalk",
        "capstalk.listener_macos",
        "capstalk.led_macos",
        "capstalk.hotkey",
        "capstalk.tray",
        # pynput always needs both platform backends bundled
        "pynput.keyboard._darwin",
        "pynput.mouse._darwin",
        # pyobjc frameworks used directly via ctypes / import
        "Quartz",
        "AppKit",
        # pystray macOS backend
        "pystray._darwin",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only modules — not needed on macOS
        "capstalk.listener_windows",
        "keyboard",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CapsTalk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # no terminal window
    argv_emulation=False,  # not a document-based app; no Finder file events needed
    target_arch=None,    # None = match build machine; set "universal2" for fat binary
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
    name="CapsTalk",
)

app = BUNDLE(
    coll,
    name="CapsTalk.app",
    icon="../assets/CapsTalk.icns",
    bundle_identifier="com.robbymccullough.capstalk",
    info_plist={
        "CFBundleName": "CapsTalk",
        "CFBundleDisplayName": "CapsTalk",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        # LSUIElement=1: run as an agent app — no Dock icon, no Cmd+Tab entry.
        # The only UI surface is the pystray menu-bar icon.
        "LSUIElement": "1",
        # Human-readable permission prompts shown by macOS when the user first
        # opens the app and macOS asks for the relevant access.
        "NSAppleEventsUsageDescription": "CapsTalk needs Accessibility access to intercept the Caps Lock key.",
        "NSAppleScriptEnabled": False,
    },
)
