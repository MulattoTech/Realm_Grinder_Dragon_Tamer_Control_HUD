from pathlib import Path
import ast

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

def test_stoic_source_conflict_is_explicit_in_reference_index():
    from src.source_knowledge import KnowledgeStore
    rows=KnowledgeStore().search('Stoic Resistance installed 4.3.11')
    assert rows and any('1e16' in row['text'] for row in rows)
