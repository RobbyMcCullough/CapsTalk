"""
Windows keyboard listener using the `keyboard` library.

The `keyboard` library installs a low-level WH_KEYBOARD_LL hook, which lets
us suppress and intercept individual key events — including Caps Lock —
system-wide without requiring admin rights on most setups.

Note: Running as Administrator gives more reliable hook behavior.
"""

import threading
import keyboard
from pynput.keyboard import Controller, Key, KeyCode

_controller = Controller()


class WindowsListener:
    """
    Intercepts the Caps Lock key and fires callbacks for record start/stop.
    Also handles Right Alt + Caps Lock → real Caps Lock toggle.
    """

    def __init__(
        self,
        on_record_start,
        on_record_stop,
        caps_lock_modifier: str = "right_alt",
        set_led=None,  # unused on Windows (LED follows OS state)
        debounce: float = 0.0,  # Windows hook is fast enough; debounce unused
    ):
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._recording = False
        self._stop_event = threading.Event()

        # Map config name → keyboard library name
        self._modifier = {
            "right_alt": "right alt",
            "right_option": "right alt",
            "ctrl": "right ctrl",
            "shift": "right shift",
        }.get(caps_lock_modifier, "right alt")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Block until stop() is called."""
        keyboard.hook_key("caps lock", self._on_event, suppress=True)
        print("[CapsTalk] Windows keyboard hook active.")
        self._stop_event.wait()
        keyboard.unhook_all()

    def stop(self):
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_event(self, event):
        modifier_held = keyboard.is_pressed(self._modifier)

        if event.event_type == keyboard.KEY_DOWN:
            if modifier_held:
                # Right Alt + Caps Lock → toggle real Caps Lock
                _controller.press(Key.caps_lock)
            else:
                if not self._recording:
                    self._recording = True
                    threading.Thread(
                        target=self._on_record_start, daemon=True
                    ).start()

        elif event.event_type == keyboard.KEY_UP:
            if not modifier_held and self._recording:
                self._recording = False
                threading.Thread(
                    target=self._on_record_stop, daemon=True
                ).start()
            elif modifier_held:
                _controller.release(Key.caps_lock)
