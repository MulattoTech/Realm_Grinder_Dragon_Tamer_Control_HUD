"""Source-icon targeting and independently verified purchase transitions."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import time
import cv2
import numpy as np
from src.action_verification import upgrade_owned
ROOT = Path(__file__).resolve().parents[1]


def locate_icon(frame, icon_path, threshold=0.84, full_frame=False):
    if frame.info.get('capture_kind') == 'SYNTHETIC_STATUS':
        raise ValueError('Cannot identify UI targets from a synthetic status frame')
    image = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
    height, width = image.shape[:2]
    if width < 760 or height < 500:
        return None
    top, bottom, left, right = 110, height - 104, 86, min(519, width)
    if full_frame:top,bottom,left,right=20,height-20,20,width-20
    area = image[top:bottom, left:right]
    icon = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
    if icon is None:
        raise FileNotFoundError(str(icon_path))
    if icon.shape[2] == 4:
        alpha = icon[:, :, 3].astype(float) / 255
        icon = (icon[:, :, :3] * alpha[:, :, None] + 18 * (1-alpha[:, :, None])).astype(np.uint8)
    best = None
    for size in (48, 50, 52, 54, 56):
        template = cv2.resize(icon, (size, size))[7:-7, 7:-7]
        response = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, point = cv2.minMaxLoc(response)
        if not math.isfinite(score):
            continue
        center = (left + point[0] + template.shape[1]//2, top + point[1] + template.shape[0]//2)
        suppressed = response.copy()
        x, y = point
        suppressed[max(0,y-24):y+25, max(0,x-24):x+25] = -1
        if best is None or score > best['score']:
            best = {'x': center[0], 'y': center[1], 'score': float(score),
                    'margin': float(score-suppressed.max()), 'size': size}
    if best is None or best['score'] < threshold or best['margin'] < 0.035:
        return None
    return best


def control_point(name, width, height, faction=None):
    if width < 760 or height < 500:
        raise ValueError('Client is too small for the calibrated layout')
    points = {'buy_all_upgrades': (157 if faction==11 else 297,59), 'load_template':(297,59), 'buy_all_buildings': (width-361,height-89),
              'realm': (min(560,width-410),min(340,height-170)),
              'abdication': (215,25), 'reincarnation': (390,25), 'upgrades_tab': (40,110)}
    if name not in points:
        raise ValueError('Unknown semantic control: '+name)
    return points[name]


def purchase_delta(before, after, known, expected):
    if before.get('reincarnation') != after.get('reincarnation'):
        return {'verified': False, 'reason': 'Reincarnation changed during purchase'}
    if any(after.get(key) != value for key, value in expected.items()):
        return {'verified': False, 'reason': 'Expected affiliation was not observed'}
    if known.get('id') is not None:
        return {'verified': upgrade_owned(after, known['id']) and not upgrade_owned(before, known['id']),
                'learned_id': known['id']}
    old = {key for key,value in before.get('raw_data',{}).get('upgrades',{}).items() if value.get('u1')}
    new = {key for key,value in after.get('raw_data',{}).get('upgrades',{}).items() if value.get('u1')}
    added = new-old
    if len(added) == 1:
        return {'verified': True, 'learned_id': int(next(iter(added)))}
    if expected and all(before.get(key) != value for key,value in expected.items()):
        return {'verified': True, 'learned_id': None, 'evidence': 'exact_affiliation_transition'}
    return {'verified': False, 'reason': 'Purchase identity is ambiguous or unchanged'}



def template_dialog(frame):
    if frame.info.get('capture_kind')=='SYNTHETIC_STATUS':return None
    image=cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY)
    title=cv2.imread(str(ROOT/'assets/templates/template-dialog-title.png'),cv2.IMREAD_GRAYSCALE)
    if title is None:return None
    response=cv2.matchTemplate(image[:image.shape[0]//2],title,cv2.TM_CCOEFF_NORMED)
    _,score,_,point=cv2.minMaxLoc(response)
    if score<.92:return None
    left,top=point[0]-98,point[1]-17
    if left<0 or top<0 or left+440>frame.width or top+592>frame.height:return None
    return {'input':(left+220,top+123),'import':(left+220,top+548),
            'close':(left+440,top-1),'bounds':(left,top,left+440,top+592),'score':score}


def unpurchased_collapsed(frame):
    if frame.info.get('capture_kind')=='SYNTHETIC_STATUS' or frame.width<760:return False
    image=cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY)[80:115,475:510]
    scores={}
    for name in ('down','up'):
        path=ROOT/f'assets/templates/unpurchased-arrow-{name}.png'
        if not path.exists():raise ValueError('Missing UI calibration anchor; run tools/bootstrap.py on the supported game version')
        icon=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if icon is None or icon.shape[0]>image.shape[0] or icon.shape[1]>image.shape[1]:
            raise ValueError('Invalid UI calibration anchor dimensions')
        scores[name]=cv2.minMaxLoc(cv2.matchTemplate(image,icon,cv2.TM_CCOEFF_NORMED))[1]
    return bool(scores['down']>.95 and scores['down']>scores['up']+.05)


class SemanticUI:
    def __init__(self, window, cancelled):
        self.window = window
        self.cancelled = cancelled
        self.icon_dir = ROOT/'assets/templates'
        self.registry = json.loads((self.icon_dir/'registry.json').read_text(encoding='utf-8'))

    def require_ready(self):
        if self.cancelled() or not self.window.find_window():
            raise RuntimeError('Input is paused or the target is absent')

    def scroll(self,delta):
        self.require_ready()
        import win32gui,win32con
        from src.input_controller import make_lparam
        # AIR routes wheel input using its last mouse position, not only lParam.
        win32gui.PostMessage(self.window.hwnd,win32con.WM_MOUSEMOVE,0,make_lparam(400,300))
        time.sleep(.05)
        screen=win32gui.ClientToScreen(self.window.hwnd,(400,300))
        win32gui.PostMessage(self.window.hwnd,win32con.WM_MOUSEWHEEL,(delta&0xffff)<<16,make_lparam(*screen))
        time.sleep(.3)

    def find_named(self,name,max_scrolls=8):
        self.require_ready()
        item=self.registry.get(name)
        if not item:raise ValueError('No attributed source icon is cached for '+name)
        path=self.icon_dir/item['file']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Source icon integrity check failed')
        if self.window.is_minimized():raise RuntimeError('This purchase needs real pixels; the game will not be restored')
        frame=self.window.capture()
        full=name.endswith(' Bloodline')
        match=locate_icon(frame,path,full_frame=full)
        if match:return dict(match,name=name,source=item,client_size=frame.size)
        if full:
            selector=self.find_named('Bloodline',max_scrolls=max_scrolls)
            if selector is None:return None
            self.click_target(selector);time.sleep(.3)
            frame=self.window.capture();match=locate_icon(frame,path,full_frame=True)
            return dict(match,name=name,source=item,client_size=frame.size) if match else None
        if unpurchased_collapsed(frame):
            self.window.click(490,97,delay_after=.25,auto_scale=False)
        self.scroll(2400)
        for index in range(max_scrolls+1):
            self.require_ready();frame=self.window.capture();match=locate_icon(frame,path)
            if match:return dict(match,name=name,source=item,client_size=frame.size)
            if index<max_scrolls:self.scroll(-360)
        return None

    def click_target(self, target):
        self.require_ready()
        if list(self.window.get_client_size()) != list(target['client_size']):
            raise RuntimeError('Window resized since target discovery')
        self.window.click(target['x'], target['y'], delay_after=0.2, auto_scale=False)

    def click_control(self,name):
        self.require_ready()
        from src.save_reader import get_current_game_state
        state=get_current_game_state()
        point=control_point(name,*self.window.get_client_size(),faction=state['faction'])
        if not self.window.is_minimized() and template_dialog(self.window.capture()):
            raise RuntimeError('A template dialog is open; normal production clicks are blocked')
        self.window.click(*point,delay_after=.1,auto_scale=False)


    def enter_mercenary_template(self,template):
        self.require_ready()
        if self.window.is_minimized():raise RuntimeError('Template entry requires real dialog evidence, not a synthetic frame')
        if not template or len(template)>4096 or any(ord(ch)<32 for ch in template):raise ValueError('Invalid template string')
        from src.save_reader import get_current_game_state
        if get_current_game_state()['faction']!=11:raise RuntimeError('Mercenary template requested outside Mercenary affiliation')
        dialog=template_dialog(self.window.capture())
        if dialog:
            self.window.click(*dialog['close'],delay_after=.2,auto_scale=False)
        self.click_control('load_template');time.sleep(.3)
        dialog=template_dialog(self.window.capture())
        if dialog is None:raise RuntimeError('Template Import dialog was not verified; no text was sent')
        self.window.click(*dialog['input'],delay_after=.1,auto_scale=False)
        for character in template:
            self.require_ready();self.window.type_text(character,delay_between=.003)
        time.sleep(.15)
        self.window.capture().save(ROOT/'screenshots/last-template-entry.png')
        self.require_ready();self.window.click(*dialog['import'],delay_after=.3,auto_scale=False)
        frame=self.window.capture();remaining=template_dialog(frame)
        if remaining:self.window.click(*remaining['close'],delay_after=.2,auto_scale=False)
        return {'dialog':dialog,'normal_ui_import':True}
