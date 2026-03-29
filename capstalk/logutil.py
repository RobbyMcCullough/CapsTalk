"""Lightweight logging helpers that tolerate missing console handles."""

from __future__ import annotations

import sys


def log(*args, **kwargs):
    """Print without crashing when stdout/stderr are unavailable."""
    stream = kwargs.pop("file", sys.stdout)
    try:
        print(*args, file=stream, **kwargs)
    except OSError:
        pass
