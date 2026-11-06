from pathlib import Path
import ast
import json

def source():return Path('src/monitor_window.py').read_text(encoding='utf-8')

def test_hud_has_persistent_faction_path_selector():
    text=source()
    assert 'self.path_var' in text and 'PATH_CHOICES' in text
    assert 'selected_path' in text

def test_start_path_does_not_create_a_second_bot():
    tree=ast.parse(source())
    candidates=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='start_selected_path']
    assert candidates, 'Start selected path handler missing'
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='DragonBot' for n in ast.walk(candidates[0]))

def test_wiki_ui_uses_full_source_index_with_provenance():
    text=source()
    assert 'KnowledgeStore' in text and 'resolved_url' in text and 'captured_at' in text

def test_worker_tracks_observed_save_samples():
    text=Path('src/state_machine.py').read_text(encoding='utf-8')
    assert 'self.tracker.observe_state' in text
    assert 'self.tracker.record_snapshot' not in text

def test_worker_dismisses_known_modal_before_pause_return():
    tree=ast.parse(Path('src/state_machine.py').read_text(encoding='utf-8'))
    step=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='step')
    def contains_call(node,name):
        return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr==name
                   for n in ast.walk(node))
    dismiss_index=next(i for i,n in enumerate(step.body) if contains_call(n,'dismiss_modals'))
    pause_index=next(i for i,n in enumerate(step.body) if contains_call(n,'is_paused'))
    assert dismiss_index < pause_index

def test_hud_pending_action_summary_names_reconciliation_evidence():
    text=source()
    assert 'def pending_action_summary(' in text
    assert "pending.get('action'" in text and "pending.get('id'" in text
    assert "pending.get('error'" in text and "pending.get('backup'" in text
    assert 'messagebox.showwarning' in text
    tree=ast.parse(text)
    start=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='start_selected_path')
    assert any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and
               n.func.id=='reconcile_known_template_no_text' for n in ast.walk(start))

def test_hud_clarifies_build_only_pause_boundary_without_blocking_start():
    text=source()
    assert "config.get('selected_goal')=='Build only'" in text
    assert 'Build only pauses after the current build is verified' in text
    assert 'select Named goal for explicit' in text
    assert "config['paused']=False" in text

def test_bundled_stoic_compatibility_note_is_searchable(tmp_path):
    from src.source_knowledge import KnowledgeStore
    repo=Path(__file__).resolve().parents[1]
    note=json.loads((repo/'data'/'compatibility_notes.json').read_text(encoding='utf-8'))['notes'][0]
    store=KnowledgeStore(tmp_path/'knowledge.sqlite3')
    store.ingest(note['title'],note['source_url'],note['text'],origin=note['origin'],captured_at=note['captured_at'])

    rows=store.search('Stoic Resistance installed 4.3.11')

    assert len(rows)==1
    assert '1e16 coins, not 1e16 faction coins' in rows[0]['text']
    assert 'Older wiki effect descriptions differ' in rows[0]['text']
    assert rows[0]['origin']=='bundled_development_observation'
