"""
System tray icon for CapsTalk.

Shows a small icon in the menu bar (macOS) or system tray (Windows) with:
  • Current status (Idle / Recording)
  • Quit option

Requires: pystray, Pillow
"""

import threading
from PIL import Image, ImageDraw

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
    Draw a keycap icon.

    Idle:      dark grey keycap body, white 'A' legend
    Recording: red/coral keycap body, white 'A' legend
    """
    S = 64  # canvas size

    # Colours
    if recording:
        body    = (220, 50,  50)   # red
        shadow  = (150, 30,  30)   # darker red for bottom edge
        top     = (240, 90,  90)   # lighter top face
    else:
        body    = (75,  75,  80)   # dark grey
        shadow  = (40,  40,  44)   # darker bottom edge
        top     = (105, 105, 112)  # lighter top face

    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Keycap shape ---
    # Outer rounded-rectangle (full body, slightly darker — gives 3-D depth)
    r = 10   # corner radius
    margin = 4
    draw.rounded_rectangle([margin, margin, S - margin, S - margin],
                           radius=r, fill=shadow)

    # Top face: inset and raised by ~4 px on the bottom
    face_t = margin + 3   # top of face
    face_l = margin + 4   # left
    face_r = S - margin - 4  # right
    face_b = S - margin - 7  # bottom (shorter = 3-D illusion)
    draw.rounded_rectangle([face_l, face_t, face_r, face_b],
                           radius=r - 2, fill=top)

    # Subtle inner bevel (one pixel lighter line on top-left edges)
    bevel = tuple(min(c + 40, 255) for c in top)
    draw.rounded_rectangle([face_l + 1, face_t + 1, face_r - 1, face_b - 1],
                           radius=r - 3, outline=bevel, width=1)

    # --- Legend: "A" centred on the top face ---
    legend_color = (255, 255, 255, 230)

    # Build the letter with basic lines (no font dependency)
    cx = S // 2
    cy = (face_t + face_b) // 2 + 1

    # Scale: letter fits in ~26×26 inside the face
    hw = 9   # half-width of the A base
    ht = 11  # half-height

    # Left leg
    draw.line([(cx - hw, cy + ht), (cx, cy - ht)], fill=legend_color, width=4)
    # Right leg
    draw.line([(cx, cy - ht), (cx + hw, cy + ht)], fill=legend_color, width=4)
    # Crossbar
    bar_y = cy + 2
    draw.line([(cx - hw + 5, bar_y), (cx + hw - 5, bar_y)],
              fill=legend_color, width=3)

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
            print("[CapsTalk] pystray not installed — tray icon disabled.")
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
