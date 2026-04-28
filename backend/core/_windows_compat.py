"""Windows-only workaround for slow/broken WMI on dev machines.

Some Windows installs have a broken or very slow WMI repository, which makes
`platform.uname()` hang indefinitely. asyncpg imports `platform` and reads
`platform.uname().system` at module-import time, so a broken WMI hangs the
entire backend on `import asyncpg`.

Importing this module BEFORE asyncpg / sqlalchemy installs a stub uname()
that pulls everything from cheap env vars / sys, never touches WMI.

Production (Linux containers) doesn't need this — it's only loaded on
Windows. Importing on non-Windows is a no-op.
"""
from __future__ import annotations

import os
import sys


def install_uname_stub() -> None:
    """Replace platform.uname / platform.processor with non-WMI stubs."""
    if sys.platform != "win32":
        return

    import platform

    class _FakeUname:
        system = "Windows"
        node = os.environ.get("COMPUTERNAME", "dev")
        release = os.environ.get("OS", "Windows_NT").replace("Windows_", "") or "11"
        version = os.environ.get("PROCESSOR_REVISION", "10.0")
        machine = os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64")

    platform.uname = lambda: _FakeUname()  # noqa: E731
    platform.processor = lambda: os.environ.get(
        "PROCESSOR_IDENTIFIER", "AMD64"
    )


# Auto-install on import — single import line at app entry suffices.
install_uname_stub()
