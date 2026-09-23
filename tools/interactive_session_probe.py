"""One-shot observation of the logged-on user's game session; no gameplay inputs."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.atomic_store import write_json
import win32gui
import win32process

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.ProcessIdToSessionId.argtypes = [w.DWORD, ctypes.POINTER(w.DWORD)]
k.ProcessIdToSessionId.restype = w.BOOL

def session_id(pid):
    value = w.DWORD()
    if not k.ProcessIdToSessionId(pid, ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.value

if __name__ == '__main__':
    if session_id(os.getpid()) == 0:
        raise RuntimeError('Run this tool in the logged-on interactive session, not session 0')
    if '--launch-game' in sys.argv:
        import subprocess
        from src.window import RealmGrinderWindow
        game = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Realm Grinder\RealmGrinderDesktop.exe')
        window = RealmGrinderWindow()
        if not window.find_window():
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 7
            subprocess.Popen([str(game)], cwd=game.parent, startupinfo=startup)
            for _ in range(40):
                time.sleep(0.25)
                if window.find_window():
                    if not window.is_minimized():
                        win32gui.ShowWindow(window.hwnd, 7)
                    break
    found = []
    def visit(hwnd, _):
        if win32gui.GetClassName(hwnd) == 'ApolloRuntimeContentWindow':
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            found.append({'hwnd': hwnd, 'pid': pid, 'session': session_id(pid),
                          'title': win32gui.GetWindowText(hwnd),
                          'minimized': bool(win32gui.IsIconic(hwnd))})
    win32gui.EnumWindows(visit, None)
    write_json(Path(__file__).resolve().parents[1]/'state/interactive_session_probe.json',
               {'timestamp': time.time(), 'observer_pid': os.getpid(),
                'observer_session': session_id(os.getpid()), 'game_windows': found})
