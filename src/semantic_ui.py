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
_ICON_REFERENCE_SIZE = (976, 669)
_MIN_VIEWPORT_SCALE = 0.5


def _viewport_scale(width, height):
    """Estimate uniform UI scale from the 976x669 client-area fixture."""
    ref_width, ref_height = _ICON_REFERENCE_SIZE
    return max(0.25, (width / ref_width + height / ref_height) / 2)


def locate_icon(frame, icon_path, threshold=0.84, full_frame=False):
    if frame.info.get('capture_kind') == 'SYNTHETIC_STATUS':
        raise ValueError('Cannot identify UI targets from a synthetic status frame')
    image = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR)
    height, width = image.shape[:2]
    if width < round(_ICON_REFERENCE_SIZE[0] * _MIN_VIEWPORT_SCALE) or \
            height < round(_ICON_REFERENCE_SIZE[1] * _MIN_VIEWPORT_SCALE):
        return None
    sx, sy = width / _ICON_REFERENCE_SIZE[0], height / _ICON_REFERENCE_SIZE[1]
    scale = _viewport_scale(width, height)
    top, bottom = round(110 * sy), height - round(104 * sy)
    left, right = round(86 * sx), min(round(519 * sx), width)
    if full_frame:
        top, bottom = round(20 * sy), height - round(20 * sy)
        left, right = round(20 * sx), width - round(20 * sx)
    area = image[top:bottom, left:right]
    if area.size == 0:
        return None
    icon = cv2.imread(str(icon_path), cv2.IMREAD_UNCHANGED)
    if icon is None:
        raise FileNotFoundError(str(icon_path))
    if icon.shape[2] == 4:
        alpha = icon[:, :, 3].astype(float) / 255
        icon = (icon[:, :, :3] * alpha[:, :, None] + 18 * (1-alpha[:, :, None])).astype(np.uint8)
    best = None
    for base_size in (48, 50, 52, 54, 56):
        size = max(16, round(base_size * scale))
        template = cv2.resize(icon, (size, size))[7:-7, 7:-7]
        if template.shape[0] > area.shape[0] or template.shape[1] > area.shape[1]:
            continue
        response = cv2.matchTemplate(area, template, cv2.TM_CCOEFF_NORMED)
        _, score, _, point = cv2.minMaxLoc(response)
        if not math.isfinite(score):
            continue
        center = (left + point[0] + template.shape[1]//2, top + point[1] + template.shape[0]//2)
        suppressed = response.copy()
        x, y = point
        radius = max(8, round(24 * scale))
        suppressed[max(0,y-radius):y+radius+1, max(0,x-radius):x+radius+1] = -1
        if best is None or score > best['score']:
            best = {'x': center[0], 'y': center[1], 'score': float(score),
                    'margin': float(score-suppressed.max()), 'size': size,
                    'client_size': (width, height)}
    if best is None or best['score'] < threshold or best['margin'] < 0.035:
        return None
    return best


def control_point(name, width, height, faction=None):
    if width < round(_ICON_REFERENCE_SIZE[0] * _MIN_VIEWPORT_SCALE) or \
            height < round(_ICON_REFERENCE_SIZE[1] * _MIN_VIEWPORT_SCALE):
        raise ValueError('Client is too small for the calibrated layout')
    points = {'buy_all_upgrades': (157 if faction==11 else 297,59), 'load_template':(297,59), 'buy_all_buildings': (width-361,height-89),
              'realm': (min(560,width-410),min(340,height-170)),
              'abdication': (215,25), 'reincarnation': (390,25), 'upgrades_tab': (40,110)}
    if name not in points:
        raise ValueError('Unknown semantic control: '+name)
    point=points[name]
    if not (0 <= point[0] < width and 0 <= point[1] < height):
        raise ValueError('Calibrated control does not fit the client viewport')
    return point


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


def locate_offline_production_dialog(frame):
    """Return the close-button center only when both calibrated modal anchors agree."""
    if frame.info.get('capture_kind') == 'SYNTHETIC_STATUS':
        return None
    image = cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2GRAY)
    title_path = ROOT/'assets/modal-calibration/offline-production-title.png'
    close_path = ROOT/'assets/modal-calibration/offline-production-close.png'
    title = cv2.imread(str(title_path), cv2.IMREAD_GRAYSCALE)
    close = cv2.imread(str(close_path), cv2.IMREAD_GRAYSCALE)
    if title is None or close is None:
        return None
    # The dialog capture was made at 1180x810. Search modest size variation for DPI scaling.
    for scale in (0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3):
        tw, th = round(title.shape[1]*scale), round(title.shape[0]*scale)
        cw, ch = round(close.shape[1]*scale), round(close.shape[0]*scale)
        if min(tw, th, cw, ch) < 8 or tw > image.shape[1] or th > image.shape[0]:
            continue
        scaled_title = cv2.resize(title, (tw, th), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        response = cv2.matchTemplate(image, scaled_title, cv2.TM_CCOEFF_NORMED)
        _, title_score, _, point = cv2.minMaxLoc(response)
        if title_score < 0.91:
            continue
        # The red close box sits 289x-26y from the title crop origin at calibration scale.
        left, top = point[0] + round(289*scale), point[1] - round(26*scale)
        if left < 0 or top < 0 or left+cw > image.shape[1] or top+ch > image.shape[0]:
            continue
        scaled_close = cv2.resize(close, (cw, ch), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        area = image[top:top+ch, left:left+cw]
        score = cv2.matchTemplate(area, scaled_close, cv2.TM_CCOEFF_NORMED)[0, 0]
        if math.isfinite(float(score)) and score >= 0.88:
            return {'close': (left+cw//2, top+ch//2), 'title_score': float(title_score), 'close_score': float(score)}
    return None


def locate_abdication_dialog(frame):
    """Find an Abdicate confirmation only when title, close and confirm controls agree."""
    if frame.info.get('capture_kind') == 'SYNTHETIC_STATUS':
        return None
    image=cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY)
    root=ROOT/'assets/modal-calibration'
    anchors={name:cv2.imread(str(root/f'abdication-{name}.png'),cv2.IMREAD_GRAYSCALE)
             for name in ('title','close','confirm')}
    if any(anchor is None for anchor in anchors.values()):
        return None
    offsets={'close':(513,-30),'confirm':(-67,172)}
    for scale in (0.8,0.9,1.0,1.1,1.2):
        title=anchors['title'];tw,th=round(title.shape[1]*scale),round(title.shape[0]*scale)
        if tw>image.shape[1] or th>image.shape[0]:continue
        title=cv2.resize(title,(tw,th),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
        response=cv2.matchTemplate(image,title,cv2.TM_CCOEFF_NORMED)
        _,title_score,_,point=cv2.minMaxLoc(response)
        if title_score<0.92:continue
        found={}
        for name,(dx,dy) in offsets.items():
            anchor=anchors[name];w,h=round(anchor.shape[1]*scale),round(anchor.shape[0]*scale)
            left,top=point[0]+round(dx*scale),point[1]+round(dy*scale)
            if left<0 or top<0 or left+w>image.shape[1] or top+h>image.shape[0]:break
            template=cv2.resize(anchor,(w,h),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
            score=float(cv2.matchTemplate(image[top:top+h,left:left+w],template,cv2.TM_CCOEFF_NORMED)[0,0])
            if not math.isfinite(score) or score < (0.90 if name=='close' else 0.87):break
            found[name]=((left+w//2,top+h//2),score)
        if len(found)==2:
            return {'close':found['close'][0],'confirm':found['confirm'][0],
                    'title_score':float(title_score),'close_score':found['close'][1],
                    'confirm_score':found['confirm'][1]}
    return None


def locate_reset_control(frame,operation):
    """Find a reset button label in captured pixels; never authorize a click by itself."""
    anchors={'abdication':'abdication-control.png','reincarnation':'reincarnation-control.png'}
    if operation not in anchors:
        raise ValueError('Unknown reset control: '+str(operation))
    if frame.info.get('capture_kind')=='SYNTHETIC_STATUS':return None
    image=cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY)
    anchor=cv2.imread(str(ROOT/'assets/modal-calibration'/anchors[operation]),cv2.IMREAD_GRAYSCALE)
    if anchor is None:return None
    for scale in (0.9,0.95,1.0,1.05,1.1):
        width,height=round(anchor.shape[1]*scale),round(anchor.shape[0]*scale)
        if width>image.shape[1] or height>image.shape[0]:continue
        template=cv2.resize(anchor,(width,height),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_CUBIC)
        response=cv2.matchTemplate(image,template,cv2.TM_CCOEFF_NORMED)
        _,score,_,point=cv2.minMaxLoc(response)
        if not math.isfinite(score) or score<0.92:continue
        suppressed=response.copy();x,y=point
        suppressed[max(0,y-20):y+21,max(0,x-40):x+41]=-1
        margin=float(score-suppressed.max())
        if margin<0.04:continue
        return {'point':(x+width//2,y+height//2),'score':float(score),'margin':margin,
                'client_size':frame.size}
    return None


def unpurchased_collapsed(frame):
    if frame.info.get('capture_kind')=='SYNTHETIC_STATUS' or \
            frame.width < round(_ICON_REFERENCE_SIZE[0] * _MIN_VIEWPORT_SCALE):
        return False
    sx,sy=frame.width/_ICON_REFERENCE_SIZE[0],frame.height/_ICON_REFERENCE_SIZE[1]
    left,top=round(475*sx),round(80*sy)
    right,bottom=round(510*sx),round(115*sy)
    image=cv2.cvtColor(np.asarray(frame),cv2.COLOR_RGB2GRAY)[top:bottom,left:right]
    factor=_viewport_scale(frame.width,frame.height)
    scores={}
    for name in ('down','up'):
        path=ROOT/f'assets/templates/unpurchased-arrow-{name}.png'
        if not path.exists():raise ValueError('Missing UI calibration anchor; run tools/bootstrap.py on the supported game version')
        icon=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
        if icon is None:
            raise ValueError('Invalid UI calibration anchor dimensions')
        icon=cv2.resize(icon,(max(1,round(icon.shape[1]*factor)),
                              max(1,round(icon.shape[0]*factor))))
        if icon.shape[0]>image.shape[0] or icon.shape[1]>image.shape[1]:
            raise ValueError('Invalid UI calibration anchor dimensions')
        scores[name]=cv2.minMaxLoc(cv2.matchTemplate(image,icon,cv2.TM_CCOEFF_NORMED))[1]
    return bool(scores['down']>.95 and scores['down']>scores['up']+.05)


class SemanticUI:
    def __init__(self, window, cancelled):
        self.window = window
        self.cancelled = cancelled
        self.icon_dir = ROOT/'assets/templates'
        registry_path = self.icon_dir/'registry.json'
        # Clean source checkouts intentionally omit generated/private icon caches.
        # Reset/modal operations do not require that registry; named-icon methods fail
        # explicitly when an attributed cache entry is unavailable.
        self.registry = json.loads(registry_path.read_text(encoding='utf-8')) if registry_path.exists() else {}

    def require_ready(self):
        if self.cancelled() or not self.window.find_window():
            raise RuntimeError('Input is paused or the target is absent')

    def _click_at_size(self, point, client_size, delay_after):
        """Dispatch only while the visible client still matches the target frame."""
        self.require_ready()
        if self.window.is_minimized():
            raise RuntimeError('Semantic input requires real game pixels')
        if tuple(self.window.get_client_size()) != tuple(client_size):
            raise RuntimeError('Window resized since target discovery')
        self.require_ready()
        self.window.click(*point, delay_after=delay_after, auto_scale=False,
                          expected_client_size=tuple(client_size))

    def scroll(self,delta):
        self.require_ready()
        if self.window.is_minimized():
            raise RuntimeError('Semantic scrolling requires a visible game window')
        import win32gui,win32con
        from src.input_controller import make_lparam
        # AIR routes wheel input using its last mouse position, not only lParam.
        width,height=self.window.get_client_size()
        point=(width//2,height//2)
        win32gui.PostMessage(self.window.hwnd,win32con.WM_MOUSEMOVE,0,make_lparam(*point))
        time.sleep(.05)
        screen=win32gui.ClientToScreen(self.window.hwnd,point)
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
            self._click_at_size((round(490*frame.width/_ICON_REFERENCE_SIZE[0]),
                                 round(97*frame.height/_ICON_REFERENCE_SIZE[1])),
                                frame.size,.25)
        self.scroll(2400)
        for index in range(max_scrolls+1):
            self.require_ready();frame=self.window.capture();match=locate_icon(frame,path)
            if match:return dict(match,name=name,source=item,client_size=frame.size)
            if index<max_scrolls:self.scroll(-360)
        return None

    def click_target(self, target):
        self._click_at_size((target['x'],target['y']),target['client_size'],0.2)

    def click_reset_control(self,operation):
        """Open a reset confirmation only from a matched live reset-button label."""
        self.require_ready()
        if self.window.is_minimized():raise RuntimeError('Reset confirmation requires real game pixels')
        frame=self.window.capture();target=locate_reset_control(frame,operation)
        if target is None:raise RuntimeError(f'{operation} button label was not verified; no input was sent')
        self._click_at_size(target['point'],target['client_size'],0.2)
        return target

    def confirm_abdication(self):
        """Click Abdicate only after matching the live modal title, close and button."""
        self.require_ready()
        if self.window.is_minimized():raise RuntimeError('Abdication confirmation requires real game pixels')
        frame=self.window.capture();dialog=locate_abdication_dialog(frame)
        if dialog is None:
            raise RuntimeError('Abdication confirmation dialog was not verified; no confirmation was sent')
        self._click_at_size(dialog['confirm'],frame.size,0.3)
        return dialog

    def click_control(self,name):
        self.require_ready()
        if self.window.is_minimized():
            raise RuntimeError('Semantic control input requires real game pixels')
        frame=self.window.capture()
        if frame.info.get('capture_kind') == 'SYNTHETIC_STATUS':
            raise RuntimeError('Semantic control input requires real game pixels')
        if tuple(frame.size) != tuple(self.window.get_client_size()):
            raise RuntimeError('Window resized while capturing semantic control')
        from src.save_reader import get_current_game_state
        state=get_current_game_state()
        point=control_point(name,*self.window.get_client_size(),faction=state['faction'])
        if template_dialog(frame):
            raise RuntimeError('A template dialog is open; normal production clicks are blocked')
        self._click_at_size(point,frame.size,.1)


    def enter_mercenary_template(self,template):
        self.require_ready()
        if self.window.is_minimized():raise RuntimeError('Template entry requires real dialog evidence, not a synthetic frame')
        if not template or len(template)>4096 or any(ord(ch)<32 for ch in template):raise ValueError('Invalid template string')
        from src.save_reader import get_current_game_state
        if get_current_game_state()['faction']!=11:raise RuntimeError('Mercenary template requested outside Mercenary affiliation')
        frame=self.window.capture();dialog=template_dialog(frame)
        if dialog:
            self._click_at_size(dialog['close'],frame.size,.2)
        self.click_control('load_template');time.sleep(.3)
        frame=self.window.capture();dialog=template_dialog(frame)
        if dialog is None:raise RuntimeError('Template Import dialog was not verified; no text was sent')
        self._click_at_size(dialog['input'],frame.size,.1)
        for character in template:
            self.require_ready();self.window.type_text(character,delay_between=.003)
        time.sleep(.15)
        self.window.capture().save(ROOT/'screenshots/last-template-entry.png')
        self.require_ready();frame=self.window.capture();dialog=template_dialog(frame)
        if dialog is None:raise RuntimeError('Template Import dialog changed before import; no input was sent')
        self._click_at_size(dialog['import'],frame.size,.3)
        frame=self.window.capture();remaining=template_dialog(frame)
        if remaining:self._click_at_size(remaining['close'],frame.size,.2)
        return {'dialog':dialog,'normal_ui_import':True}
