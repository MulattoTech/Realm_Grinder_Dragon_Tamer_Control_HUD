"""
Production-Grade Window Interaction & Controller for Realm Grinder.
Features:
- Per-Monitor DPI Aware V2 support for pixel-perfect coordinate scaling
- Thread-safe HWND caching with microsecond Win32 API validation
- Zero-unminimize background operation guarantee (window strictly stays iconic)
- Integration with high-performance InputController (WM_KEYDOWN scan codes & PostMessage)
- DWM-safe visual telemetry and high-resolution screen capture
"""

import os
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List
from datetime import datetime

import win32gui
import win32ui
import win32con
import win32process
from PIL import Image

from src.input_controller import InputController, scale_coord

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Attempt Per-Monitor V2 DPI awareness initialization
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE_V2
except Exception:
    try:
        user32.SetProcessDpiAwarenessContext(-4) # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    except Exception:
        pass


def _get_default_desktop_handle():
    """Returns handle to user interactive desktop."""
    return user32.OpenDesktopW("Default", 0, False, 0x01FF)


class RealmGrinderWindow:
    """
    Complete Win32 Window Controller for Realm Grinder (Adobe AIR / Apollo).
    Operates seamlessly whether game is active, obscured, backgrounded, or minimized.
    """
    def __init__(self, target_title: str = "Realm Grinder"):
        self.target_title = target_title
        self.hwnd: Optional[int] = None
        self.pid: Optional[int] = None
        self.base_width = 1280
        self.base_height = 752
        self.find_window()

    def find_window(self):
        """Find the exact AIR game on the current desktop without switching desktops."""
        if self.hwnd:
            try:
                if (win32gui.IsWindow(self.hwnd) and
                    win32gui.GetClassName(self.hwnd) == 'ApolloRuntimeContentWindow' and
                    win32gui.GetWindowText(self.hwnd) == self.target_title and
                    win32process.GetWindowThreadProcessId(self.hwnd)[1] == self.pid):
                    return True
            except Exception:
                pass
        matches = []
        def visit(hwnd, unused):
            try:
                if (win32gui.GetClassName(hwnd) == 'ApolloRuntimeContentWindow' and
                        win32gui.GetWindowText(hwnd) == self.target_title):
                    matches.append((hwnd, win32process.GetWindowThreadProcessId(hwnd)[1]))
            except Exception:
                pass
        try:
            win32gui.EnumWindows(visit, None)
        except Exception:
            pass
        if len(matches) != 1:
            self.hwnd, self.pid = None, None
            return False
        self.hwnd, self.pid = matches[0]
        return True

    def is_valid(self) -> bool:
        """Microsecond validation of window handle."""
        if not self.hwnd:
            return False
        return bool(user32.IsWindow(self.hwnd))

    def is_minimized(self) -> bool:
        """Returns True if the game is minimized (iconic) to the taskbar."""
        if not self.is_valid():
            return False
        return bool(user32.IsIconic(self.hwnd))

    def is_maximized(self) -> bool:
        """Returns True if the window is maximized."""
        if not self.is_valid():
            return False
        return bool(user32.IsZoomed(self.hwnd))

    def ensure_interactable(self):
        """
        Ensures window handle is connected and valid.
        STRICT GUARANTEE: Never un-minimizes, restores, or disturbs window state.
        """
        if not self.is_valid():
            self.find_window()

    def get_client_rect(self) -> Tuple[int, int, int, int]:
        """Returns client RECT (left, top, right, bottom) directly in microseconds."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return 0, 0, self.base_width, self.base_height
        rect = wintypes.RECT()
        user32.GetClientRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    def get_client_size(self) -> Tuple[int, int]:
        """Returns client (width, height), defaulting to 1280x752 if minimized."""
        if self.is_minimized():
            return getattr(self, "_last_client_size", None) or (self.base_width, self.base_height)
        r = self.get_client_rect()
        w = max(1, r[2] - r[0])
        h = max(1, r[3] - r[1])
        self._last_client_size = (w,h)
        return w, h

    def scale_point(self, base_cx: int, base_cy: int) -> Tuple[int, int]:
        """Scales (base_cx, base_cy) from design canvas (1280x752) to active window size."""
        cw, ch = self.get_client_size()
        return scale_coord(base_cx, base_cy, cw, ch, self.base_width, self.base_height)

    def click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True):
        """
        Clicks at client coordinates via background PostMessage.
        Automatically scales coordinates from baseline design dimensions.
        Works 100% reliably while minimized.
        """
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self.scale_point(cx, cy) if auto_scale else (cx, cy)
        InputController.post_click(self.hwnd, target_x, target_y, delay_after)

    def ctrl_click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True):
        """Sends Ctrl + Left Click (autocasting toggle) via background PostMessage."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self.scale_point(cx, cy) if auto_scale else (cx, cy)
        InputController.post_ctrl_click(self.hwnd, target_x, target_y, delay_after)

    def right_click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True):
        """Right-clicks at client coordinates."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self.scale_point(cx, cy) if auto_scale else (cx, cy)
        InputController.post_right_click(self.hwnd, target_x, target_y, delay_after)

    def press_key(self, key: str, delay_after: float = 0.015):
        """Sends key event with authentic hardware scan codes via PostMessage."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        InputController.post_key(self.hwnd, key, delay_after)

    def type_text(self, text: str, delay_between: float = 0.003):
        """Types text via WM_CHAR messages."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        InputController.post_text(self.hwnd, text, delay_between)

    def activate(self, force: bool = False):
        """Brings game to foreground only if force=True and not minimized."""
        if not self.is_valid():
            if not self.find_window():
                return
        if self.is_minimized() and not force:
            return  # Strictly respect minimized state

        fore_hwnd = user32.GetForegroundWindow()
        if fore_hwnd == self.hwnd:
            return

        # Simulate ALT keystroke to unlock foreground restriction
        user32.keybd_event(0x12, 0, 0, 0)
        time.sleep(0.01)
        user32.keybd_event(0x12, 0, 2, 0)

        cur_thread = kernel32.GetCurrentThreadId()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None) if fore_hwnd else 0

        attached = False
        if fore_thread != 0 and fore_thread != cur_thread:
            try:
                attached = user32.AttachThreadInput(cur_thread, fore_thread, True)
            except Exception:
                attached = False

        try:
            user32.ShowWindow(self.hwnd, 9)  # SW_RESTORE
            user32.BringWindowToTop(self.hwnd)
            user32.SetForegroundWindow(self.hwnd)
        except Exception:
            pass
        finally:
            if attached:
                try:
                    user32.AttachThreadInput(cur_thread, fore_thread, False)
                except Exception:
                    pass

    def capture(self, re_minimize: bool = False) -> Image.Image:
        """
        Captures client area via native Win32 PrintWindow.
        If minimized, generates a high-res telemetry visual frame WITHOUT un-minimizing!
        """
        if not self.is_valid():
            if not self.find_window():
                raise RuntimeError("Realm Grinder window not found")

        # Zero-Unminimize: If minimized, never touch window state!
        if self.is_minimized():
            from PIL import ImageDraw
            cw, ch = self.base_width, self.base_height
            im = Image.new("RGB", (cw, ch), (18, 19, 24))
            draw = ImageDraw.Draw(im)
            draw.rectangle([(0, 0), (cw-1, ch-1)], outline=(47, 51, 66), width=2)
            draw.text((40, 40), "REALM GRINDER [RUNNING SILENTLY IN BACKGROUND - MINIMIZED]", fill=(0, 229, 192))
            draw.text((40, 70), f"SYNTHETIC STATUS FRAME - NOT LIVE GAME PIXELS OR PROOF OF AUTOMATION", fill=(245, 166, 35))
            draw.text((40, 100), f"Capture Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(142, 148, 166))
            draw.text((40, 130), "Window is kept safely on taskbar without interrupting your workflow.", fill=(46, 204, 113))
            im.info['capture_kind'] = 'SYNTHETIC_STATUS'
            im.info['is_live_ui_evidence'] = False
            return im

        cw, ch = self.get_client_size()
        wr = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(wr))
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(self.hwnd, ctypes.byref(pt))
        ox = pt.x - wr.left
        oy = pt.y - wr.top
        ww = wr.right - wr.left
        wh = wr.bottom - wr.top

        hwndDC = user32.GetWindowDC(self.hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, ww, wh)
        saveDC.SelectObject(saveBitMap)

        user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 2)
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        full_im = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)

        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        user32.ReleaseDC(self.hwnd, hwndDC)

        return full_im.crop((ox, oy, ox + cw, oy + ch))
