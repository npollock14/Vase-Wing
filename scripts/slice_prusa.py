from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from build_scad import repo_path


def slice_prusa(config: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    exe = Path(config["prusaslicer_exe"])
    profile = repo_path(repo_root, config["prusa_profile"])
    stl = repo_path(repo_root, config["output_stl"])
    gcode = repo_path(repo_root, config["output_gcode"])
    stdout_path = repo_path(repo_root, config["slice_stdout"])
    stderr_path = repo_path(repo_root, config["slice_stderr"])

    result: dict[str, Any] = {
        "stage": "prusaslicer",
        "status": "fail",
        "output_gcode": str(gcode),
    }

    if not exe.exists():
        result["error"] = f"PrusaSlicer executable not found: {exe}"
        return result
    if not profile.exists():
        result["error"] = f"PrusaSlicer profile not found: {profile}"
        return result
    if not stl.exists():
        result["error"] = f"Input STL not found: {stl}"
        return result

    gcode.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(exe),
        "--load",
        str(profile),
        "--export-gcode",
        "--output",
        str(gcode),
        "--spiral-vase",
        "--perimeters=1",
        "--fill-density=0%",
        "--top-solid-layers=0",
        "--bottom-solid-layers=0",
        "--no-support-material",
        "--skirts=0",
        "--brim-width=0",
        "--retract-length=0",
        "--filament-retract-length=0",
        "--retract-lift=0",
        "--filament-retract-lift=0",
        "--no-retract-layer-change",
        "--seam-gap-distance=0",
        "--slice-closing-radius=0",
        "--no-binary-gcode",
        "--gcode-comments",
        str(stl),
    ]

    result["command"] = cmd
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    stdout_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(proc.stderr, encoding="utf-8", errors="replace")
    result["returncode"] = proc.returncode
    result["stdout"] = str(stdout_path)
    result["stderr"] = str(stderr_path)

    if proc.returncode != 0:
        result["error"] = f"PrusaSlicer failed with exit code {proc.returncode}"
        return result
    if not gcode.exists() or gcode.stat().st_size == 0:
        result["error"] = "PrusaSlicer completed but did not produce a non-empty G-code file"
        return result

    head = gcode.read_bytes()[:256]
    if b"\x00" in head:
        result["error"] = "G-code appears to be binary; disable binary_gcode"
        return result

    result["status"] = "pass"
    result["gcode_bytes"] = gcode.stat().st_size
    return result
