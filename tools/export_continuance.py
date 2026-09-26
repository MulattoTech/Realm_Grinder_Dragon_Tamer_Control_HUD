"""Deterministic AI Continuance packager.
Gathers handoff markdown docs, verification state, memory probe results, and git status
into AI_Continuance.zip for zero-loss multi-AI session continuation.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def run_git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except Exception as exc:
        return f"git error: {exc}"

def export_continuance(output_path: Path | None = None) -> Path:
    if output_path is None:
        output_path = ROOT / "AI_Continuance.zip"

    branch = run_git("branch", "--show-current")
    head_commit = run_git("rev-parse", "HEAD")
    git_status = run_git("status", "--short", "--branch")
    git_diff_stat = run_git("diff", "--stat")

    manifest = {
        "export_timestamp": time.time(),
        "export_iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "branch": branch,
        "head_commit": head_commit,
        "git_status": git_status,
        "git_diff_stat": git_diff_stat,
        "files_included": []
    }

    files_to_pack = [
        ROOT / "docs" / "CURRENT-HANDOFF.md",
        ROOT / "docs" / "AI-CONTINUANCE.md",
        ROOT / "docs" / "CLAUDE-HANDOFF.md",
        ROOT / "docs" / "AUTOPILOT-TARGET-ARCHITECTURE.md",
        ROOT / "state" / "memory_probe_results.json",
        ROOT / "state" / "memory_mappings.json",
    ]

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in files_to_pack:
            if p.exists():
                arcname = str(p.relative_to(ROOT))
                zf.write(p, arcname=arcname)
                manifest["files_included"].append(arcname)

        # Write manifest directly into zip
        zf.writestr("continuance_manifest.json", json.dumps(manifest, indent=2))

    size_kb = output_path.stat().st_size / 1024.0
    print(f"[+] Packaged {len(manifest['files_included'])} files into {output_path.name} ({size_kb:.1f} KB)")
    print(f"[+] Branch: {branch} @ {head_commit[:8]}")
    return output_path

if __name__ == "__main__":
    export_continuance()
