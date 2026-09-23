"""
Realm Grinder Dragon Tamer - Universal Launcher
Autonomously launches and coordinates the Steam game, worker bot daemon, and Monitor HUD.
- Detects or launches Realm Grinder via Steam (App ID: 610080)
- Preserves STOP/paused state and lets the existing HUD own the worker
- Launches or focuses the Dragon Tamer Control HUD
- Displays the custom multi-resolution Dragon Tamer icon
"""

import os
import sys
import time
import json
import subprocess
import win32gui
import win32con
import win32process

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STEAM_APP_ID = "610080"
GAME_EXE = "RealmGrinderDesktop.exe"
STATE_FILE = os.path.join(APP_DIR, "state", "dragon_tamer_state.json")
STOP_FILE = os.path.join(APP_DIR, "state", "STOP")
CONFIG_FILE = os.path.join(APP_DIR, "state", "bot_config.json")
ICO_FILE = os.path.join(APP_DIR, "assets", "dragon_tamer.ico")


from src.window import RealmGrinderWindow, _get_default_desktop_handle


def is_game_running() -> bool:
    try:
        w = RealmGrinderWindow()
        return bool(w.find_window())
    except Exception:
        return False


def is_bot_running() -> bool:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                st = json.load(f)
            last_check = st.get("timestamps", {}).get("last_check")
            if last_check:
                from datetime import datetime
                dt = datetime.fromisoformat(last_check)
                if (datetime.now() - dt).total_seconds() < 25.0:
                    return True
    except Exception:
        pass
    return False


def unpause_bot():
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
        except Exception:
            pass
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["paused"] = False
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass


def focus_hud_window() -> bool:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    found_hwnd = [None]

    hdesk = _get_default_desktop_handle()
    if hdesk:
        user32.SetThreadDesktop(hdesk)

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.IsHungAppWindow(hwnd):
            buf_c = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, buf_c, 256)
            if "Tk" in buf_c.value:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf_t = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf_t, length + 1)
                    if "Dragon Tamer" in buf_t.value:
                        found_hwnd[0] = hwnd
                        return False
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)

    if found_hwnd[0]:
        h = found_hwnd[0]
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(h)
        return True
    return False


def launch_game_via_steam():
    try:
        os.startfile(f"steam://rungameid/{STEAM_APP_ID}")
    except Exception:
        try:
            import win32api
            win32api.ShellExecute(0, "open", f"steam://rungameid/{STEAM_APP_ID}", None, None, 1)
        except Exception:
            pass


def main():
    os.chdir(APP_DIR)
    from src.runtime_safety import require_interactive_session
    require_interactive_session()

    # 1. Check if Realm Grinder is already running; if not, trigger launch via Steam
    game_started_now = False
    if not is_game_running():
        launch_game_via_steam()
        game_started_now = True

    python_exe = sys.executable
    pythonw_exe = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
    runner = pythonw_exe if os.path.exists(pythonw_exe) else python_exe

    daemon_flags = 0
    if os.name == 'nt':
        daemon_flags = (
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NEW_PROCESS_GROUP |
            subprocess.CREATE_NO_WINDOW
        )

    # The existing HUD owns the sole worker; preserve the paused/STOP state.

    # 3. Check and start / focus Monitor HUD (GUI must NOT have CREATE_NO_WINDOW)
    if not focus_hud_window():
        gui_flags = 0
        if os.name == 'nt':
            gui_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [runner, os.path.join(APP_DIR, "src", "monitor_window.py")],
            cwd=APP_DIR,
            creationflags=gui_flags,
            close_fds=True
        )

    # 4. If game was triggered just now, wait briefly for it to appear
    if game_started_now:
        for _ in range(30):
            if is_game_running():
                break
            time.sleep(0.5)


if __name__ == "__main__":
    main()
