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
    assert coords('buy_all_buildings',1280,752)==(919,663)


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
