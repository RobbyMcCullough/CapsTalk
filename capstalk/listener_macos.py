"""
macOS keyboard listener — hidutil remap + Quartz CGEventTap.

Why hidutil instead of intercepting kCGEventFlagsChanged:
  - kCGSessionEventTap fires AFTER the OS has already processed the physical
    Caps Lock key.  By the time our callback runs, the OS has already toggled
    the Caps Lock state — returning None suppresses the event from apps but
    does not undo the state change.
  - kCGEventFlagsChanged fires on BOTH physical key-down AND key-up with the
    SAME AlphaShift flag value, so there's no reliable way to distinguish
    "key pressed" from "key released" using flags alone.

Strategy:
  1. On start: remap Caps Lock → F13 via `hidutil`.  The OS now sees F13
     presses instead of Caps Lock, so the Caps Lock state is never toggled.
  2. Intercept F13 keyDown / keyUp in a CGEventTap — clean push-to-talk.
  3. Double-tap (two quick F13 keyDowns): synthesize a real Caps Lock
     keyDown+keyUp posted at kCGHIDEventTap.  Because the hidutil remap
     operates at the USB HID driver level (below CGEvent injection), the
     synthetic event is NOT remapped — the OS toggles Caps Lock normally.
  4. On exit (atexit + stop()): restore an empty hidutil mapping.

NOTE: This overwrites any existing hidutil UserKeyMapping for the session.
If you have other hidutil key remaps, back them up before running CapsTalk.
"""

import atexit
import ctypes
import json
import subprocess  # used only for hidutil
import threading
import time

import Quartz
from Quartz import (
    CGEventTapCreate,
    CGEventTapEnable,
    CGEventMaskBit,
    CGEventGetIntegerValueField,
    kCGEventKeyDown,
    kCGEventKeyUp,
    kCGEventFlagMaskAlphaShift,
    kCGSessionEventTap,
    kCGHeadInsertEventTap,
    kCGEventTapOptionDefault,
    kCGKeyboardEventKeycode,
    CGEventSourceFlagsState,
    kCGEventSourceStateCombinedSessionState,
    CFMachPortCreateRunLoopSource,
    CFRunLoopGetCurrent,
    CFRunLoopAddSource,
    kCFRunLoopDefaultMode,
    CFRunLoopRun,
)

# HID usage IDs used by hidutil (format: usagePage << 32 | usage)
_CAPS_LOCK_HID = 0x700000039   # page 7, usage 0x39
_F13_HID       = 0x700000068   # page 7, usage 0x68

# IOKit handles for toggling Caps Lock — loaded once on first use.
# _hid_service: None = not looked up yet, False = lookup failed, int = io_service_t
# _hid_connect: None = not opened yet, False = open failed,   int = io_connect_t
#
# IOHIDSetModifierLockState / IOHIDGetModifierLockState require an io_connect_t
# (obtained via IOServiceOpen with kIOHIDParamConnectType) on macOS 14+.
# Passing an io_service_t directly returns kIOReturnNotPermitted.
_iokit       = None
_hid_service = None
_hid_connect = None

_kIOHIDParamConnectType = 1   # from IOHIDLib.h

def _iokit_ensure_service() -> None:
    """Load IOKit, look up IOHIDSystem, and open a param connection (idempotent)."""
    global _iokit, _hid_service, _hid_connect
    if _iokit is None:
        _iokit = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/IOKit.framework/IOKit"
        )
        _iokit.IOServiceMatching.restype  = ctypes.c_void_p
        _iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]
        _iokit.IOServiceGetMatchingService.restype  = ctypes.c_uint32
        _iokit.IOServiceGetMatchingService.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        _iokit.IOServiceOpen.restype  = ctypes.c_int
        _iokit.IOServiceOpen.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
                                         ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        _iokit.IOServiceClose.restype  = ctypes.c_int
        _iokit.IOServiceClose.argtypes = [ctypes.c_uint32]
        _iokit.IOHIDSetModifierLockState.restype  = ctypes.c_int
        _iokit.IOHIDSetModifierLockState.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_int]
        _iokit.IOHIDGetModifierLockState.restype  = ctypes.c_int
        _iokit.IOHIDGetModifierLockState.argtypes = [ctypes.c_uint32, ctypes.c_int,
                                                     ctypes.POINTER(ctypes.c_bool)]
        _iokit.IOObjectRelease.restype  = ctypes.c_int
        _iokit.IOObjectRelease.argtypes = [ctypes.c_uint32]

    if _hid_service is None:
        matching = _iokit.IOServiceMatching(b"IOHIDSystem")
        service = _iokit.IOServiceGetMatchingService(0, matching)
        if not service:
            print("[CapsTalk] IOHIDSystem service not found — caps lock toggle unavailable via IOKit")
            _hid_service = False
            _hid_connect = False
            return
        _hid_service = service

    if _hid_connect is None:
        # mach_task_self_ is a global mach_port_t exported from libSystem
        libsys = ctypes.cdll.LoadLibrary("/usr/lib/libSystem.B.dylib")
        task_self = ctypes.c_uint32.in_dll(libsys, "mach_task_self_").value
        connect = ctypes.c_uint32(0)
        ret = _iokit.IOServiceOpen(_hid_service, task_self,
                                   _kIOHIDParamConnectType, ctypes.byref(connect))
        if ret != 0:
            print(f"[CapsTalk] IOServiceOpen failed: {ret:#010x} — will try service handle directly")
            _hid_connect = False
        else:
            _hid_connect = connect.value
            print(f"[CapsTalk] IOHIDSystem connection opened (io_connect={_hid_connect:#x})")


def _iokit_set_caps_lock(state: bool) -> bool:
    """
    Set the OS Caps Lock state via IOHIDSetModifierLockState.
    Returns True on success, False if the service was not found or the call failed.
    """
    _iokit_ensure_service()
    # Prefer io_connect_t (required on macOS 14+); fall back to io_service_t.
    handle = _hid_connect if (_hid_connect and _hid_connect is not False) else _hid_service
    if not handle:
        return False

    # selector 1 = Caps Lock (NX_MODIFIERKEY_ALPHASHIFT index in IOHIDSystem)
    result = _iokit.IOHIDSetModifierLockState(handle, 1, int(state))
    if result != 0:
        print(f"[CapsTalk] IOHIDSetModifierLockState failed: kern_return={result:#010x}")
        return False
    return True


# CGEvent virtual keycodes (different from HID usages)
_F13_KEYCODE        = 105   # kVK_F13
_CAPS_LOCK_KEYCODE  = 57    # kVK_CapsLock


def _post_caps_lock_event(state: bool) -> None:
    """
    Fallback: synthesize a Caps Lock FlagsChanged event posted at kCGHIDEventTap.

    Because hidutil remaps physical HID input only, synthetic CGEvents bypass
    the remap — keycode 57 (Caps Lock) is NOT redirected to F13 here.
    Posting at kCGHIDEventTap puts the event below our kCGSessionEventTap,
    so it won't be caught and suppressed by our own callback.
    """
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    event = Quartz.CGEventCreateKeyboardEvent(src, _CAPS_LOCK_KEYCODE, True)
    flags = kCGEventFlagMaskAlphaShift if state else 0
    Quartz.CGEventSetFlags(event, flags)
    Quartz.CGEventSetType(event, Quartz.kCGEventFlagsChanged)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _hidutil_set(mappings: list) -> None:
    payload = json.dumps({"UserKeyMapping": mappings})
    r = subprocess.run(["hidutil", "property", "--set", payload],
                       capture_output=True, check=False)
    if r.returncode != 0:
        print(f"[CapsTalk] hidutil failed (rc={r.returncode}): {r.stderr.decode().strip()}")


# Module-level safety net: always restore the default key mapping on Python exit,
# even if the instance's atexit/stop() path doesn't run (e.g. pystray swallows SIGINT).
atexit.register(lambda: _hidutil_set([]))


class MacOSListener:
    """
    Intercepts the Caps Lock key via hidutil remap + CGEventTap:
      - Hold       → push-to-talk (fires on_record_start / on_record_stop)
      - Double-tap → toggles real Caps Lock on/off
    """

    def __init__(
        self,
        on_record_start,
        on_record_stop,
        double_tap_window: float = 0.4,
        set_led=None,
        debounce: float = 0.15,
    ):
        self._on_record_start  = on_record_start
        self._on_record_stop   = on_record_stop
        self._set_led          = set_led
        self._double_tap_window = double_tap_window

        self._recording        = False
        self._tap              = None
        self._last_press_time  = 0.0
        self._remap_installed  = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Block until the event tap is torn down. Call from a background thread."""
        self._install_remap()

        # We only care about keyDown/keyUp — Caps Lock never fires these
        # directly (it fires FlagsChanged), but F13 does.
        mask = CGEventMaskBit(kCGEventKeyDown) | CGEventMaskBit(kCGEventKeyUp)

        self._tap = CGEventTapCreate(
            kCGSessionEventTap,
            kCGHeadInsertEventTap,
            kCGEventTapOptionDefault,
            mask,
            self._callback,
            None,
        )

        if not self._tap:
            self._remove_remap()
            raise RuntimeError(
                "CGEventTap creation failed.\n"
                "Grant Accessibility + Input Monitoring permissions to this app:\n"
                "  System Settings → Privacy & Security → Accessibility\n"
                "  System Settings → Privacy & Security → Input Monitoring"
            )

        source = CFMachPortCreateRunLoopSource(None, self._tap, 0)
        CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopDefaultMode)
        CGEventTapEnable(self._tap, True)
        print("[CapsTalk] macOS event tap active (Caps Lock → F13 remap installed).")
        CFRunLoopRun()

    def stop(self):
        if self._tap:
            CGEventTapEnable(self._tap, False)
        self._remove_remap()

    # ------------------------------------------------------------------
    # hidutil remap
    # ------------------------------------------------------------------

    def _install_remap(self):
        if self._remap_installed:
            return
        _hidutil_set([{
            "HIDKeyboardModifierMappingSrc": _CAPS_LOCK_HID,
            "HIDKeyboardModifierMappingDst": _F13_HID,
        }])
        self._remap_installed = True
        atexit.register(self._remove_remap)

    def _remove_remap(self):
        if not self._remap_installed:
            return
        _hidutil_set([])
        self._remap_installed = False

    # ------------------------------------------------------------------
    # Event callback (called on the CFRunLoop thread)
    # ------------------------------------------------------------------

    def _callback(self, proxy, event_type, event, refcon):
        keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)

        if keycode != _F13_KEYCODE:
            return event  # pass everything else through unchanged

        now = time.monotonic()

        if event_type == kCGEventKeyDown:
            # Ignore auto-repeat events — only the initial press matters.
            # Without this, holding the key generates rapid repeat keyDowns
            # that fall within the double-tap window and falsely trigger it.
            if CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat):
                return None  # suppress repeat silently

            if now - self._last_press_time <= self._double_tap_window:
                # Double-tap: cancel any recording and toggle real Caps Lock.
                print(f"[CapsTalk] double-tap detected (gap={now - self._last_press_time:.3f}s)")
                if self._recording:
                    self._stop_recording()
                self._last_press_time = 0.0   # reset so a third tap doesn't trigger
                threading.Thread(target=self._toggle_real_caps_lock, daemon=True).start()
            else:
                self._last_press_time = now
                if not self._recording:
                    self._start_recording()

        elif event_type == kCGEventKeyUp:
            if self._recording:
                self._stop_recording()

        return None  # suppress F13 in all cases

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_recording(self):
        self._recording = True
        if self._set_led:
            threading.Thread(target=self._set_led, args=(True,), daemon=True).start()
        threading.Thread(target=self._on_record_start, daemon=True).start()

    def _stop_recording(self):
        self._recording = False
        if self._set_led:
            threading.Thread(target=self._set_led, args=(False,), daemon=True).start()
        threading.Thread(target=self._on_record_stop, daemon=True).start()

    def _toggle_real_caps_lock(self):
        _iokit_ensure_service()
        # Prefer io_connect_t for read too — it's what the API expects on macOS 14+.
        handle = _hid_connect if (_hid_connect and _hid_connect is not False) else _hid_service

        state_out = ctypes.c_bool(False)
        if handle:
            read_result = _iokit.IOHIDGetModifierLockState(handle, 1, ctypes.byref(state_out))
            if read_result != 0:
                print(f"[CapsTalk] IOHIDGetModifierLockState failed (rc={read_result:#010x})")
                caps_is_on = bool(CGEventSourceFlagsState(kCGEventSourceStateCombinedSessionState) & kCGEventFlagMaskAlphaShift)
            else:
                caps_is_on = state_out.value
        else:
            caps_is_on = bool(CGEventSourceFlagsState(kCGEventSourceStateCombinedSessionState) & kCGEventFlagMaskAlphaShift)

        new_state = not caps_is_on
        print(f"[CapsTalk] toggle_caps_lock: caps={'ON' if caps_is_on else 'OFF'} → {'ON' if new_state else 'OFF'}")

        if not _iokit_set_caps_lock(new_state):
            print("[CapsTalk] IOKit set failed — trying CGEvent fallback")
            _post_caps_lock_event(new_state)

        # Give the event system a moment to apply the change before verifying
        time.sleep(0.05)
        after_out = ctypes.c_bool(False)
        if handle:
            _iokit.IOHIDGetModifierLockState(handle, 1, ctypes.byref(after_out))
        print(f"[CapsTalk] toggle_caps_lock: result={'ON' if after_out.value else 'OFF'}")
