<div align="center">
  <img src="logos/capstalk-banner.png" alt="CapsTalk — Keybind Dictation Tool" width="480">

  <p>Repurpose your <strong>Caps Lock key</strong> as a push-to-talk trigger for AI dictation apps like&nbsp;<a href="https://wisprflow.ai">Wispr&nbsp;Flow</a>.</p>

  <p>
    <img src="https://img.shields.io/badge/macOS-10.15%2B-1a3a5c?style=flat-square&logo=apple&logoColor=white" alt="macOS">
    <img src="https://img.shields.io/badge/Windows-10%2B-1a3a5c?style=flat-square&logo=windows&logoColor=white" alt="Windows">
    <img src="https://img.shields.io/badge/Python-3.9%2B-1a3a5c?style=flat-square&logo=python&logoColor=white" alt="Python">
  </p>
</div>

---

## What it does

| Gesture | Action |
|---|---|
| **Hold** Caps Lock | Sends your configured hotkey down → starts recording |
| **Release** Caps Lock | Releases the hotkey → stops recording |
| **Double-tap** Caps Lock | Toggles real Caps Lock on/off |
| **Caps Lock LED** *(MacBook)* | Lights up while recording, off while idle |

Your voice app sees the hotkey exactly as if you'd held it on the keyboard — CapsTalk just gets out of the way.

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Grant permissions (macOS)

CapsTalk intercepts keyboard input at the system level and needs two permissions granted to **Terminal** (or whichever app runs Python):

> **System Settings → Privacy & Security → Accessibility** — add Terminal / Python
> **System Settings → Privacy & Security → Input Monitoring** — add Terminal / Python

### 3. Configure your dictation app

Set your dictation app's push-to-talk hotkey to match `RECORD_KEY` in `config.py`.
The default is **`Cmd + Option + R`** — set that as the hold-to-record shortcut in Wispr Flow (or your app of choice).

### 4. Run

```bash
python3 main.py
```

To stop, use the **tray icon → Quit** or press `Ctrl+C` in the terminal. Either way, your Caps Lock key is restored automatically.

---

## Configuration

All settings are in `config.py`:

```python
# The key or chord your dictation app listens for
RECORD_KEY = ["cmd", "alt", "r"]   # or a single key: "f18"

# How quickly you must double-tap for it to count (seconds)
DOUBLE_TAP_WINDOW = 0.4

# Mirror recording state to the Caps Lock LED (MacBook only)
CONTROL_LED = True

# Show a menu-bar icon with a Quit option
SHOW_TRAY_ICON = True
```

**Chord syntax:** any combination of pynput key names — `"cmd"`, `"alt"`, `"ctrl"`, `"shift"`, `"f18"`, single characters, etc.

---

## How it works (macOS)

1. **hidutil remap** — on launch, Caps Lock is remapped to F13 at the USB HID driver level. The OS never sees a Caps Lock press, so it never toggles its internal state.
2. **CGEventTap** — a Quartz event tap intercepts every F13 keyDown/keyUp and suppresses it from reaching other apps.
3. **Push-to-talk** — on F13 keyDown, CapsTalk presses your configured hotkey via pynput; on keyUp, it releases it.
4. **Double-tap** — two F13 keyDowns within `DOUBLE_TAP_WINDOW` seconds triggers a real Caps Lock toggle via IOKit, bypassing the remap.
5. **Cleanup** — on exit (tray Quit, Ctrl+C, or terminal close), the hidutil remap is removed and your Caps Lock key returns to normal.

---

## Requirements

| Platform | Notes |
|---|---|
| **macOS** | Accessibility + Input Monitoring permissions required. LED control works on MacBooks; silently skipped on external keyboards that don't expose the LED via HID. |
| **Windows** | May require running as Administrator for the low-level keyboard hook to work across all apps. LED follows OS Caps Lock state (not independently controlled). |

---

## Project structure

```
CapsTalk/
├── main.py                   # Entry point, signal handling, wiring
├── config.py                 # All user settings
├── requirements.txt
├── capstalk/
│   ├── listener_macos.py     # hidutil remap + Quartz CGEventTap
│   ├── listener_windows.py   # WH_KEYBOARD_LL hook
│   ├── led_macos.py          # IOKit Caps Lock LED control
│   ├── hotkey.py             # pynput key/chord press & release
│   └── tray.py               # Menu-bar icon (pystray + Pillow)
└── build/
    ├── captalk_macos.spec    # PyInstaller — macOS .app
    └── captalk_windows.spec  # PyInstaller — Windows .exe
```

---

## Building a standalone app

**macOS:**
```bash
pip install pyinstaller
pyinstaller build/captalk_macos.spec
# → dist/CapsTalk.app
```

**Windows:**
```cmd
pip install pyinstaller
pyinstaller build\captalk_windows.spec
# → dist\CapsTalk.exe
```
