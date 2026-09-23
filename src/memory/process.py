"""Minimal Win32 observation wrapper. No write-capable process operations exist here."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
from dataclasses import dataclass
import os
from pathlib import Path
import struct
from typing import Iterator

READ_ACCESS = 0x0410  # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, not configurable.
TYPE_FORMATS = {'Float64': '<d', 'Float32': '<f', 'Int32': '<i', 'UInt32': '<I',
                'Int64': '<q', 'UInt64': '<Q', 'Byte': '<B'}

@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_time: int
    exe_path: str
    pointer_size: int

@dataclass(frozen=True)
class MemoryRegion:
    base: int
    size: int
    state: int
    protection: int
    type: int

    @property
    def readable(self) -> bool:
        return bool(self.size > 0 and self.state == 0x1000 and
                    not self.protection & 0x100 and
                    self.protection & 0xff in (0x02, 0x04, 0x08, 0x20, 0x40, 0x80))

class _MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', w.DWORD)]
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        _fields_ += [('PartitionId', w.WORD)]
    _fields_ += [('RegionSize', ctypes.c_size_t), ('State', w.DWORD),
                ('Protect', w.DWORD), ('Type', w.DWORD)]

class ReadOnlyProcess:
    """Own one non-inheritable read-only handle; validate the executable before any read."""
    def __init__(self, pid: int, expected_exe: str = 'RealmGrinderDesktop.exe'):
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError('A positive process ID is required')
        if not expected_exe:
            raise ValueError('An expected executable is required')
        self.pid, self.expected_exe = pid, expected_exe
        self.handle = None
        self.identity = None
        self._api = None

    def _bind(self):
        if os.name != 'nt':
            raise OSError('Win32 process observation requires Windows')
        if self._api is not None:
            return self._api
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            'CloseHandle': ([w.HANDLE], w.BOOL),
            'QueryFullProcessImageNameW': ([w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)], w.BOOL),
            'GetProcessTimes': ([w.HANDLE] + [ctypes.POINTER(w.FILETIME)]*4, w.BOOL),
            'GetExitCodeProcess': ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            'ReadProcessMemory': ([w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)], w.BOOL),
            'VirtualQueryEx': ([w.HANDLE, ctypes.c_void_p, ctypes.POINTER(_MBI),
                                ctypes.c_size_t], ctypes.c_size_t),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(k, name)
            fn.argtypes, fn.restype = args, result
        self._api = k
        return k

    def open(self) -> 'ReadOnlyProcess':
        self.close()
        k = self._bind()
        h = k.OpenProcess(READ_ACCESS, False, self.pid)
        if not h:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle = h
        try:
            length = w.DWORD(32768)
            path = ctypes.create_unicode_buffer(length.value)
            if not k.QueryFullProcessImageNameW(h, 0, path, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            actual = path.value
            expected = self.expected_exe
            matches = (os.path.normcase(actual) == os.path.normcase(expected) if
                       os.path.isabs(expected) else Path(actual).name.casefold() == expected.casefold())
            if not matches:
                raise PermissionError(f'Unexpected executable: {actual}; expected {expected}')
            times = [w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(h, *(ctypes.byref(t) for t in times)):
                raise ctypes.WinError(ctypes.get_last_error())
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            if hasattr(k, 'IsWow64Process2'):
                fn = k.IsWow64Process2
                fn.argtypes = [w.HANDLE, ctypes.POINTER(w.WORD), ctypes.POINTER(w.WORD)]
                fn.restype = w.BOOL
                target, native = w.WORD(), w.WORD()
                if not fn(h, ctypes.byref(target), ctypes.byref(native)):
                    raise ctypes.WinError(ctypes.get_last_error())
                machine = target.value or native.value
                if machine not in (0x14c, 0x1c4, 0x8664, 0xaa64):
                    raise OSError(f'Unsupported target architecture: {machine:#x}')
                pointer_size = 4 if machine in (0x14c, 0x1c4) else 8
            else:
                k.IsWow64Process.argtypes = [w.HANDLE, ctypes.POINTER(w.BOOL)]
                k.IsWow64Process.restype = w.BOOL
                wow = w.BOOL()
                if not k.IsWow64Process(h, ctypes.byref(wow)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if ctypes.sizeof(ctypes.c_void_p) < 8:
                    raise OSError('Use 64-bit Python when IsWow64Process2 is unavailable')
                pointer_size = 4 if wow.value else 8
            if pointer_size > ctypes.sizeof(ctypes.c_void_p):
                raise OSError('Use a 64-bit observer for this target')
            self.identity = ProcessIdentity(self.pid, created, actual, pointer_size)
            if not self.is_alive():
                raise OSError('Target exited during attachment')
            return self
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.handle:
            self._api.CloseHandle(self.handle)
        self.handle = None
        self.identity = None

    def reconnect(self) -> 'ReadOnlyProcess':
        return self.open()

    def process_identity(self) -> ProcessIdentity:
        if not self.identity or not self.is_alive():
            raise OSError('No live process session')
        return self.identity

    def is_alive(self) -> bool:
        if not self.handle:
            return False
        code = w.DWORD()
        return bool(self._api.GetExitCodeProcess(self.handle, ctypes.byref(code)) and code.value == 259)

    def query_regions(self, start: int = 0, end: int | None = None) -> Iterator[MemoryRegion]:
        identity = self.process_identity()
        limit = min(end if end is not None else 1 << (8*identity.pointer_size),
                    0x100000000 if identity.pointer_size == 4 else 0x0000800000000000)
        cursor = max(0, start)
        while cursor < limit:
            info = _MBI()
            count = self._api.VirtualQueryEx(self.handle, ctypes.c_void_p(cursor),
                                            ctypes.byref(info), ctypes.sizeof(info))
            if not count:
                break  # Includes the normal end of the target's address space.
            base, size = int(info.BaseAddress or 0), int(info.RegionSize)
            if size <= 0 or base + size <= cursor:
                raise OSError('VirtualQueryEx returned a non-advancing region')
            yield MemoryRegion(base, size, info.State, info.Protect, info.Type)
            cursor = base + size

    def read_bytes(self, address: int, size: int) -> bytes:
        if not self.handle or not self.identity:
            raise OSError('Process handle is closed')
        if not isinstance(address, int) or not isinstance(size, int) or address < 0 or size < 0:
            raise ValueError('Address and size must be non-negative integers')
        if size > 8*1024*1024 or address + size > 1 << (8*self.identity.pointer_size):
            raise ValueError('Read exceeds the bounded target address range')
        if size == 0:
            return b''
        buffer = ctypes.create_string_buffer(size)
        actual = ctypes.c_size_t()
        ok = self._api.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer,
                                        size, ctypes.byref(actual))
        if not ok or actual.value != size:
            raise OSError(ctypes.get_last_error(), f'Incomplete process read at {address:#x}: {actual.value}/{size}')
        return buffer.raw

    def read_avm2_number(self, address: int):
        """Read a numeric Atom slot, following a moving boxed double without modifying it.

        Encoding is documented in adobe/avmplus core/atom.h: tag 6 is a signed
        pointer-sized integer shifted by 3; tag 7 is an aligned double pointer.
        Read the slot twice to reject a replacement during dereference.
        """
        if self.identity is None:
            raise OSError('No process identity')
        bits = self.identity.pointer_size * 8
        for _ in range(3):
            atom = self.read_pointer(address)
            tag = atom & 7
            if tag == 6:
                signed = atom - (1 << bits) if atom & (1 << (bits-1)) else atom
                return signed >> 3
            if tag != 7 or (atom & ~7) == 0:
                raise ValueError('AVM2 slot is not a numeric Atom')
            number = self.read_double(atom & ~7)
            if self.read_pointer(address) == atom:
                return number
        raise OSError('AVM2 numeric slot changed during read')

    def read_value(self, address: int, datatype: str):
        if datatype == 'AVM2Number':
            return self.read_avm2_number(address)
        fmt = TYPE_FORMATS[datatype]
        return struct.unpack(fmt, self.read_bytes(address, struct.calcsize(fmt)))[0]

    def read_int32(self, address): return self.read_value(address, 'Int32')
    def read_uint32(self, address): return self.read_value(address, 'UInt32')
    def read_int64(self, address): return self.read_value(address, 'Int64')
    def read_uint64(self, address): return self.read_value(address, 'UInt64')
    def read_float(self, address): return self.read_value(address, 'Float32')
    def read_double(self, address): return self.read_value(address, 'Float64')
    def read_pointer(self, address):
        return self.read_uint64(address) if self.process_identity().pointer_size == 8 else self.read_uint32(address)
    def read_ascii(self, address, length=256):
        return self.read_bytes(address, min(max(0, length), 4096)).split(b'\0', 1)[0].decode('ascii', errors='strict')
    def read_utf16(self, address, length=256):
        return self.read_bytes(address, min(max(0, length), 4096)*2).decode('utf-16-le', errors='strict').split('\0', 1)[0]
    def __enter__(self): return self.open()
    def __exit__(self, *exc): self.close()
