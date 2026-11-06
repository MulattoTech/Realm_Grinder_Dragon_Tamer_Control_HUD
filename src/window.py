"""
Window Interaction & Controller for Realm Grinder.
Features:
- Per-Monitor DPI awareness with client-coordinate scaling
- Cached HWND identity checks before window operations
- Synthetic status frames when the game is minimized; those are not UI evidence
- Integration with high-performance InputController (WM_KEYDOWN scan codes & PostMessage)
- Best-effort client-area screen capture
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

# Prefer Per-Monitor V2 awareness and fall back to Per-Monitor V1.
try:
    _dpi_v2_set = user32.SetProcessDpiAwarenessContext(-4) # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
    if not _dpi_v2_set:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        pass


def _get_default_desktop_handle():
    """Returns handle to user interactive desktop."""
    return user32.OpenDesktopW("Default", 0, False, 0x01FF)


class RealmGrinderWindow:
    """
    Win32 window controller for Realm Grinder (Adobe AIR / Apollo).
    Uses client-area coordinates. PostMessage behavior can vary by game/window state;
    minimized input and capture are not treated as verified UI interaction.
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
        """Return whether the cached HWND still names a live window."""
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
        """Refresh an invalid handle without changing visibility or minimized state."""
        if not self.is_valid():
            self.find_window()

    def get_client_rect(self) -> Tuple[int, int, int, int]:
        """Return client RECT (left, top, right, bottom) in client coordinates."""
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

    def _resolve_click_point(self, cx, cy, auto_scale, expected_client_size):
        if expected_client_size is not None and self.is_minimized():
            raise RuntimeError('Semantic input requires real game pixels')
        client_size = tuple(self.get_client_size())
        if expected_client_size is not None and client_size != tuple(expected_client_size):
            raise RuntimeError('Window resized since target discovery')
        if auto_scale:
            x, y = scale_coord(cx, cy, *client_size, self.base_width, self.base_height)
        else:
            x, y = cx, cy
        if not (0 <= x < client_size[0] and 0 <= y < client_size[1]):
            raise ValueError('Click point is outside the current client')
        return x, y

    def point_is_visible(self, cx: int, cy: int) -> bool:
        """Return whether this point is unobscured by another top-level window.

        Foreground focus is deliberately not required: an unfocused game window
        is safe to target when it is the topmost window at the intended point.
        PrintWindow can capture covered content, so pixels alone do not establish
        that a posted action can reach the game.
        """
        try:
            if not self.is_valid() or self.is_minimized():
                return False
            screen_point = win32gui.ClientToScreen(self.hwnd, (int(cx), int(cy)))
            top = win32gui.WindowFromPoint(screen_point)
            if not top:
                return False
            root = win32gui.GetAncestor(top, win32con.GA_ROOT)
            return top == self.hwnd or root == self.hwnd
        except Exception:
            return False

    def click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True,
              expected_client_size: Optional[Tuple[int, int]] = None):
        """
        Clicks at client coordinates via background PostMessage.
        Optionally binds a visual target to the client size that was captured.
        Direct coordinate calls may be attempted while minimized, but are not
        proof that the game received or acted on the input.
        """
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self._resolve_click_point(cx, cy, auto_scale, expected_client_size)
        if not self.point_is_visible(target_x, target_y):
            raise RuntimeError('Click point is covered by another window or not visible')
        InputController.post_click(self.hwnd, target_x, target_y, delay_after)

    def ctrl_click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True,
                   expected_client_size: Optional[Tuple[int, int]] = None):
        """Sends Ctrl + Left Click (autocasting toggle) via background PostMessage."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self._resolve_click_point(cx, cy, auto_scale, expected_client_size)
        if not self.point_is_visible(target_x, target_y):
            raise RuntimeError('Click point is covered by another window or not visible')
        InputController.post_ctrl_click(self.hwnd, target_x, target_y, delay_after)

    def right_click(self, cx: int, cy: int, delay_after: float = 0.04, auto_scale: bool = True,
                    expected_client_size: Optional[Tuple[int, int]] = None):
        """Right-clicks at client coordinates."""
        if not self.is_valid():
            self.find_window()
        if not self.hwnd:
            return
        target_x, target_y = self._resolve_click_point(cx, cy, auto_scale, expected_client_size)
        if not self.point_is_visible(target_x, target_y):
            raise RuntimeError('Click point is covered by another window or not visible')
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
        """Request foreground activation; force=True may restore a minimized window."""
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
        """Capture client pixels, or return a synthetic non-evidence frame if minimized."""
        if not self.is_valid():
            if not self.find_window():
                raise RuntimeError("Realm Grinder window not found")

        # Do not invoke PrintWindow when minimized; its output is not UI evidence.
        if self.is_minimized():
            from PIL import ImageDraw
            cw, ch = self.base_width, self.base_height
            im = Image.new("RGB", (cw, ch), (18, 19, 24))
            draw = ImageDraw.Draw(im)
            draw.rectangle([(0, 0), (cw-1, ch-1)], outline=(47, 51, 66), width=2)
            draw.text((40, 40), "REALM GRINDER [MINIMIZED]", fill=(0, 229, 192))
            draw.text((40, 70), "SYNTHETIC STATUS FRAME - NO LIVE GAME PIXELS", fill=(245, 166, 35))
            draw.text((40, 100), f"Capture Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fill=(142, 148, 166))
            draw.text((40, 130), "Capture left the window state unchanged.", fill=(46, 204, 113))
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

        if cw <= 0 or ch <= 0 or ww <= 0 or wh <= 0:
            raise RuntimeError('Realm Grinder client area has invalid dimensions')
        hwndDC = user32.GetWindowDC(self.hwnd)
        if not hwndDC:
            raise RuntimeError('Could not capture Realm Grinder window pixels')
        mfcDC = saveDC = saveBitMap = None
        try:
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, ww, wh)
            saveDC.SelectObject(saveBitMap)

            if not user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 2):
                raise RuntimeError('PrintWindow did not return live game pixels')
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)
            full_im = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                                       bmpstr, 'raw', 'BGRX', 0, 1)
            if ox < 0 or oy < 0 or ox + cw > full_im.width or oy + ch > full_im.height:
                raise RuntimeError('Captured window geometry does not match the client area')
            frame = full_im.crop((ox, oy, ox + cw, oy + ch))
            if frame.size != (cw, ch):
                raise RuntimeError('Captured pixels do not match the current client size')
            return frame
        finally:
            if saveBitMap is not None:
                win32gui.DeleteObject(saveBitMap.GetHandle())
            if saveDC is not None:
                saveDC.DeleteDC()
            if mfcDC is not None:
                mfcDC.DeleteDC()
            user32.ReleaseDC(self.hwnd, hwndDC)
