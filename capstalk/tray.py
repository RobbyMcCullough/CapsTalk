"""
System tray icon for CapsTalk.

Shows a small icon in the menu bar (macOS) or system tray (Windows) with:
  • Current status (Idle / Recording)
  • Quit option

Requires: pystray, Pillow
"""

import os
import sys
import threading
from PIL import Image, ImageDraw
from capstalk.logutil import log


def _asset_path(filename: str) -> str:
    """Resolve an asset path for both development and PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle — assets are in sys._MEIPASS
        return os.path.join(sys._MEIPASS, filename)
    # Running from source — assets/ is one directory above this package
    return os.path.join(os.path.dirname(__file__), "..", "assets", filename)

try:
    import pystray
    _PYSTRAY_AVAILABLE = True
except ImportError:
    _PYSTRAY_AVAILABLE = False

try:
    import AppKit as _AppKit

    class _SignalPoller(_AppKit.NSObject):
        """NSTimer target — fires periodically so Python can deliver pending signals."""
        def poll_(self, _timer):
            pass  # returning to Python is all that's needed

    _APPKIT_AVAILABLE = True
except ImportError:
    _APPKIT_AVAILABLE = False


def _make_icon(recording: bool) -> Image.Image:
    """
    Load the toolbar icon and overlay a coloured indicator dot.

    Idle:      green dot  (matches the icon's original design)
    Recording: red dot    (signals active recording state)
    """
    img = Image.open(_asset_path("toolbar_icon.png")).convert("RGBA").resize(
        (64, 64), Image.LANCZOS
    )

    # Draw a small indicator dot in the top-left corner (same position as the
    # green circle in the original artwork).
    draw = ImageDraw.Draw(img)
    dot_color = (220, 50, 50) if recording else (80, 200, 100)
    r = 7
    draw.ellipse([4, 4, 4 + r * 2, 4 + r * 2], fill=dot_color)

    return img


class TrayIcon:
    def __init__(self, app_name: str, on_quit):
        self._app_name = app_name
        self._on_quit = on_quit
        self._icon = None
        self._recording = False

    def start(self):
        """Launch the tray icon (blocks until quit). Call from the main thread."""
        if not _PYSTRAY_AVAILABLE:
            log("[CapsTalk] pystray not installed — tray icon disabled.")
            return

        self._icon = pystray.Icon(
            self._app_name,
            _make_icon(False),
            self._app_name,
            menu=pystray.Menu(
                pystray.MenuItem("Status: Idle", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit),
            ),
        )

        if _APPKIT_AVAILABLE:
            # Install a repeating timer on the main run loop so Python can deliver
            # pending signals (e.g. Ctrl+C) while AppKit's NSRunLoop is blocking.
            self._signal_poller = _SignalPoller.alloc().init()
            _AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.5, self._signal_poller, b"poll:", None, True
            )

        self._icon.run()

    def set_recording(self, recording: bool):
        self._recording = recording
        if self._icon:
            self._icon.icon = _make_icon(recording)
            label = "Status: Recording…" if recording else "Status: Idle"
            self._icon.menu = pystray.Menu(
                pystray.MenuItem(label, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit),
            )

    def stop(self):
        if self._icon:
            self._icon.stop()

    def _quit(self, icon, item):
        self.stop()
        self._on_quit()
