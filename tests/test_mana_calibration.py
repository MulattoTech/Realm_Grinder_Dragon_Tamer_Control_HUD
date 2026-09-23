from pathlib import Path
import importlib

def api():
    assert Path('src/memory/calibration.py').exists(), 'Controlled calibration is missing'
    return importlib.import_module('src.memory.calibration')

def test_two_drops_and_regeneration_prove_a_candidate():
    rows=[(0,1000),(0.1,800),(0.6,802),(1.1,804),(2.1,608),(2.6,610),(3.1,612)]
    assert api().validate_mana_trace(rows,[0.05,2.05],200)['verified']

def test_constant_maximum_or_cache_is_rejected():
    rows=[(0,1000),(0.1,1000),(0.6,1000),(1.1,1000),(2.1,1000),(2.6,1000),(3.1,1000)]
    assert not api().validate_mana_trace(rows,[0.05,2.05],200)['verified']

def test_only_one_cast_is_not_sufficient():
    assert not api().validate_mana_trace([(0,1000),(0.2,800),(1,805)],[0.1],200)['verified']

def test_nonfinite_and_wrong_cost_are_rejected():
    rows=[(0,1000),(0.1,900),(0.6,902),(1.1,904),(2.1,808),(2.6,810),(3.1,812)]
    assert not api().validate_mana_trace(rows,[0.05,2.05],200)['verified']
