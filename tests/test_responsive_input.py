"""Viewport-aware input stays bound to the pixels that authorized it."""
from pathlib import Path

import numpy as np
import pytest


def _synthetic_icon():
    """A deterministic, non-flat 64px source icon with a distinctive center."""
    icon = np.zeros((64, 64, 3), dtype=np.uint8)
    icon[:, :] = (35, 80, 150)
    icon[8:56, 8:56] = (190, 45, 80)
    icon[18:46, 18:46] = (30, 210, 170)
    icon[26:38, 26:38] = (245, 230, 40)
    return icon


@pytest.mark.parametrize("factor", [0.65, 0.8, 1.2])
def test_icon_search_scales_viewport_and_template_together(monkeypatch, factor):
    import cv2
    from PIL import Image
    import src.semantic_ui as ui

    source = _synthetic_icon()
    base_icon = cv2.resize(source, (50, 50))[7:-7, 7:-7]
    canvas = np.full((669, 976, 3), (18, 20, 26), dtype=np.uint8)
    canvas[145 - 18:145 + 18, 180 - 18:180 + 18] = base_icon[:, :, ::-1]
    frame = Image.fromarray(canvas).resize(
        (round(976 * factor), round(669 * factor)), Image.Resampling.NEAREST
    )
    monkeypatch.setattr(ui.cv2, "imread", lambda *_args, **_kwargs: source.copy())

    found = ui.locate_icon(frame, Path("synthetic-icon.png"), threshold=0.7)

    assert found is not None
    assert abs(found["x"] - round(180 * factor)) <= 2
    assert abs(found["y"] - round(145 * factor)) <= 2


def test_semantic_layout_accepts_compact_viewports_without_out_of_bounds_points():
    from src.semantic_ui import control_point

    size = (640, 480)
    for name in ("buy_all_upgrades", "load_template", "buy_all_buildings", "realm",
                 "abdication", "reincarnation", "upgrades_tab"):
        x, y = control_point(name, *size)
        assert 0 <= x < size[0]
        assert 0 <= y < size[1]


def test_window_click_refuses_viewport_changed_since_visual_authorization(monkeypatch):
    from src.window import RealmGrinderWindow

    calls = []
    monkeypatch.setattr(RealmGrinderWindow, "is_valid", lambda _self: True)
    monkeypatch.setattr(RealmGrinderWindow, "is_minimized", lambda _self: False)
    monkeypatch.setattr(RealmGrinderWindow, "get_client_size", lambda _self: (1180, 810))
    monkeypatch.setattr(
        "src.window.InputController.post_click",
        lambda *args: calls.append(args),
    )
    window = RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.hwnd = 7

    with pytest.raises(RuntimeError, match="Window resized since target discovery"):
        window.click(215, 20, auto_scale=False, expected_client_size=(976, 669))

    assert calls == []


def test_window_click_can_bind_to_matching_captured_viewport(monkeypatch):
    from src.window import RealmGrinderWindow

    calls = []
    monkeypatch.setattr(RealmGrinderWindow, "is_valid", lambda _self: True)
    monkeypatch.setattr(RealmGrinderWindow, "is_minimized", lambda _self: False)
    monkeypatch.setattr(RealmGrinderWindow, "get_client_size", lambda _self: (976, 669))
    monkeypatch.setattr(
        "src.window.InputController.post_click",
        lambda *args: calls.append(args),
    )
    window = RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.hwnd = 7

    window.click(215, 20, auto_scale=False, expected_client_size=(976, 669))

    assert calls == [(7, 215, 20, 0.04)]


def test_window_click_rejects_point_outside_current_client(monkeypatch):
    from src.window import RealmGrinderWindow

    calls = []
    monkeypatch.setattr(RealmGrinderWindow, "is_valid", lambda _self: True)
    monkeypatch.setattr(RealmGrinderWindow, "is_minimized", lambda _self: False)
    monkeypatch.setattr(RealmGrinderWindow, "get_client_size", lambda _self: (976, 669))
    monkeypatch.setattr(
        "src.window.InputController.post_click",
        lambda *args: calls.append(args),
    )
    window = RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.hwnd = 7

    with pytest.raises(ValueError, match="outside the current client"):
        window.click(1000, 20, auto_scale=False, expected_client_size=(976, 669))
    assert calls == []


@pytest.mark.parametrize(
    ("size", "point", "expected"),
    [((976, 669), (400, 300), (305, 267)),
     ((1180, 810), (400, 300), (369, 323)),
     ((1920, 1080), (400, 300), (600, 431))],
)
def test_window_coordinate_scaling_tracks_current_viewport(monkeypatch, size, point, expected):
    from src.window import RealmGrinderWindow

    calls = []
    monkeypatch.setattr(RealmGrinderWindow, "is_valid", lambda _self: True)
    monkeypatch.setattr(RealmGrinderWindow, "is_minimized", lambda _self: False)
    monkeypatch.setattr(RealmGrinderWindow, "get_client_size", lambda _self: size)
    monkeypatch.setattr(
        "src.window.InputController.post_click",
        lambda *args: calls.append(args),
    )
    window = RealmGrinderWindow.__new__(RealmGrinderWindow)
    window.hwnd = 7
    window.base_width = 1280
    window.base_height = 752

    window.click(*point, expected_client_size=size)

    assert calls == [(7, *expected, 0.04)]


def test_semantic_control_click_refuses_synthetic_minimized_frame():
    from PIL import Image
    from src.semantic_ui import SemanticUI

    class Window:
        hwnd = 7

        def __init__(self):
            self.clicks = []

        def find_window(self):
            return True

        def is_minimized(self):
            return False

        def get_client_size(self):
            return (976, 669)

        def capture(self):
            frame = Image.new("RGB", (1280, 752))
            frame.info["capture_kind"] = "SYNTHETIC_STATUS"
            return frame

        def click(self, *point, **kwargs):
            self.clicks.append((point, kwargs))

    window = Window()
    ui = SemanticUI(window, lambda: False)
    with pytest.raises(RuntimeError, match="real game pixels"):
        ui.click_control("buy_all_buildings")
    assert window.clicks == []


def test_capture_failure_does_not_fall_through_to_semantic_click():
    from src.semantic_ui import SemanticUI

    class Window:
        hwnd = 7

        def __init__(self):
            self.clicks = []

        def find_window(self):
            return True

        def is_minimized(self):
            return False

        def capture(self):
            raise RuntimeError("PrintWindow did not return live game pixels")

        def click(self, *point, **kwargs):
            self.clicks.append((point, kwargs))

    window = Window()
    with pytest.raises(RuntimeError, match="did not return live game pixels"):
        SemanticUI(window, lambda: False).click_control("buy_all_buildings")
    assert window.clicks == []


def test_semantic_target_click_rejects_client_resize_before_dispatch():
    from src.semantic_ui import SemanticUI

    class Window:
        def __init__(self):
            self.clicks = []

        def find_window(self):
            return True

        def is_minimized(self):
            return False

        def get_client_size(self):
            return (1180, 810)

        def click(self, *point, **kwargs):
            self.clicks.append((point, kwargs))

    window = Window()
    ui = SemanticUI(window, lambda: False)
    with pytest.raises(RuntimeError, match="Window resized since target discovery"):
        ui.click_target({"x": 215, "y": 20, "client_size": (976, 669)})
    assert window.clicks == []

