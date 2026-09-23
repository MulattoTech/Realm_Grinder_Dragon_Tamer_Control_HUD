"""
Desktop and Window Utilities for Realm Grinder Automation.
Provides safe process creation on the interactive desktop (WinSta0\\Default)
and robust window enumeration/focus management.
"""

import os
import sys
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GENERIC_ALL = 0x10000000
DESKTOP_ALL = 0x01FF

class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def spawn_on_interactive_desktop(cmd_list, cwd=None, detached=True):
    """
    Spawns a process directly attached to the interactive user desktop 'WinSta0\\Default'.
    This ensures GUI windows appear on the user's active screen and are composed by DWM.
    """
    if cwd is None:
        cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    cmd_line = subprocess_list_to_cmdline(cmd_list)

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(STARTUPINFOW)
    si.lpDesktop = "WinSta0\\Default"

    pi = PROCESS_INFORMATION()
    flags = 0
    if detached:
        flags = 0x00000008 | 0x00000200 # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    ok = kernel32.CreateProcessW(
        None,
        cmd_line,
        None,
        None,
        False,
        flags,
        None,
        cwd,
        ctypes.byref(si),
        ctypes.byref(pi)
    )
    if not ok:
        err = kernel32.GetLastError()
        raise RuntimeError(f"CreateProcessW failed with error code {err}")

    kernel32.CloseHandle(pi.hThread)
    kernel32.CloseHandle(pi.hProcess)
    return pi.dwProcessId


def subprocess_list_to_cmdline(seq):
    """Encodes a sequence of argument strings into a Win32 command line string."""
    result = []
    needquote = False
    for arg in seq:
        bs_buf = []
        if len(result) > 0:
            result.append(" ")
        needquote = (" " in arg) or ("\t" in arg) or not arg
        if needquote:
            result.append('"')
        for c in arg:
            if c == '\\':
                bs_buf.append(c)
            elif c == '"':
                result.append('\\' * (len(bs_buf) * 2 + 1))
                result.append(c)
                bs_buf = []
            else:
                if len(bs_buf) > 0:
                    result.append('\\' * len(bs_buf))
                    bs_buf = []
                result.append(c)
        if len(bs_buf) > 0:
            result.append('\\' * (len(bs_buf) * 2 if needquote else len(bs_buf)))
        if needquote:
            result.append('"')
    return "".join(result)


def get_default_desktop_windows():
    """Returns a list of (hwnd, class_name, title) on the Default desktop."""
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    
    # Temporarily switch calling thread to Default desktop
    old_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
    hdesk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL)
    if hdesk:
        user32.SetThreadDesktop(hdesk)

    results = []
    def enum_cb(h, _):
        if user32.IsWindowVisible(h):
            len_t = user32.GetWindowTextLengthW(h)
            title = ""
            if len_t > 0:
                buf_t = ctypes.create_unicode_buffer(len_t + 1)
                user32.GetWindowTextW(h, buf_t, len_t + 1)
                title = buf_t.value
            buf_c = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, buf_c, 256)
            results.append((h, buf_c.value, title))
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if hdesk:
        user32.CloseDesktop(hdesk)
    if old_desk:
        user32.SetThreadDesktop(old_desk)

    return results
