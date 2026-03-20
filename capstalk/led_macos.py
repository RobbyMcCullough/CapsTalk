"""
macOS Caps Lock LED control via IOKit.

Uses ctypes to call IOKit C functions directly — no extra dependencies
beyond what ships with macOS.

Requires: Accessibility and Input Monitoring permissions granted to the app
(or the Terminal/Python binary running it).
"""

import ctypes
import threading

_lock = threading.Lock()
_iokit = None
_cf = None

# IOKit / CoreFoundation constants
_kIOHIDOptionsTypeNone = 0
_kHIDPage_GenericDesktop = 0x01
_kHIDUsage_GD_Keyboard = 0x06
_kHIDPage_LEDs = 0x08
_kHIDUsage_LED_CapsLock = 0x02
_kCFNumberIntType = 9


def _load_frameworks():
    global _iokit, _cf
    if _iokit is not None:
        return

    _iokit = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/IOKit.framework/IOKit"
    )
    _cf = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
    )

    # Shorthand types
    _p = ctypes.c_void_p
    _u32 = ctypes.c_uint32
    _i32 = ctypes.c_int32
    _long = ctypes.c_long

    # --- IOKit ---
    # IMPORTANT: argtypes must be set for every function that receives a
    # pointer argument.  Without argtypes, ctypes converts Python ints to
    # the platform C 'int' (32-bit), silently truncating 64-bit pointers.
    _iokit.IOHIDManagerCreate.argtypes = [_p, _u32]
    _iokit.IOHIDManagerCreate.restype = _p

    _iokit.IOHIDManagerSetDeviceMatching.argtypes = [_p, _p]
    _iokit.IOHIDManagerSetDeviceMatching.restype = None

    _iokit.IOHIDManagerOpen.argtypes = [_p, _u32]
    _iokit.IOHIDManagerOpen.restype = _i32

    _iokit.IOHIDManagerClose.argtypes = [_p, _u32]
    _iokit.IOHIDManagerClose.restype = _i32

    _iokit.IOHIDManagerCopyDevices.argtypes = [_p]
    _iokit.IOHIDManagerCopyDevices.restype = _p

    _iokit.IOHIDDeviceCopyMatchingElements.argtypes = [_p, _p, _u32]
    _iokit.IOHIDDeviceCopyMatchingElements.restype = _p

    _iokit.IOHIDElementGetUsagePage.argtypes = [_p]
    _iokit.IOHIDElementGetUsagePage.restype = _u32

    _iokit.IOHIDElementGetUsage.argtypes = [_p]
    _iokit.IOHIDElementGetUsage.restype = _u32

    # AbsoluteTime is uint64_t; CFIndex is long
    _iokit.IOHIDValueCreateWithIntegerValue.argtypes = [
        _p, _p, ctypes.c_uint64, _long
    ]
    _iokit.IOHIDValueCreateWithIntegerValue.restype = _p

    _iokit.IOHIDDeviceSetValue.argtypes = [_p, _p, _p]
    _iokit.IOHIDDeviceSetValue.restype = _i32

    # --- CoreFoundation ---
    _cf.CFStringCreateWithCString.argtypes = [_p, ctypes.c_char_p, _u32]
    _cf.CFStringCreateWithCString.restype = _p

    _cf.CFNumberCreate.argtypes = [_p, _i32, _p]
    _cf.CFNumberCreate.restype = _p

    _cf.CFDictionaryCreate.argtypes = [_p, _p, _p, _long, _p, _p]
    _cf.CFDictionaryCreate.restype = _p

    _cf.CFSetGetCount.argtypes = [_p]
    _cf.CFSetGetCount.restype = _long

    _cf.CFSetGetValues.argtypes = [_p, _p]
    _cf.CFSetGetValues.restype = None

    _cf.CFArrayGetCount.argtypes = [_p]
    _cf.CFArrayGetCount.restype = _long

    _cf.CFArrayGetValueAtIndex.argtypes = [_p, _long]
    _cf.CFArrayGetValueAtIndex.restype = _p

    _cf.CFRelease.argtypes = [_p]
    _cf.CFRelease.restype = None


def _cfstr(s: str):
    """Create a CFStringRef from a Python str. Caller is responsible for CFRelease."""
    return _cf.CFStringCreateWithCString(None, s.encode("utf-8"), 0x08000100)


def _cfnum(n: int):
    """Create a CFNumberRef from a Python int. Caller is responsible for CFRelease."""
    ref = ctypes.c_int32(n)
    return _cf.CFNumberCreate(None, _kCFNumberIntType, ctypes.byref(ref))


def set_caps_lock_led(state: bool) -> bool:
    """
    Turn the Caps Lock LED on (state=True) or off (state=False).

    Returns True on success, False if the LED element could not be found or
    set (e.g., running on a desktop Mac with an external keyboard that
    doesn't expose the LED element via HID).
    """
    with _lock:
        try:
            _load_frameworks()
            return _set_led(state)
        except Exception as exc:
            print(f"[CapsTalk] LED control failed: {exc}")
            return False


def _set_led(state: bool) -> bool:
    # Build device matching dict: GenericDesktop / Keyboard
    page_key = _cfstr("DeviceUsagePage")
    usage_key = _cfstr("DeviceUsage")
    page_val = _cfnum(_kHIDPage_GenericDesktop)
    usage_val = _cfnum(_kHIDUsage_GD_Keyboard)

    keys = (ctypes.c_void_p * 2)(page_key, usage_key)
    values = (ctypes.c_void_p * 2)(page_val, usage_val)

    # kCFTypeDictionaryKeyCallBacks is a global struct in CoreFoundation.
    # We need to pass its *address* (a pointer to the struct) to CFDictionaryCreate.
    # c_byte.in_dll() anchors a ctypes view at the symbol's address in the library;
    # ctypes.addressof() then retrieves that address as a Python int.
    _sentinel = ctypes.c_byte * 1
    key_cbs_ref = _sentinel.in_dll(_cf, "kCFTypeDictionaryKeyCallBacks")
    val_cbs_ref = _sentinel.in_dll(_cf, "kCFTypeDictionaryValueCallBacks")

    matching = _cf.CFDictionaryCreate(
        None,
        ctypes.cast(keys, ctypes.c_void_p),
        ctypes.cast(values, ctypes.c_void_p),
        2,
        ctypes.addressof(key_cbs_ref),
        ctypes.addressof(val_cbs_ref),
    )

    # Release the temporary CF objects now that the dict has retained them
    for obj in (page_key, usage_key, page_val, usage_val):
        if obj:
            _cf.CFRelease(obj)

    if not matching:
        return False

    manager = _iokit.IOHIDManagerCreate(None, _kIOHIDOptionsTypeNone)
    _iokit.IOHIDManagerSetDeviceMatching(manager, matching)
    _cf.CFRelease(matching)

    _iokit.IOHIDManagerOpen(manager, _kIOHIDOptionsTypeNone)
    device_set = _iokit.IOHIDManagerCopyDevices(manager)
    if not device_set:
        _iokit.IOHIDManagerClose(manager, _kIOHIDOptionsTypeNone)
        _cf.CFRelease(manager)
        return False

    count = _cf.CFSetGetCount(device_set)
    device_ptrs = (ctypes.c_void_p * count)()
    _cf.CFSetGetValues(device_set, ctypes.cast(device_ptrs, ctypes.c_void_p))
    _cf.CFRelease(device_set)

    found = False
    for device in device_ptrs:
        if not device:
            continue

        elements = _iokit.IOHIDDeviceCopyMatchingElements(device, None, 0)
        if not elements:
            continue

        elem_count = _cf.CFArrayGetCount(elements)
        for i in range(elem_count):
            elem = _cf.CFArrayGetValueAtIndex(elements, i)
            if not elem:
                continue
            page = _iokit.IOHIDElementGetUsagePage(elem)
            usage = _iokit.IOHIDElementGetUsage(elem)
            if page == _kHIDPage_LEDs and usage == _kHIDUsage_LED_CapsLock:
                value = _iokit.IOHIDValueCreateWithIntegerValue(
                    None, elem, 0, int(state)
                )
                ret = _iokit.IOHIDDeviceSetValue(device, elem, value)
                _cf.CFRelease(value)
                if ret == 0:  # kIOReturnSuccess
                    found = True
                break

        _cf.CFRelease(elements)
        if found:
            break

    _iokit.IOHIDManagerClose(manager, _kIOHIDOptionsTypeNone)
    _cf.CFRelease(manager)
    return found
