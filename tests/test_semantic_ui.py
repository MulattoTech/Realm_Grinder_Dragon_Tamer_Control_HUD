"""Native window and semantic targeting must not guess a global scale."""
from pathlib import Path
import importlib
import pytest
import numpy as np

def test_window_finder_uses_exact_class_and_title(monkeypatch):
    import src.window as module
    calls=[]
    monkeypatch.setattr(module.win32gui,'EnumWindows',lambda visit,data:[visit(h,data) for h in (10,11,12)])
    monkeypatch.setattr(module.win32gui,'GetClassName',lambda h:'ApolloRuntimeContentWindow' if h in (10,12) else 'CabinetWClass')
    monkeypatch.setattr(module.win32gui,'GetWindowText',lambda h:'Another AIR App' if h==10 else 'Realm Grinder')
    monkeypatch.setattr(module.win32process,'GetWindowThreadProcessId',lambda h:(100,700+h))
    window=module.RealmGrinderWindow.__new__(module.RealmGrinderWindow)
    window.hwnd=None;window.pid=None;window.target_title='Realm Grinder';window._last_client_size=None
    assert window.find_window() and window.hwnd==12 and window.pid==712


def test_minimized_window_uses_last_observed_client_size(monkeypatch):
    from src.window import RealmGrinderWindow
    window=RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.base_width=1280;window.base_height=752
    window._last_client_size=(976,669)
    window.is_minimized=lambda:True
    assert window.get_client_size()==(976,669)


def api():
    assert Path('src/semantic_ui.py').exists(), 'Semantic icon targeting is missing'
    return importlib.import_module('src.semantic_ui')


def test_semantic_target_matches_specific_icon_not_common_frame():
    from PIL import Image
    root=Path.cwd();frame=Image.open(root/'screenshots/route-calibration-current.png')
    result=api().locate_icon(frame,root/'assets/templates/GemPower.png')
    assert result and abs(result['x']-180)<=3 and abs(result['y']-145)<=3
    assert api().locate_icon(frame,root/'assets/templates/MercenaryFirstContract.png') is None


def test_synthetic_status_frame_is_not_game_evidence():
    from PIL import Image
    frame=Image.new('RGB',(976,669));frame.info['capture_kind']='SYNTHETIC_STATUS'
    with pytest.raises(ValueError,match='synthetic'):
        api().locate_icon(frame,Path('assets/templates/GemPower.png'))


def test_basic_ui_controls_anchor_to_correct_panes():
    coords=api().control_point
    assert coords('buy_all_upgrades',976,669)==(297,59)
    assert coords('buy_all_upgrades',1280,752)==(297,59)
    assert coords('buy_all_buildings',976,669)==(615,580)
    assert coords('buy_all_buildings',1280,752)==(919,635)
    # Live 1433x822 capture: the Buildings Buy All button is at (1072, 695).
    # Keep the dispatched point inside the observed button bounds (y=673..717).
    x, y = coords('buy_all_buildings',1433,822)
    assert x == 1072
    assert 673 <= y <= 717
    assert coords('research_tab',1433,822)==(40,300)
    assert coords('research_load_template',1433,822)==(398,18)
    assert coords('buy_all_research',1433,822)==(305,47)
    assert coords('research_tab',716,411)==(20,150)
    assert coords('buy_all_research',716,411)==(152,24)


def test_single_target_purchase_proof_rejects_unrelated_many_upgrades():
    proof=api().purchase_delta
    before={'reincarnation':24,'alignment':0,'faction':-1,'raw_data':{'upgrades':{}}}
    after={'reincarnation':24,'alignment':0,'faction':-1,'raw_data':{'upgrades':{'1':{'u1':True}}}}
    assert proof(before,after,{},{} )=={'verified':True,'learned_id':1}
    after['raw_data']['upgrades']['2']={'u1':True}
    assert not proof(before,after,{},{} )['verified']
    assert proof(before,after,{'id':1},{})['verified']
    assert not proof(before,after,{}, {'faction':11})['verified']


def test_installed_fifty_pixel_alignment_icon_is_supported():
    from PIL import Image
    from src.semantic_ui import locate_icon
    frame=Image.open('screenshots/route-calibration-current.png')
    result=locate_icon(frame,Path('assets/templates/installed-388.png'))
    assert result and result['score']>.98 and abs(result['x']-480)<=2


def test_mercenary_buy_all_is_not_the_load_template_button():
    from src.semantic_ui import control_point
    assert control_point('buy_all_upgrades',976,669,faction=11)==(157,59)
    assert control_point('load_template',976,669,faction=11)==(297,59)
    assert control_point('buy_all_upgrades',976,669,faction=3)==(297,59)

def test_template_dialog_is_identified_before_typing():
    from PIL import Image
    import src.semantic_ui as ui
    assert hasattr(ui,'template_dialog'), 'Template dialog recognition missing'
    found=ui.template_dialog(Image.open('screenshots/mercenary-template-dialog.png'))
    assert found and abs(found['input'][0]-488)<3 and abs(found['input'][1]-160)<3
    assert abs(found['import'][1]-585)<3
    assert ui.template_dialog(Image.open('screenshots/route-calibration-current.png')) is None


def test_research_template_uses_visible_dialog_and_scaled_control_path(monkeypatch):
    from PIL import Image
    import src.semantic_ui as ui
    import src.save_reader as save_reader
    frame=Image.new('RGB',(1433,822));frame.info['capture_kind']='LIVE'
    dialog={'input':(717,238),'import':(717,663),'close':(937,114),'bounds':(497,115,937,707),'score':.99}
    recognitions=iter((None,dialog,dialog,None))
    monkeypatch.setattr(ui,'template_dialog',lambda _frame:next(recognitions))
    monkeypatch.setattr(save_reader,'get_current_game_state',lambda:{'faction':3})
    class Window:
        def __init__(self):self.clicks=[];self.typed=''
        def find_window(self):return True
        def is_minimized(self):return False
        def capture(self):return frame.copy()
        def get_client_size(self):return frame.size
        def click(self,*point,**_kwargs):self.clicks.append(point)
        def type_text(self,value,**_kwargs):self.typed+=value
    window=Window();semantic=ui.SemanticUI(window,lambda:False)
    result=semantic.enter_research_template('S50,S105')
    assert result['normal_ui_import'] is True
    assert window.clicks==[(40,300),(398,18),(717,238),(717,663),(305,47)]
    assert window.typed=='S50,S105'


def test_offline_production_close_requires_title_and_close_icon_pair():
    from PIL import Image
    import src.semantic_ui as ui
    assert hasattr(ui,'locate_offline_production_dialog'), 'Offline Production dialog recognition missing'
    title_path=Path('assets/modal-calibration/offline-production-title.png')
    close_path=Path('assets/modal-calibration/offline-production-close.png')
    assert title_path.exists() and close_path.exists(), 'Offline Production calibration anchors missing'
    title=Image.open(title_path).convert('RGB')
    close=Image.open(close_path).convert('RGB')
    frame=Image.new('RGB',(1180,810),(30,45,55))
    frame.paste(title,(448,280))
    frame.paste(close,(737,254))
    found=ui.locate_offline_production_dialog(frame)
    assert found and found['close']==(753,270)


def test_offline_production_title_without_close_icon_is_not_dismissed():
    from PIL import Image
    import src.semantic_ui as ui
    assert hasattr(ui,'locate_offline_production_dialog'), 'Offline Production dialog recognition missing'
    title=Image.open('assets/modal-calibration/offline-production-title.png').convert('RGB')
    frame=Image.new('RGB',(1180,810),(30,45,55))
    frame.paste(title,(448,280))
    assert ui.locate_offline_production_dialog(frame) is None


def test_offline_production_dialog_recognition_scales_with_window():
    from PIL import Image
    import src.semantic_ui as ui
    title=Image.open('assets/modal-calibration/offline-production-title.png').convert('RGB')
    close=Image.open('assets/modal-calibration/offline-production-close.png').convert('RGB')
    scale=0.8
    title=title.resize((round(title.width*scale),round(title.height*scale)),Image.Resampling.NEAREST)
    close=close.resize((round(close.width*scale),round(close.height*scale)),Image.Resampling.NEAREST)
    frame=Image.new('RGB',(640,480),(30,45,55))
    title_origin=(200,200)
    close_origin=(title_origin[0]+round(289*scale),title_origin[1]-round(26*scale))
    frame.paste(title,title_origin)
    frame.paste(close,close_origin)
    found=ui.locate_offline_production_dialog(frame)
    assert found and found['close']==(close_origin[0]+close.width//2,close_origin[1]+close.height//2)

def test_abdication_dialog_requires_title_close_and_confirm_button():
    from PIL import Image
    import src.semantic_ui as ui
    assert hasattr(ui,'locate_abdication_dialog'), 'Abdication dialog recognizer missing'
    root=Path('assets/modal-calibration')
    title=Image.open(root/'abdication-title.png').convert('RGB')
    close=Image.open(root/'abdication-close.png').convert('RGB')
    confirm=Image.open(root/'abdication-confirm.png').convert('RGB')
    frame=Image.new('RGB',(1280,752),(22,22,24))
    title_origin=(574,260)
    frame.paste(title,title_origin)
    frame.paste(close,(title_origin[0]+513,title_origin[1]-30))
    frame.paste(confirm,(title_origin[0]-67,title_origin[1]+172))
    found=ui.locate_abdication_dialog(frame)
    assert found and found['close']==(1103,247) and found['confirm']==(572,459)

def test_abdication_dialog_does_not_match_without_confirm_control():
    from PIL import Image
    import src.semantic_ui as ui
    title=Image.open('assets/modal-calibration/abdication-title.png').convert('RGB')
    close=Image.open('assets/modal-calibration/abdication-close.png').convert('RGB')
    frame=Image.new('RGB',(1280,752),(22,22,24))
    frame.paste(title,(574,260));frame.paste(close,(1087,230))
    assert ui.locate_abdication_dialog(frame) is None

def test_abdication_dialog_controls_follow_centered_modal_in_live_client_geometry():
    from PIL import Image
    import src.semantic_ui as ui
    root=Path('assets/modal-calibration')
    title=Image.open(root/'abdication-title.png').convert('RGB')
    close=Image.open(root/'abdication-close.png').convert('RGB')
    confirm=Image.open(root/'abdication-confirm.png').convert('RGB')
    frame=Image.new('RGB',(1180,810),(22,22,24))
    origin=(524,289)
    frame.paste(title,origin)
    frame.paste(close,(origin[0]+513,origin[1]-30))
    frame.paste(confirm,(origin[0]-67,origin[1]+172))
    found=ui.locate_abdication_dialog(frame)
    assert found and found['close']==(1053,276) and found['confirm']==(522,488)

@pytest.mark.parametrize(('operation','filename','origin','expected'),[
    ('abdication','abdication-control.png',(100,20),(155,31)),
    ('reincarnation','reincarnation-control.png',(300,20),(360,31)),
])
def test_reset_control_requires_live_button_label(operation,filename,origin,expected):
    from PIL import Image
    import src.semantic_ui as ui
    path=Path('assets/modal-calibration')/filename
    assert hasattr(ui,'locate_reset_control') and path.exists()
    anchor=Image.open(path).convert('RGB')
    frame=Image.new('RGB',(800,300),(18,20,26));frame.paste(anchor,origin)
    found=ui.locate_reset_control(frame,operation)
    assert found and found['point']==expected

def test_reset_control_locator_rejects_unknown_controls():
    from PIL import Image
    import src.semantic_ui as ui
    with pytest.raises(ValueError,match='Unknown reset control'):
        ui.locate_reset_control(Image.new('RGB',(1180,810)),'fast_forward')

def test_semantic_reset_click_needs_pixels_and_live_input_gate():
    from PIL import Image
    from src.semantic_ui import SemanticUI
    anchor=Image.open('assets/modal-calibration/abdication-control.png').convert('RGB')
    frame=Image.new('RGB',(1180,810),(18,20,26));frame.paste(anchor,(160,9))
    class Window:
        def __init__(self):self.clicks=[]
        def find_window(self):return True
        def is_minimized(self):return False
        def get_client_size(self):return (1180,810)
        def capture(self):return frame
        def click(self,*point,**kwargs):self.clicks.append((point,kwargs))
    window=Window();ui=SemanticUI(window,lambda:False)
    target=ui.click_reset_control('abdication')
    assert target['point']==(215,20)
    assert window.clicks==[((215,20),{'delay_after':0.2,'auto_scale':False,
                                     'expected_client_size':(1180,810)})]
    guarded=Window();cancelled=SemanticUI(guarded,lambda:True)
    with pytest.raises(RuntimeError,match='paused or the target is absent'):
        cancelled.click_reset_control('abdication')
    assert guarded.clicks==[]

def test_abdication_confirm_requires_full_dialog_pixel_match():
    from PIL import Image
    from src.semantic_ui import SemanticUI
    root=Path('assets/modal-calibration')
    frame=Image.new('RGB',(1280,752),(22,22,24));origin=(574,260)
    frame.paste(Image.open(root/'abdication-title.png').convert('RGB'),origin)
    frame.paste(Image.open(root/'abdication-close.png').convert('RGB'),(origin[0]+513,origin[1]-30))
    frame.paste(Image.open(root/'abdication-confirm.png').convert('RGB'),(origin[0]-67,origin[1]+172))
    class Window:
        def __init__(self,im):self.frame=im;self.clicks=[]
        def find_window(self):return True
        def is_minimized(self):return False
        def get_client_size(self):return self.frame.size
        def capture(self):return self.frame
        def click(self,*point,**kwargs):self.clicks.append((point,kwargs))
    window=Window(frame);ui=SemanticUI(window,lambda:False)
    dialog=ui.confirm_abdication()
    assert dialog['confirm']==(572,459)
    assert window.clicks==[((572,459),{'delay_after':0.3,'auto_scale':False,
                                      'expected_client_size':(1280,752)})]
    missing=Image.new('RGB',(1280,752),(22,22,24));missing.paste(
        Image.open(root/'abdication-title.png').convert('RGB'),origin)
    guarded=Window(missing)
    with pytest.raises(RuntimeError,match='confirmation dialog was not verified'):
        SemanticUI(guarded,lambda:False).confirm_abdication()
    assert guarded.clicks==[]

def test_full_frame_bloodline_choice_recognition():
    from PIL import Image
    from src.semantic_ui import locate_icon
    frame=Image.open('screenshots/bloodline-choice-modal.png')
    found=locate_icon(frame,Path('assets/templates/installed-194.png'),full_frame=True)
    assert found and abs(found['x']-428)<3 and abs(found['y']-237)<3

def test_collapsed_unpurchased_panel_is_not_guessed():
    from PIL import Image
    import src.semantic_ui as ui
    assert hasattr(ui,'unpurchased_collapsed')
    assert ui.unpurchased_collapsed(Image.open('screenshots/expanded-unpurchased-panel.png'))
    assert not ui.unpurchased_collapsed(Image.open('screenshots/unpurchased-scroll-diagnostic.png'))


def test_missing_arrow_calibration_is_an_explicit_error_not_an_opencv_crash(monkeypatch,tmp_path):
    import src.semantic_ui as ui
    from PIL import Image
    monkeypatch.setattr(ui,'ROOT',tmp_path)
    with pytest.raises(ValueError,match='calibration'):
        ui.unpurchased_collapsed(Image.new('RGB',(976,669)))
