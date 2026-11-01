"""CPU 코어 수 확인. PSIM 시뮬레이션 1개는 단일 스레드라 물리 코어 수가 기준이다."""

from __future__ import annotations

import ctypes
import os
import sys
from functools import lru_cache

_RELATION_PROCESSOR_CORE = 0


def logical_cores() -> int:
    return os.cpu_count() or 1


@lru_cache(maxsize=1)
def physical_cores() -> int:
    """물리 코어 수. 확인할 수 없으면 논리 코어 수를 돌려준다."""
    if sys.platform == "win32":
        count = _windows_physical_cores()
        if count:
            return count
    return logical_cores()


def _windows_physical_cores() -> int | None:
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        length = ctypes.c_ulong(0)
        kernel32.GetLogicalProcessorInformationEx(
            _RELATION_PROCESSOR_CORE, None, ctypes.byref(length)
        )
        if length.value == 0:
            return None
        buf = (ctypes.c_byte * length.value)()
        if not kernel32.GetLogicalProcessorInformationEx(
            _RELATION_PROCESSOR_CORE, buf, ctypes.byref(length)
        ):
            return None
        # SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX: DWORD Relationship, DWORD Size, ...
        offset, count = 0, 0
        raw = bytes(buf)
        while offset + 8 <= length.value:
            relationship = int.from_bytes(raw[offset : offset + 4], "little")
            size = int.from_bytes(raw[offset + 4 : offset + 8], "little")
            if size <= 0:
                break
            if relationship == _RELATION_PROCESSOR_CORE:
                count += 1
            offset += size
        return count or None
    except Exception:
        return None
