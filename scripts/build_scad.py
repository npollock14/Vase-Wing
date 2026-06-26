from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def _format_define_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    return str(value)


def build_scad(config: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    exe = Path(config["openscad_exe"])
    scad = repo_path(repo_root, config["scad_entrypoint"])
    output_stl = repo_path(repo_root, config["output_stl"])
    summary = repo_path(repo_root, config["openscad_summary"])
    stdout_path = repo_path(repo_root, config["build_stdout"])
    stderr_path = repo_path(repo_root, config["build_stderr"])

    output_stl.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "stage": "openscad",
        "status": "fail",
        "output_stl": str(output_stl),
        "summary": str(summary),
    }

    if not exe.exists():
        result["error"] = f"OpenSCAD executable not found: {exe}"
        return result
    if not scad.exists():
        result["error"] = f"SCAD entrypoint not found: {scad}"
        return result

    cmd = [
        str(exe),
        "--backend",
        config.get("openscad_backend", "Manifold"),
        "--summary",
        "all",
        "--summary-file",
        str(summary),
        "-o",
        str(output_stl),
    ]
    for name, value in config.get("openscad_defines", {}).items():
        cmd.extend(["-D", f"{name}={_format_define_value(value)}"])
    cmd.append(str(scad))

    result["command"] = cmd
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    stdout_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(proc.stderr, encoding="utf-8", errors="replace")

    result["returncode"] = proc.returncode
    result["stdout"] = str(stdout_path)
    result["stderr"] = str(stderr_path)
    if proc.returncode != 0:
        result["error"] = f"OpenSCAD failed with exit code {proc.returncode}"
        return result
    if not output_stl.exists() or output_stl.stat().st_size == 0:
        result["error"] = "OpenSCAD completed but did not produce a non-empty STL"
        return result

    result["status"] = "pass"
    result["stl_bytes"] = output_stl.stat().st_size
    if summary.exists():
        try:
            result["openscad_summary"] = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result["openscad_summary_error"] = "Summary file was not valid JSON"
    return result
