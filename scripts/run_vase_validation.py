from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from build_scad import build_scad, repo_path
from inspect_gcode import inspect_gcode
from inspect_stl import inspect_stl
from report import write_reports
from slice_prusa import slice_prusa


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _overall_status(report: dict[str, Any]) -> str:
    required = [
        report.get("build", {}).get("status"),
        report.get("stl", {}).get("status"),
        report.get("slicer", {}).get("status"),
        report.get("gcode", {}).get("zero_retraction", {}).get("status"),
        report.get("gcode", {}).get("continuity", {}).get("status"),
        report.get("gcode", {}).get("vase_profile", {}).get("status"),
        report.get("gcode", {}).get("feature_types", {}).get("status"),
        report.get("gcode", {}).get("internal_structure", {}).get("status"),
        report.get("gcode", {}).get("edge_coverage", {}).get("status"),
    ]
    return "pass" if all(status in {"pass", "skipped"} for status in required) else "fail"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "config" / "vase_validation.json"
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    report: dict[str, Any] = {"status": "fail", "config": str(config_path)}
    try:
        config = _load_config(config_path)
    except Exception as exc:  # noqa: BLE001 - top-level CLI should report configuration errors plainly.
        print(f"Failed to read config: {exc}", file=sys.stderr)
        return 2

    build = build_scad(config, repo_root)
    report["build"] = build
    if build.get("status") != "pass":
        report["status"] = "fail"
        write_reports(report, config, repo_root)
        print(f"OpenSCAD failed: {build.get('error')}", file=sys.stderr)
        return 1

    report["stl_clean"] = {
        "status": "skipped",
        "reason": "Validation uses the raw OpenSCAD STL; clean_stl.py is intentionally not part of the pipeline.",
        "path": str(repo_path(repo_root, config["output_stl"])),
    }

    stl = inspect_stl(repo_path(repo_root, config["output_stl"]))
    report["stl"] = stl

    slicer = slice_prusa(config, repo_root)
    report["slicer"] = slicer
    if slicer.get("status") != "pass":
        report["status"] = "fail"
        write_reports(report, config, repo_root)
        print(f"PrusaSlicer failed: {slicer.get('error')}", file=sys.stderr)
        return 1

    gcode = inspect_gcode(repo_path(repo_root, config["output_gcode"]), config)
    report["gcode"] = gcode
    report["status"] = _overall_status(report)
    write_reports(report, config, repo_root)

    print(f"Validation {report['status'].upper()}")
    print(f"Markdown report: {report['report_md']}")
    print(f"JSON report: {report['report_json']}")
    print(f"Extent plot: {report['extent_plot']}")
    print(f"XY preview: {report['extrusion_xy_preview']}")
    print(f"Z sample preview: {report['extrusion_z_samples']}")
    estimates = report.get("gcode", {}).get("slicer_estimates", {})
    if estimates:
        print(
            "Slicer estimate: "
            f"{estimates.get('print_time_normal', 'unknown')} normal, "
            f"{estimates.get('filament_used_mm', 'unknown')} mm filament"
        )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
