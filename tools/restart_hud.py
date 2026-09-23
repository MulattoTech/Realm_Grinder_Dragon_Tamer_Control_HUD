"""Restart only this project's HUD, preserving the game and keeping reset operations disabled during acceptance."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time
import win32gui
import win32con
import win32process
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.runtime_safety import require_interactive_session,session_id
from src.config import load_config,save_config
from src.atomic_store import write_json
from src.window import RealmGrinderWindow


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-build',action='store_true')
    parser.add_argument('--max-wait',type=float,default=90)
    args=parser.parse_args()
    require_interactive_session()
    game=RealmGrinderWindow()
    if not game.find_window():raise RuntimeError('Realm Grinder is not open on this desktop')
    stop=ROOT/'state/STOP';stop.write_text('Reloading HUD; game is preserved.',encoding='utf-8')
    config=load_config();config['paused']=True
    if args.run_build:config.update(selected_goal='Build only',auto_abdicate=False,auto_reincarnate=False)
    save_config(config)
    old=[]
    def visit(hwnd,unused):
        if win32gui.GetClassName(hwnd)=='TkTopLevel' and win32gui.GetWindowText(hwnd)=='Dragon Tamer Quest Tracker & Control HUD':
            pid=win32process.GetWindowThreadProcessId(hwnd)[1]
            if session_id(pid)==session_id():old.append((hwnd,pid))
    win32gui.EnumWindows(visit,None)
    for hwnd,pid in old:win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
    deadline=time.monotonic()+5
    while any(win32gui.IsWindow(hwnd) for hwnd,pid in old) and time.monotonic()<deadline:time.sleep(.1)
    if any(win32gui.IsWindow(hwnd) for hwnd,pid in old):raise RuntimeError('Old HUD did not close normally; no duplicate was started')
    with (ROOT/'logs/hud-upgrade-out.log').open('w') as out,(ROOT/'logs/hud-upgrade-err.log').open('w') as err:
        process=subprocess.Popen([str(Path(sys.executable).with_name('pythonw.exe')),str(ROOT/'src/monitor_window.py')],
            cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(2)
    if process.poll() is not None:raise RuntimeError('HUD startup failed; inspect logs/hud-upgrade-err.log')
    print('HUD_RESTARTED',process.pid,'GAME_PRESERVED',game.pid,flush=True)
    write_json(ROOT/'state/hud-upgrade-launch.json',{'pid':process.pid,'game_pid':game.pid,'session':session_id(),
        'timestamp':time.time(),'previous_pids':[pid for hwnd,pid in old]})
    if not args.run_build:return
    config=load_config();config['paused']=False;save_config(config)
    if stop.exists():stop.unlink()
    started=time.monotonic();reason='Observation timeout';state={}
    try:
        while time.monotonic()-started<min(180,max(1,args.max_wait)):
            try:state=json.loads((ROOT/'state/dragon_tamer_state.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):time.sleep(.2);continue
            if state.get('build_verification',{}).get('build_verified') and load_config().get('paused'):
                reason='Selected build verified and worker paused itself';break
            pending=ROOT/'state/pending_action.json'
            if pending.exists() and json.loads(pending.read_text()).get('status')=='UNCERTAIN':
                reason='Uncertain action; remained fail-closed';break
            time.sleep(.25)
    finally:
        stop.write_text('Build acceptance ended; automation paused.',encoding='utf-8')
        config=load_config();config['paused']=True;save_config(config)
        result={'reason':reason,'elapsed':time.monotonic()-started,'hud_pid':process.pid,'timestamp':time.time(),
            'build':state.get('build_verification'),'last_action':state.get('last_action_result'),
            'next_action':state.get('next_expected_action')}
        write_json(ROOT/'state/full-mercenary-worker-acceptance.json',result)
        print('BUILD_ACCEPTANCE',json.dumps(result),flush=True)

if __name__=='__main__':main()
