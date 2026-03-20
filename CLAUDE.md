# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Install dependencies
pip install -r requirements.txt

# Run (requires Accessibility + Input Monitoring permissions granted to Terminal/Python)
python main.py
```

macOS permissions required: **System Settings → Privacy & Security → Accessibility** and **Input Monitoring** — both must be granted to whichever binary runs the script (Terminal, Python, or a bundled app).

## Configuration

All user-facing settings live in `config.py` (not environment variables or CLI flags):

- `RECORD_KEY` — single key (`"f18"`) or chord list (`["cmd", "alt", "r"]`) sent to the voice app
- `DOUBLE_TAP_WINDOW` — seconds within which two taps count as a double-tap (default 0.4s)
- `CONTROL_LED` — whether to mirror recording state to the Caps Lock LED
- `CAPS_LOCK_DEBOUNCE` — defined but not currently used in event logic

## Architecture

```
main.py          — wires config → Listener → RecordHotkey + TrayIcon; owns signal handling
config.py        — all user-tunable constants
capstalk/
  listener_macos.py   — core macOS interception logic (see below)
  listener_windows.py — Windows equivalent via keyboard library WH_KEYBOARD_LL hook
  hotkey.py           — pynput wrapper; press/release a key or chord
  led_macos.py        — IOKit ctypes calls to control the Caps Lock LED directly
  tray.py             — pystray menu-bar icon (draws keycap with Pillow, no font files)
```

### macOS interception — two-layer design

**Layer 1 (hidutil):** Remaps the physical Caps Lock key → F13 at the USB HID driver level. This prevents the OS from ever toggling its internal Caps Lock state on a physical keypress.

**Layer 2 (CGEventTap at kCGSessionEventTap):** Intercepts F13 `keyDown`/`keyUp` events and suppresses them (returns `None`). This is where push-to-talk and double-tap logic runs.

**Why this layering matters for the caps lock toggle:** Synthetic `CGEvent`s posted via `CGEventPost` bypass the hidutil remap (which only affects physical HID input). So a synthetic event with keycode 57 (Caps Lock) posted at `kCGHIDEventTap` is NOT remapped to F13 and can toggle the real OS Caps Lock state. The current implementation instead uses `IOHIDSetModifierLockState` via IOKit.

### Double-tap detection (`listener_macos.py:_callback`)

- Tracks `_last_press_time` (time of last F13 `keyDown` that started recording)
- On each `keyDown`: if gap ≤ `double_tap_window` → double-tap → cancel recording, reset timer to 0, spawn thread calling `_toggle_real_caps_lock()`
- Auto-repeat events (`kCGKeyboardEventAutorepeat`) are suppressed to prevent false double-tap triggers during holds
- `_toggle_real_caps_lock` reads current state via `CGEventSourceFlagsState`, then calls `IOHIDSetModifierLockState(service, selector=1, state)` — selector 1 = NX_MODIFIERKEY_ALPHASHIFT (Caps Lock)

### Threading model

The `MacOSListener.start()` call blocks its thread running `CFRunLoopRun()`. It must run in a background thread so the main thread is free for `TrayIcon.start()`, which pystray/AppKit requires on the main thread. LED and hotkey callbacks are each dispatched to short-lived daemon threads from within the CFRunLoop callback.

### Known issue: caps lock toggle

`_iokit_set_caps_lock()` does not check whether `_hid_service` is `IO_OBJECT_NULL` (0) after `IOServiceGetMatchingService`, and does not check the `kern_return_t` from `IOHIDSetModifierLockState`. On newer macOS (Darwin 25+), this call may fail silently. The strategy comment at the top of `listener_macos.py` describes an alternative: posting a synthetic `kCGEventFlagsChanged` event at `kCGHIDEventTap` — this was the intended design but was not implemented.
