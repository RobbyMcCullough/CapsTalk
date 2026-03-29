#!/usr/bin/env python3
"""
CapsTalk — Caps Lock as a push-to-talk record key.

Usage:
    python main.py          # Run normally
    python main.py --help   # Show options

Requires (macOS):
    System Settings → Privacy & Security → Accessibility       ← grant to Terminal / Python
    System Settings → Privacy & Security → Input Monitoring    ← grant to Terminal / Python
"""

import platform
import sys
import signal
import threading

import config
from capstalk.hotkey import RecordHotkey
from capstalk.logutil import log

# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

SYSTEM = platform.system()

if SYSTEM == "Darwin":
    from capstalk.listener_macos import MacOSListener as Listener

    set_led = None
    if config.CONTROL_LED:
        try:
            from capstalk.led_macos import set_caps_lock_led
            set_led = set_caps_lock_led
        except Exception as e:
            log(f"[CapsTalk] LED control unavailable: {e}")

elif SYSTEM == "Windows":
    from capstalk.listener_windows import WindowsListener as Listener
    set_led = None  # Windows: LED follows OS Caps Lock state automatically

else:
    log(f"[CapsTalk] Unsupported platform: {SYSTEM}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

hotkey = RecordHotkey(config.RECORD_KEY)
tray = None
listener = None


def _fmt_key(k):
    return "+".join(k) if isinstance(k, list) else k


def on_record_start():
    log(f"[CapsTalk] ● Recording  (sending {_fmt_key(config.RECORD_KEY)} down)")
    hotkey.press()
    if tray:
        tray.set_recording(True)


def on_record_stop():
    log(f"[CapsTalk] ○ Idle       (sending {_fmt_key(config.RECORD_KEY)} up)")
    hotkey.release()
    if tray:
        tray.set_recording(False)


def shutdown(*_):
    log("\n[CapsTalk] Shutting down…")
    if listener:
        listener.stop()
    if tray:
        tray.stop()
    # Ensure LED is off on exit
    if set_led:
        try:
            set_led(False)
        except Exception:
            pass
    sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global tray, listener

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, shutdown)   # terminal window closed

    log(f"[CapsTalk] Starting on {SYSTEM}")
    log(f"  Record key    : {_fmt_key(config.RECORD_KEY)}")
    log(f"  Double-tap    : {config.DOUBLE_TAP_WINDOW}s window → real Caps Lock")
    log(f"  LED control   : {'on (mirrors recording state)' if set_led else 'off'}")
    log()

    # Keyboard listener runs in a background thread so the main thread is
    # free for the tray icon (macOS AppKit requires NSStatusBar on main thread).
    listener = Listener(
        on_record_start=on_record_start,
        on_record_stop=on_record_stop,
        double_tap_window=config.DOUBLE_TAP_WINDOW,
        set_led=set_led,
        debounce=config.CAPS_LOCK_DEBOUNCE,
    )

    listener_thread = threading.Thread(target=_run_listener, args=(listener,), daemon=True)
    listener_thread.start()

    # Tray icon blocks the main thread (AppKit requires NSStatusBar on main thread).
    if config.SHOW_TRAY_ICON:
        from capstalk.tray import TrayIcon
        tray = TrayIcon(config.APP_NAME, on_quit=shutdown)
        tray.start()  # blocks until quit
    else:
        try:
            while listener_thread.is_alive():
                listener_thread.join(timeout=0.5)
        except KeyboardInterrupt:
            shutdown()


def _run_listener(listener):
    try:
        listener.start()
    except RuntimeError as e:
        log(f"\n[CapsTalk] Fatal: {e}")
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    main()
