"""Explicit environmental prerequisites, never blanket suppression of test failures."""
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
IMAGE_TESTS={
 'test_semantic_target_matches_specific_icon_not_common_frame':['screenshots/route-calibration-current.png','assets/templates/GemPower.png','assets/templates/MercenaryFirstContract.png'],
 'test_installed_fifty_pixel_alignment_icon_is_supported':['screenshots/route-calibration-current.png','assets/templates/installed-388.png'],
 'test_template_dialog_is_identified_before_typing':['screenshots/mercenary-template-dialog.png','screenshots/route-calibration-current.png','assets/templates/template-dialog-title.png'],
 'test_full_frame_bloodline_choice_recognition':['screenshots/bloodline-choice-modal.png','assets/templates/installed-194.png'],
 'test_collapsed_unpurchased_panel_is_not_guessed':['screenshots/expanded-unpurchased-panel.png','screenshots/unpurchased-scroll-diagnostic.png','assets/templates/unpurchased-arrow-up.png','assets/templates/unpurchased-arrow-down.png'],
}

def pytest_collection_modifyitems(items):
    for item in items:
        name=item.originalname or item.name
        if name in IMAGE_TESTS:
            item.add_marker(pytest.mark.local_assets)
            missing=[path for path in IMAGE_TESTS[name] if not (ROOT/path).exists()]
            if missing:item.add_marker(pytest.mark.skip(reason='Private visual integration fixtures absent: '+', '.join(missing)))
        if name in ('test_reader','test_binary_decoder_has_no_concurrent_mutable_access'):
            item.add_marker(pytest.mark.live_game)
            from src.save_reader import SOL_PATH
            if not Path(SOL_PATH).exists():item.add_marker(pytest.mark.skip(reason='Read-only local game save is absent'))
        if 'catalog' in item.fixturenames and Path(item.path).name=='test_installed_catalog.py':
            item.add_marker(pytest.mark.live_game)
            from src.bootstrap import find_game_directory
            if not (find_game_directory()/'RealmGrinderDesktop.swf').exists():
                item.add_marker(pytest.mark.skip(reason='Installed Realm Grinder binary is absent'))
