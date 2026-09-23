"""Bounded numeric/string discovery and session-safe candidate narrowing."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import struct
import time
from .process import ProcessIdentity, TYPE_FORMATS

@dataclass(frozen=True)
class Candidate:
    address: int
    value: object
    datatype: str

@dataclass
class ScanResult:
    identity: ProcessIdentity
    candidates: list[Candidate] = field(default_factory=list)
    bytes_scanned: int = 0
    truncated: bool = False
    elapsed_seconds: float = 0.0
    read_errors: int = 0

class BoundedScanner:
    def __init__(self, process, max_bytes=512*1024*1024, max_seconds=10.0,
                 max_candidates=50000, chunk_bytes=1024*1024):
        if min(max_bytes, max_seconds, max_candidates, chunk_bytes) <= 0:
            raise ValueError('Scan budgets must be positive')
        self.process = process
        self.max_bytes, self.max_seconds = int(max_bytes), float(max_seconds)
        self.max_candidates = int(max_candidates)
        self.chunk_bytes = min(int(chunk_bytes), 8*1024*1024)

    def _scan(self, datatype, needle=None, bounds=None, regions=None):
        if not self.process.is_alive() or not self.process.identity:
            raise OSError('No live process session')
        result = ScanResult(self.process.identity)
        started = time.monotonic()
        width = len(needle) if needle is not None else struct.calcsize(TYPE_FORMATS[datatype])
        for region in regions if regions is not None else self.process.query_regions():
            if not region.readable:
                continue
            cursor, carry = region.base, b''
            while cursor < region.base + region.size:
                if result.bytes_scanned >= self.max_bytes or time.monotonic()-started >= self.max_seconds:
                    result.truncated = True
                    result.elapsed_seconds = time.monotonic()-started
                    return result
                size = min(self.chunk_bytes, region.base+region.size-cursor,
                           self.max_bytes-result.bytes_scanned)
                try:
                    block = self.process.read_bytes(cursor, size)
                except OSError:
                    result.read_errors += 1
                    result.bytes_scanned += size  # Budget failed reads too.
                    cursor += size
                    carry = b''
                    continue
                result.bytes_scanned += size
                data, base = carry + block, cursor-len(carry)
                if needle is not None:
                    offsets = []
                    offset = data.find(needle)
                    while offset >= 0:
                        offsets.append(offset)
                        if len(offsets) >= self.max_candidates - len(result.candidates):
                            break
                        offset = data.find(needle, offset+1)
                    for offset in offsets:
                        if datatype in TYPE_FORMATS:
                            value = struct.unpack_from(TYPE_FORMATS[datatype], data, offset)[0]
                        else:
                            value = needle.decode('ascii' if datatype == 'Ascii' else 'utf-16-le')
                        result.candidates.append(Candidate(base+offset, value, datatype))
                else:
                    alignment = (-base) % width
                    end = len(data)-width+1
                    for offset in range(alignment, end, width):
                        value = struct.unpack_from(TYPE_FORMATS[datatype], data, offset)[0]
                        if math.isfinite(value) and bounds[0] <= value <= bounds[1]:
                            result.candidates.append(Candidate(base+offset, value, datatype))
                            if len(result.candidates) >= self.max_candidates:
                                break
                if len(result.candidates) >= self.max_candidates:
                    result.truncated = True
                    result.elapsed_seconds = time.monotonic()-started
                    return result
                carry = data[-(width-1):] if width > 1 else b''
                cursor += size
        result.elapsed_seconds = time.monotonic()-started
        return result

    def scan_exact(self, value, datatype='Float64', regions=None):
        if datatype in TYPE_FORMATS:
            if not math.isfinite(value):
                raise ValueError('A finite numeric anchor is required')
            needle = struct.pack(TYPE_FORMATS[datatype], value)
        elif datatype in ('Ascii', 'UTF16'):
            needle = value.encode('ascii' if datatype == 'Ascii' else 'utf-16-le')
            if not needle or len(needle) > 4096:
                raise ValueError('String anchors must have 1..4096 encoded bytes')
        else:
            raise ValueError(f'Unknown datatype: {datatype}')
        return self._scan(datatype, needle=needle, regions=regions)

    def scan_range(self, minimum, maximum, datatype='Float64', regions=None):
        if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum > maximum:
            raise ValueError('A finite ordered range is required')
        return self._scan(datatype, bounds=(minimum, maximum), regions=regions)

    def narrow(self, previous: ScanResult, mode: str, value=None) -> ScanResult:
        if previous.identity != self.process.identity or not self.process.is_alive():
            raise ValueError('Candidates belong to a different or expired process session')
        mode = mode.upper()
        if mode not in ('EXACT', 'CHANGED', 'UNCHANGED', 'INCREASED', 'DECREASED',
                        'GREATER_THAN', 'LESS_THAN', 'RANGE'):
            raise ValueError(f'Unknown comparison: {mode}')
        result = ScanResult(previous.identity)
        started = time.monotonic()
        for candidate in previous.candidates:
            if time.monotonic()-started >= self.max_seconds or result.bytes_scanned >= self.max_bytes:
                result.truncated = True
                break
            try:
                if candidate.datatype in TYPE_FORMATS:
                    current = self.process.read_value(candidate.address, candidate.datatype)
                    result.bytes_scanned += struct.calcsize(TYPE_FORMATS[candidate.datatype])
                    if not math.isfinite(current):
                        continue
                else:
                    encoding = 'ascii' if candidate.datatype == 'Ascii' else 'utf-16-le'
                    size = len(candidate.value.encode(encoding))
                    current = self.process.read_bytes(candidate.address, size).decode(encoding)
                    result.bytes_scanned += size
                old = candidate.value
                matched = ((mode == 'EXACT' and current == value) or
                           (mode == 'CHANGED' and current != old) or
                           (mode == 'UNCHANGED' and current == old) or
                           (mode == 'INCREASED' and current > old) or
                           (mode == 'DECREASED' and current < old) or
                           (mode == 'GREATER_THAN' and current > value) or
                           (mode == 'LESS_THAN' and current < value) or
                           (mode == 'RANGE' and value[0] <= current <= value[1]))
                if matched:
                    result.candidates.append(Candidate(candidate.address, current, candidate.datatype))
            except (OSError, UnicodeError):
                result.read_errors += 1
        result.elapsed_seconds = time.monotonic()-started
        return result
