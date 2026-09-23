"""
High-Performance Win32 Input Controller for Realm Grinder Automation.
Provides accurate background message dispatch (PostMessageW) with proper
scan codes, transition flags, virtual key mapping, and dynamic DPI/size scaling.
Operates seamlessly whether the game window is active, background, or minimized.
"""

import time
import ctypes
from ctypes import wintypes
from typing import Tuple, Optional, Union

user32 = ctypes.windll.user32

# Win32 Constants
WM_MOUSEMOVE    = 0x0200
WM_LBUTTONDOWN  = 0x0201
WM_LBUTTONUP    = 0x0202
WM_RBUTTONDOWN  = 0x0204
WM_RBUTTONUP    = 0x0205
WM_KEYDOWN      = 0x0100
WM_KEYUP        = 0x0101
WM_CHAR         = 0x0102

MK_LBUTTON      = 0x0001
MK_RBUTTON      = 0x0002
MK_CONTROL      = 0x0008

VK_CONTROL      = 0x11
VK_SHIFT        = 0x10
VK_BACK         = 0x08
VK_RETURN       = 0x0D

MAPVK_VK_TO_VSC = 0


def make_lparam(x: int, y: int) -> int:
    """Encodes client X, Y coordinates into Win32 LPARAM."""
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def get_key_lparam(vk_code: int, is_up: bool = False) -> int:
    """
    Constructs an authentic Win32 keystroke LPARAM containing:
    Bits 0-15:  Repeat count (1)
    Bits 16-23: Scan code from MapVirtualKeyW
    Bit 24:     Extended key flag
    Bit 29:     Context code
    Bit 30:     Previous key state (1 for KEYUP, 0 for KEYDOWN)
    Bit 31:     Transition state (1 for KEYUP, 0 for KEYDOWN)
    """
    scan = user32.MapVirtualKeyW(vk_code, MAPVK_VK_TO_VSC)
    flags = 1 | ((scan & 0xFF) << 16)
    if is_up:
        flags |= (1 << 30) | (1 << 31) # 0xC0000000
    return flags


def scale_coord(base_x: int, base_y: int, curr_w: int, curr_h: int, base_w: int = 1280, base_h: int = 752) -> Tuple[int, int]:
    """Scales coordinates from base design canvas (1280x752) to current client dimensions."""
    if curr_w <= 0 or curr_h <= 0:
        return base_x, base_y
    rx = float(curr_w) / float(base_w)
    ry = float(curr_h) / float(base_h)
    return int(round(base_x * rx)), int(round(base_y * ry))


class InputController:
    """
    Direct Win32 message dispatcher for background / minimized game automation.
    Thread-safe, non-blocking, and never steals user focus.
    """

    @staticmethod
    def post_click(hwnd: int, cx: int, cy: int, delay_after: float = 0.04):
        """Dispatches mouse move, down, and up messages directly to window."""
        if not hwnd or not user32.IsWindow(hwnd):
            return
        lparam = make_lparam(cx, cy)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.02)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
        time.sleep(0.065)  # 65ms = ~2 full frames at 30 FPS ensures Flash button down registers
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
        if delay_after > 0:
            time.sleep(delay_after)

    @staticmethod
    def post_right_click(hwnd: int, cx: int, cy: int, delay_after: float = 0.04):
        """Dispatches right mouse click directly to window."""
        if not hwnd or not user32.IsWindow(hwnd):
            return
        lparam = make_lparam(cx, cy)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lparam)
        time.sleep(0.02)
        user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, lparam)
        time.sleep(0.065)
        user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, lparam)
        if delay_after > 0:
            time.sleep(delay_after)

    @staticmethod
    def post_ctrl_click(hwnd: int, cx: int, cy: int, delay_after: float = 0.04):
        """Sends Ctrl + Left Click (used in Realm Grinder for autocasting toggles)."""
        if not hwnd or not user32.IsWindow(hwnd):
            return
        lparam = make_lparam(cx, cy)
        lp_ctrl_down = get_key_lparam(VK_CONTROL, is_up=False)
        lp_ctrl_up = get_key_lparam(VK_CONTROL, is_up=True)

        user32.PostMessageW(hwnd, WM_KEYDOWN, VK_CONTROL, lp_ctrl_down)
        time.sleep(0.015)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON | MK_CONTROL, lparam)
        time.sleep(0.065)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, MK_CONTROL, lparam)
        time.sleep(0.015)
        user32.PostMessageW(hwnd, WM_KEYUP, VK_CONTROL, lp_ctrl_up)
        if delay_after > 0:
            time.sleep(delay_after)

    @staticmethod
    def post_key(hwnd: int, key: Union[str, int], delay_after: float = 0.015):
        """
        Sends a single key event (KEYDOWN + KEYUP) with authentic hardware scan codes.
        key can be a single character (e.g. '1', 's') or a virtual key code int.
        """
        if not hwnd or not user32.IsWindow(hwnd):
            return
        if isinstance(key, str):
            k_upper = key.upper()
            KEY_MAP = {
                "VK_ESCAPE": 0x1B, "ESC": 0x1B, "ESCAPE": 0x1B,
                "VK_RETURN": 0x0D, "RETURN": 0x0D, "ENTER": 0x0D,
                "VK_BACK": 0x08, "BACKSPACE": 0x08,
                "VK_TAB": 0x09, "TAB": 0x09,
                "VK_SPACE": 0x20, "SPACE": 0x20,
            }
            if k_upper in KEY_MAP:
                vk = KEY_MAP[k_upper]
            elif len(key) == 1:
                vk = ord(key.upper())
            else:
                vk = 0x1B
        else:
            vk = key

        lp_down = get_key_lparam(vk, is_up=False)
        lp_up = get_key_lparam(vk, is_up=True)

        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, lp_down)
        time.sleep(0.008)
        user32.PostMessageW(hwnd, WM_KEYUP, vk, lp_up)
        if delay_after > 0:
            time.sleep(delay_after)

    @staticmethod
    def post_text(hwnd: int, text: str, delay_between: float = 0.003):
        """Types text via WM_CHAR events (used for import/export templates)."""
        if not hwnd or not user32.IsWindow(hwnd):
            return
        for ch in text:
            user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 0)
            if delay_between > 0:
                time.sleep(delay_between)
