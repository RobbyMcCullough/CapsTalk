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
    Draw a microphone icon with a status dot.

    Idle:      green dot
    Recording: red dot

    Drawn procedurally with Pillow — no external image file required.
    White on transparent background; renders well in macOS dark-mode menu bar.
    """
    SIZE = 64
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    MIC  = (255, 255, 255, 230)   # mic body / stand / base
    IDLE = (80,  200, 100, 255)   # green dot
    REC  = (220,  50,  50, 255)   # red dot
    dot_color = REC if recording else IDLE

    cx = SIZE // 2  # horizontal centre = 32

    # Capsule body
    draw.rounded_rectangle([cx - 9, 7, cx + 9, 36], radius=9, fill=MIC)

    # U-shaped stand (arc opening upward, beneath capsule)
    draw.arc([cx - 15, 24, cx + 15, 50], start=0, end=180, fill=MIC, width=3)

    # Vertical stem
    draw.line([cx, 49, cx, 57], fill=MIC, width=3)

    # Horizontal base
    draw.line([cx - 11, 57, cx + 11, 57], fill=MIC, width=3)

    # Status dot — bottom-right so it doesn't crowd the mic shape
    draw.ellipse([43, 43, 59, 59], fill=dot_color)

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
