"""
Sends and releases the configured record hotkey to the active application.

Supports a single key (e.g. 'f18') or a chord list (e.g. ['cmd', 'option', 'r']).
Special keys are looked up by name in the pynput Key enum; single characters
are sent as-is.
"""

from pynput.keyboard import Controller, Key, KeyCode

_controller = Controller()

# Map string names to pynput Key enum values for special keys
_SPECIAL_KEYS = {
    name.lower(): val
    for name, val in vars(Key).items()
    if not name.startswith("_")
}


def _resolve(key_name: str):
    """Return a pynput key object from a string like 'f18', 'cmd', or 'r'."""
    lower = key_name.lower()
    if lower in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[lower]
    if len(key_name) == 1:
        return KeyCode.from_char(key_name)
    raise ValueError(
        f"Unknown key name '{key_name}'. "
        "Use a single character or a pynput Key name (e.g. 'f18', 'cmd', 'option')."
    )


class RecordHotkey:
    """Manages press/release of the configured record key or chord."""

    def __init__(self, key_config):
        # Accept a single key string or a list of keys for a chord.
        keys = key_config if isinstance(key_config, list) else [key_config]
        self._keys = [_resolve(k) for k in keys]

    def press(self):
        for key in self._keys:
            _controller.press(key)

    def release(self):
        for key in reversed(self._keys):
            _controller.release(key)
