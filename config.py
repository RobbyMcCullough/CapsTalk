# CapsTalk Configuration
# Edit this file to customize behavior.

# ---------------------------------------------------------------------------
# RECORD KEY
# The key (or chord) CapsTalk will simulate when Caps Lock is held.
# This must match the hotkey you configure in Wispr Flow (or your voice app).
#
# Single key:  RECORD_KEY = "f18"
# Chord:       RECORD_KEY = ["cmd", "alt", "r"]
# ---------------------------------------------------------------------------
RECORD_KEY = ["cmd", "alt", "r"]

# ---------------------------------------------------------------------------
# DOUBLE-TAP WINDOW
# How quickly you must tap Caps Lock twice (in seconds) for it to count as
# a double-tap and toggle real Caps Lock on/off.
# Note: macOS applies a ~150 ms hardware debounce to Caps Lock, so the
# minimum effective window is ~0.3 s. 0.4 s is comfortable for most users.
# ---------------------------------------------------------------------------
DOUBLE_TAP_WINDOW = 0.4

# ---------------------------------------------------------------------------
# LED BEHAVIOR (macOS only)
# When True, the Caps Lock LED mirrors recording state:
#   LED ON  = actively recording
#   LED OFF = idle
# Requires Accessibility + Input Monitoring permissions.
# ---------------------------------------------------------------------------
CONTROL_LED = True

# ---------------------------------------------------------------------------
# CAPS LOCK DEBOUNCE (macOS only)
# macOS requires Caps Lock to be held ~150ms before it registers.
# This delay (in seconds) prevents accidental triggers on quick taps.
# Set to 0 to disable.
# ---------------------------------------------------------------------------
CAPS_LOCK_DEBOUNCE = 0.15

# ---------------------------------------------------------------------------
# TRAY ICON
# Show a system tray icon with a quit option.
# ---------------------------------------------------------------------------
SHOW_TRAY_ICON = True
APP_NAME = "CapsTalk"
