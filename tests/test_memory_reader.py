"""Read-only telemetry tests: fake memory plus a controlled child process."""
import ast
import ctypes
import importlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]

def api():
    assert (ROOT / 'src/memory/process.py').exists(), 'Read-only memory reader is not implemented'
    return importlib.import_module('src.memory.process'), importlib.import_module('src.memory.scanner')

class FakeProcess:
    def __init__(self, data, base=4096):
        p, _ = api()
        self.data, self.base = data, base
        self.identity = p.ProcessIdentity(17, 123456, 'RealmGrinderDesktop.exe', 8)
        self.reads = []
    def is_alive(self):
        return True
    def query_regions(self):
        p, _ = api()
        yield p.MemoryRegion(self.base, len(self.data), 0x1000, 0x04, 0x20000)
    def read_bytes(self, address, size):
        self.reads.append((address, size))
        offset = address - self.base
        if offset < 0 or offset + size > len(self.data):
            raise OSError('Invalid read')
        return self.data[offset:offset + size]
    def read_value(self, address, datatype):
        p, _ = api()
        fmt = p.TYPE_FORMATS[datatype]
        return struct.unpack(fmt, self.read_bytes(address, struct.calcsize(fmt)))[0]


def test_access_rights_are_read_only_and_not_configurable():
    p, _ = api()
    assert p.READ_ACCESS == 0x410
    import inspect
    assert 'access' not in inspect.signature(p.ReadOnlyProcess).parameters
    for file in (ROOT / 'src/memory').glob('*.py'):
        tree = ast.parse(file.read_text(encoding='utf-8'))
        banned = {'WriteProcessMemory', 'VirtualProtectEx', 'CreateRemoteThread', 'NtWriteVirtualMemory'}
        assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in banned]

@pytest.mark.parametrize('state,protection,readable', [
    (0x1000, 0x04, True), (0x1000, 0x02, True), (0x1000, 0x20, True),
    (0x1000, 0x104, False), (0x1000, 0x01, False), (0x1000, 0x10, False),
    (0x2000, 0x04, False), (0x10000, 0x04, False),
])
def test_region_filter(state, protection, readable):
    p, _ = api()
    assert p.MemoryRegion(4096, 4096, state, protection, 0x20000).readable is readable

@pytest.mark.parametrize('datatype,value', [('Float64', 812.55), ('Float32', 12.5),
    ('Int32', -123456), ('UInt32', 4000000000), ('Int64', -(2**50)),
    ('UInt64', 2**60), ('Byte', 213)])
def test_exact_numeric_scan(datatype, value):
    p, s = api()
    data = b'\x00'*13 + struct.pack(p.TYPE_FORMATS[datatype], value) + b'\x00'*19
    process = FakeProcess(data)
    result = s.BoundedScanner(process, chunk_bytes=16).scan_exact(value, datatype)
    assert [c.address for c in result.candidates] == [4109]
    assert result.bytes_scanned == len(data)
    assert not result.truncated

@pytest.mark.parametrize('datatype,value,encoded', [
    ('Ascii', 'realm-test', b'realm-test'), ('UTF16', 'mana-test', 'mana-test'.encode('utf-16-le'))])
def test_string_scan_crosses_chunk_boundaries(datatype, value, encoded):
    _, s = api()
    process = FakeProcess(b'x'*13 + encoded + b'x'*30)
    result = s.BoundedScanner(process, chunk_bytes=16).scan_exact(value, datatype)
    assert [c.address for c in result.candidates] == [4109]

@pytest.mark.parametrize('mode,new,expected', [
    ('CHANGED', 90.0, 1), ('UNCHANGED', 100.0, 1),
    ('DECREASED', 90.0, 1), ('INCREASED', 110.0, 1),
    ('DECREASED', 110.0, 0), ('INCREASED', 90.0, 0),
    ('CHANGED', float('nan'), 0)])
def test_differential_narrowing(mode, new, expected):
    _, s = api()
    process = FakeProcess(struct.pack('<d', 100.0))
    scanner = s.BoundedScanner(process)
    result = scanner.scan_exact(100.0)
    process.data = struct.pack('<d', new)
    narrowed = scanner.narrow(result, mode)
    assert len(narrowed.candidates) == expected


def test_range_scan_and_comparisons():
    _, s = api()
    process = FakeProcess(struct.pack('<dddd', 50.0, 100.0, 150.0, float('nan')))
    scanner = s.BoundedScanner(process)
    result = scanner.scan_range(90, 160)
    assert [c.value for c in result.candidates] == [100.0, 150.0]
    assert len(scanner.narrow(result, 'GREATER_THAN', 120).candidates) == 1
    assert len(scanner.narrow(result, 'LESS_THAN', 120).candidates) == 1
    assert len(scanner.narrow(result, 'RANGE', (95, 110)).candidates) == 1


def test_scan_budgets_are_enforced():
    _, s = api()
    process = FakeProcess(struct.pack('<d', 88.0)*100)
    result = s.BoundedScanner(process, max_bytes=80, chunk_bytes=16).scan_exact(88.0)
    assert result.bytes_scanned <= 80 and result.truncated
    result = s.BoundedScanner(process, max_candidates=3, chunk_bytes=16).scan_exact(88.0)
    assert len(result.candidates) == 3 and result.truncated


def test_guard_page_is_not_read_even_when_supplied_directly():
    p, s = api()
    process = FakeProcess(struct.pack('<d', 88.0))
    region = p.MemoryRegion(4096, 8, 0x1000, 0x104, 0x20000)
    result = s.BoundedScanner(process).scan_exact(88.0, regions=[region])
    assert result.candidates == [] and process.reads == []


def test_pid_reuse_invalidates_candidates():
    p, s = api()
    process = FakeProcess(struct.pack('<d', 88.0))
    scanner = s.BoundedScanner(process)
    result = scanner.scan_exact(88.0)
    process.identity = p.ProcessIdentity(17, 999999, 'RealmGrinderDesktop.exe', 8)
    with pytest.raises(ValueError, match='session'):
        scanner.narrow(result, 'UNCHANGED')

@pytest.fixture
def helper():
    if os.name != 'nt':
        pytest.skip('Live Win32 helper test')
    script = "import ctypes,json,os,sys\nx=ctypes.c_double(31415.926535)\nprint(json.dumps({'pid':os.getpid(),'address':ctypes.addressof(x)}),flush=True)\nfor line in sys.stdin:\n x.value=float(line); print(x.value,flush=True)\n"
    child = subprocess.Popen([sys.executable, '-u', '-c', script], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    info = json.loads(child.stdout.readline())
    yield child, info
    child.stdin.close()
    child.wait(timeout=5)


def test_live_helper_read_attach_close_reopen_and_narrow(helper):
    p, s = api()
    child, info = helper
    reader = p.ReadOnlyProcess(info['pid'], expected_exe=Path(sys.executable).name)
    reader.open()
    identity = reader.identity
    try:
        assert identity.pointer_size == ctypes.sizeof(ctypes.c_void_p)
        assert reader.read_double(info['address']) == pytest.approx(31415.926535)
        regions = list(reader.query_regions(start=info['address'], end=info['address']+8))
        assert regions and regions[0].readable
        scanregion = p.MemoryRegion(info['address'], 8, 0x1000, 0x04, 0x20000)
        scanner = s.BoundedScanner(reader)
        result = scanner.scan_exact(31415.926535, regions=[scanregion])
        child.stdin.write('12345.5\n'); child.stdin.flush(); child.stdout.readline()
        assert len(scanner.narrow(result, 'DECREASED').candidates) == 1
        assert reader.read_double(info['address']) == 12345.5
        reader.close()
        assert not reader.is_alive()
        reader.open()
        assert reader.identity == identity
    finally:
        reader.close()


def test_live_wrong_executable_rejected(helper):
    p, _ = api()
    _, info = helper
    with pytest.raises(PermissionError, match='executable'):
        p.ReadOnlyProcess(info['pid']).open()


def test_avm2_numeric_atoms_follow_boxed_value_and_inline_integer():
    p, _ = api()
    assert hasattr(p.ReadOnlyProcess, 'read_avm2_number'), 'AVM2 numeric Atom reader is missing'
    reader = p.ReadOnlyProcess(17)
    reader.identity = p.ProcessIdentity(17, 1, 'RealmGrinderDesktop.exe', 4)
    memory = {4096: (23161 << 3) | 6}
    reader.read_pointer = lambda address: memory[address]
    reader.read_double = lambda address: {8192: 812.5, 12288: 923.5}[address]
    assert reader.read_avm2_number(4096) == 23161
    memory[4096] = 8192 | 7
    assert reader.read_avm2_number(4096) == 812.5
    memory[4096] = 12288 | 7
    assert reader.read_avm2_number(4096) == 923.5
    memory[4096] = ((-3 << 3) | 6) & 0xffffffff
    assert reader.read_avm2_number(4096) == -3
    memory[4096] = 5  # Boolean is not numeric mana.
    with pytest.raises(ValueError, match='numeric'):
        reader.read_avm2_number(4096)


def test_avm2_atom_rejects_unstable_pointer_sample():
    p, _ = api()
    assert hasattr(p.ReadOnlyProcess, 'read_avm2_number'), 'AVM2 numeric Atom reader is missing'
    reader = p.ReadOnlyProcess(17)
    reader.identity = p.ProcessIdentity(17, 1, 'RealmGrinderDesktop.exe', 4)
    calls = 0
    def pointer(_):
        nonlocal calls
        calls += 1
        return (8192 if calls % 2 else 12288) | 7
    reader.read_pointer = pointer
    reader.read_double = lambda address: 812.5
    with pytest.raises(OSError, match='changed'):
        reader.read_avm2_number(4096)
