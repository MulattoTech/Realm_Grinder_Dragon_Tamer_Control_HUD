"""Standalone, non-intrusive probe script for Adobe AIR / AVM2 memory.
Scans readable memory regions, discovers volatile field slots (mana_current, mana_max,
mana_regeneration, coins, fairy_assistants), verifies dynamic slopes, and outputs results.
"""
from __future__ import annotations
import ctypes
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.memory.process import ReadOnlyProcess
from src.memory.provider import MemoryProvider, FieldMapping
from src.save_reader import get_current_game_state
from src.window import RealmGrinderWindow
from src.atomic_store import write_json

def ensure_game_running(max_wait_seconds: float = 20.0) -> int:
    """Require an existing game; an observation probe must not launch or restore it."""
    window = RealmGrinderWindow()
    if window.find_window():
        return window.pid

    raise RuntimeError('Realm Grinder must be already running; the read-only probe will not launch it')

def probe_memory() -> dict:
    print("=======================================================")
    print("   REALM GRINDER ADOBE AIR / AVM2 MEMORY PROBE         ")
    print("=======================================================")
    pid = ensure_game_running()
    print(f"[+] Target Process: RealmGrinderDesktop.exe (PID {pid})")

    # Read current persistent save state for anchors
    save = get_current_game_state()
    print(f"[+] Save Anchors: R={save.get('reincarnation')}, Gems={save.get('gems'):.3e}, Coins={save.get('coins'):.3e}, Exc={save.get('excavations')}")

    state_dir = ROOT / "state"
    provider = MemoryProvider(state_dir, discovery_enabled=True)
    provider._connect()
    if not provider.reader:
        raise RuntimeError("Failed to attach ReadOnlyProcess to Realm Grinder")

    # Wait for AIR heap stabilization
    print("[*] Verifying memory heap stability...")
    for _ in range(25):
        try:
            readable = [r for r in provider.reader.query_regions() if r.readable]
            total_mb = sum(r.size for r in readable) / (1024 * 1024)
            if total_mb >= 300.0:
                print(f"[+] Heap stable: {len(readable)} readable regions, {total_mb:.1f} MB.")
                break
        except Exception:
            pass
        time.sleep(0.8)

    # Perform AVM2 atom discovery
    print("[*] Running multi-stage AVM2 atom discovery...")
    discovered = provider.discover_fields(save, sample_delay=0.6)
    print(f"[+] Discovered {len(discovered)} volatile field mappings:")
    for name, mapping in discovered.items():
        val = provider.reader.read_value(mapping.address, mapping.datatype)
        print(f"    - {name:20s}: Address={mapping.address:#010x}, Type={mapping.datatype}, Value={val}")

    # Sample provider observations
    observations, health = provider.sample(save)
    print(f"\n[+] Health: {health.get('memory_provider_health')} | Verified: {health.get('verified_fields')}")

    results = {
        "timestamp": time.time(),
        "pid": pid,
        "identity": asdict(provider.reader.identity) if provider.reader.identity else None,
        "health": health,
        "discovered_mappings": {name: asdict(m) for name, m in discovered.items()},
        "live_observations": observations
    }

    out_file = state_dir / "memory_probe_results.json"
    write_json(out_file, results)
    print(f"[+] Telemetry written to {out_file}")

    provider.close()
    return results

if __name__ == "__main__":
    probe_memory()
