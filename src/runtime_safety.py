"""Session-aware guards: observation is allowed remotely; input/GUI launch is not session 0."""
import ctypes
from ctypes import wintypes as w
import os
from pathlib import Path
from src.config import load_config
STATE_DIR=Path(__file__).resolve().parents[1]/'state'

def session_id(pid=None):
    if os.name!='nt': return None
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.ProcessIdToSessionId.argtypes=[w.DWORD,ctypes.POINTER(w.DWORD)]
    kernel.ProcessIdToSessionId.restype=w.BOOL
    value=w.DWORD()
    if not kernel.ProcessIdToSessionId(pid or os.getpid(),ctypes.byref(value)):
        raise ctypes.WinError(ctypes.get_last_error())
    return value.value

def require_interactive_session():
    if session_id() in (None,0):
        raise RuntimeError('Open Realm Grinder and this launcher from the logged-on Windows desktop, not a service/session-0 terminal.')

def input_allowed(window):
    try:
        config=load_config()
        if (STATE_DIR/'STOP').exists() or config.get('paused',True): return False
        own=session_id()
        return bool(own not in (None,0) and window.find_window() and
                    session_id(window.pid)==own and (window.is_minimized() or not config.get('require_minimized',True)))
    except (OSError,RuntimeError):
        return False

def modal_dismissal_allowed(window):
    """Permit a recognized modal close while paused, within the current live session only."""
    try:
        own=session_id()
        return bool(own not in (None,0) and window.find_window() and
                    session_id(window.pid)==own and not window.is_minimized())
    except (OSError,RuntimeError,AttributeError):
        return False


class WorkerLease:
    def __init__(self,state_dir=STATE_DIR):
        self.path=Path(state_dir)/'worker.lock';self.stream=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('a+b')
        self.stream.seek(0,2)
        if self.stream.tell()==0:self.stream.write(b'0');self.stream.flush()
        self.stream.seek(0)
        try:
            import msvcrt
            msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            self.stream.close();self.stream=None
            raise RuntimeError('A Realm Grinder worker already owns this project')
        return self
    def __exit__(self,*exc):
        if self.stream:
            import msvcrt
            self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            self.stream.close()
