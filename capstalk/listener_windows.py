"""
Windows keyboard listener using the `keyboard` library.

The `keyboard` library installs a low-level WH_KEYBOARD_LL hook, which lets
us suppress and intercept individual key events — including Caps Lock —
system-wide without requiring admin rights on most setups.

Note: Running as Administrator gives more reliable hook behavior.
"""

import threading
import time

import keyboard
from capstalk.logutil import log


class WindowsListener:
    """
    Intercepts the Caps Lock key and fires callbacks for record start/stop.
    Two Caps Lock presses within the configured window toggle real Caps Lock.
    """

    def __init__(
        self,
        on_record_start,
        on_record_stop,
        double_tap_window: float = 0.4,
        set_led=None,  # unused on Windows (LED follows OS state)
        debounce: float = 0.0,  # Windows hook is fast enough; debounce unused
    ):
        self._on_record_start = on_record_start
        self._on_record_stop = on_record_stop
        self._recording = False
        self._stop_event = threading.Event()
        self._double_tap_window = double_tap_window
        self._last_press_time = 0.0
        self._caps_is_down = False
        self._hook = None
        self._hook_lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Block until stop() is called."""
        self._install_hook()
        log("[CapsTalk] Windows keyboard hook active.")
        self._stop_event.wait()
        self._remove_hook()

    def stop(self):
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Event handler
    # ------------------------------------------------------------------

    def _on_event(self, event):
        if event.event_type == keyboard.KEY_DOWN:
            if self._caps_is_down:
                return

            self._caps_is_down = True
            now = time.monotonic()

            if (now - self._last_press_time) <= self._double_tap_window:
                self._last_press_time = 0.0

                if self._recording:
                    self._recording = False
                    threading.Thread(
                        target=self._on_record_stop, daemon=True
                    ).start()

                threading.Thread(
                    target=self._toggle_real_caps_lock, daemon=True
                ).start()
                return

            self._last_press_time = now

            if not self._recording:
                self._recording = True
                threading.Thread(
                    target=self._on_record_start, daemon=True
                ).start()

        elif event.event_type == keyboard.KEY_UP:
            self._caps_is_down = False
            if self._recording:
                self._recording = False
                threading.Thread(
                    target=self._on_record_stop, daemon=True
                ).start()

    def _toggle_real_caps_lock(self):
        with self._hook_lock:
            self._remove_hook()
            try:
                keyboard.send("caps lock")
                time.sleep(0.05)
            finally:
                self._install_hook()

    def _install_hook(self):
        with self._hook_lock:
            if self._hook is None:
                self._hook = keyboard.hook_key("caps lock", self._on_event, suppress=True)

    def _remove_hook(self):
        with self._hook_lock:
            if self._hook is not None:
                keyboard.unhook(self._hook)
                self._hook = None
