def test_modal_dismissal_is_allowed_while_paused_only_for_same_live_session(tmp_path, monkeypatch):
    import src.runtime_safety as safety

    class Window:
        pid=1234
        def find_window(self): return True
        def is_minimized(self): return False

    window=Window()
    monkeypatch.setattr(safety,'STATE_DIR',tmp_path)
    monkeypatch.setattr(safety,'load_config',lambda:{'paused':True})
    monkeypatch.setattr(safety,'session_id',lambda pid=None:1 if pid in (None,1234) else 2)
    (tmp_path/'STOP').write_text('Paused by user')

    assert not safety.input_allowed(window)
    assert safety.modal_dismissal_allowed(window)

    monkeypatch.setattr(safety,'session_id',lambda pid=None:1 if pid is None else 2)
    assert not safety.modal_dismissal_allowed(window)
    monkeypatch.setattr(safety,'session_id',lambda pid=None:1)
    monkeypatch.setattr(window,'is_minimized',lambda:True)
    assert not safety.modal_dismissal_allowed(window)
