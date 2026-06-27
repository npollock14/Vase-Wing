from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_scad import build_scad, repo_path
from clean_stl import clean_stl
from slice_prusa import slice_prusa

GENERATED_PROFILE = Path(
    "generated/current_wing_gridmode3_centered_margin_lightening_sections39/gridmode3_centered_margin_lightening_cli.ini"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def _tag_number(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def _parse_define(raw_define: str) -> tuple[str, Any]:
    if "=" not in raw_define:
        raise argparse.ArgumentTypeError("defines must use NAME=VALUE syntax")

    name, raw_value = raw_define.split("=", 1)
    name = name.strip()
    raw_value = raw_value.strip()
    if not name:
        raise argparse.ArgumentTypeError("define name cannot be empty")

    lowered = raw_value.lower()
    if lowered == "true":
        return name, True
    if lowered == "false":
        return name, False
    try:
        if any(marker in raw_value for marker in [".", "e", "E"]):
            return name, float(raw_value)
        return name, int(raw_value)
    except ValueError:
        return name, raw_value


def _default_profile(repo_root: Path, config: dict[str, Any]) -> str:
    generated_profile = repo_root / GENERATED_PROFILE
    if generated_profile.exists():
        return str(GENERATED_PROFILE)
    return str(config["prusa_profile"])


def _default_name(args: argparse.Namespace) -> str:
    return "_".join(
        [
            "gm3",
            f"le{_tag_number(args.leading_threshold_mm)}",
            f"te{_tag_number(args.trailing_threshold_mm)}",
            f"moat{_tag_number(args.spar_moat_mm)}",
            f"leE{_tag_number(args.le_entry_overshoot_mm)}",
            f"teE{_tag_number(args.te_entry_overshoot_mm)}",
            f"teMin{_tag_number(args.centerline_trailing_min_airfoil_height_mm)}",
            f"cS{args.centerline_chord_samples}",
        ]
    )


def _make_config(
    args: argparse.Namespace, repo_root: Path, base_config: dict[str, Any]
) -> tuple[dict[str, Any], Path, str]:
    name = args.name or _default_name(args)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else Path("generated") / f"current_wing_{name}_sections{args.wing_sections}"
    )

    defines: dict[str, Any] = {
        "grid_mode": 3,
        "wing_sections": args.wing_sections,
        "wing_mm": args.wing_mm,
        "create_servo_void": args.create_servo_void,
        "spar_hole": args.spar_hole,
        "spar_rib_no_go_enabled": True,
        "spar_rib_no_go_clearance_mm": args.spar_moat_mm,
        "mode3_centerline_le_overshoot_mm": args.le_entry_overshoot_mm,
        "mode3_centerline_te_overshoot_mm": args.te_entry_overshoot_mm,
        "mode3_centerline_start_fraction": args.centerline_start_fraction,
        "mode3_centerline_end_fraction": args.centerline_end_fraction,
        "mode3_centerline_trailing_min_airfoil_height_mm": args.centerline_trailing_min_airfoil_height_mm,
        "mode3_centerline_chord_samples": args.centerline_chord_samples,
        "rib_thin_zone_enabled": True,
        "rib_leading_thin_zone_enabled": True,
        "rib_trailing_thin_zone_enabled": True,
        "rib_leading_min_airfoil_height_mm": args.leading_threshold_mm,
        "rib_trailing_min_airfoil_height_mm": args.trailing_threshold_mm,
    }
    for define_name, define_value in args.define:
        defines[define_name] = define_value

    config = dict(base_config)
    config.update(
        {
            "prusa_profile": args.profile or _default_profile(repo_root, base_config),
            "output_stl": str(output_dir / f"{name}.stl"),
            "output_gcode": str(output_dir / f"{name}.gcode"),
            "openscad_summary": str(output_dir / "openscad-summary.json"),
            "build_stdout": str(output_dir / "openscad.stdout.txt"),
            "build_stderr": str(output_dir / "openscad.stderr.txt"),
            "slice_stdout": str(output_dir / "prusaslicer.stdout.txt"),
            "slice_stderr": str(output_dir / "prusaslicer.stderr.txt"),
            "openscad_timeout_seconds": args.openscad_timeout_seconds,
            "openscad_output_wait_seconds": args.openscad_timeout_seconds,
            "openscad_defines": defines,
        }
    )
    return config, output_dir, name


def _viewer_exe(args: argparse.Namespace, config: dict[str, Any]) -> Path:
    if args.viewer_exe:
        return Path(args.viewer_exe)
    return Path(config["prusaslicer_exe"]).with_name("prusa-gcodeviewer.exe")


def _open_viewer(
    args: argparse.Namespace, config: dict[str, Any], repo_root: Path
) -> dict[str, Any]:
    if not args.open_viewer:
        return {"status": "skipped", "reason": "--no-open-viewer was supplied"}

    viewer = _viewer_exe(args, config)
    gcode = repo_path(repo_root, config["output_gcode"])
    if not viewer.exists():
        return {"status": "skipped", "reason": f"G-code viewer not found: {viewer}"}

    subprocess.Popen([str(viewer), str(gcode)], cwd=repo_root)
    return {"status": "pass", "viewer": str(viewer), "gcode": str(gcode)}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a Vase-Wing STL, clean it, slice G-code, and open Prusa G-code Viewer."
    )
    parser.add_argument(
        "--config",
        default="config/vase_validation.json",
        help="Base JSON config with OpenSCAD and PrusaSlicer paths.",
    )
    parser.add_argument(
        "--profile",
        help="PrusaSlicer profile path. Defaults to the generated CLI profile when present.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory. Defaults to generated/current_wing_<name>_sections<wing_sections>.",
    )
    parser.add_argument(
        "--name",
        help="Artifact basename. Defaults to a name derived from the wing settings.",
    )
    parser.add_argument("--wing-mm", type=float, default=1000)
    parser.add_argument("--wing-sections", type=int, default=39)
    parser.add_argument("--leading-threshold-mm", type=float, default=20)
    parser.add_argument("--trailing-threshold-mm", type=float, default=10)
    parser.add_argument("--spar-moat-mm", type=float, default=0.6)
    parser.add_argument("--le-entry-overshoot-mm", type=float, default=0.6)
    parser.add_argument("--te-entry-overshoot-mm", type=float, default=0.6)
    parser.add_argument("--centerline-start-fraction", type=float, default=0)
    parser.add_argument("--centerline-end-fraction", type=float, default=1)
    parser.add_argument(
        "--centerline-trailing-min-airfoil-height-mm", type=float, default=2
    )
    parser.add_argument("--centerline-chord-samples", type=int, default=64)
    parser.add_argument("--openscad-timeout-seconds", type=float, default=60)
    parser.add_argument(
        "--create-servo-void",
        action="store_true",
        help="Include the servo void. Default is disabled for wing artifact builds.",
    )
    parser.add_argument(
        "--no-spar-hole",
        dest="spar_hole",
        action="store_false",
        help="Disable the spar hole.",
    )
    parser.set_defaults(spar_hole=True)
    parser.add_argument(
        "--define",
        action="append",
        default=[],
        type=_parse_define,
        metavar="NAME=VALUE",
        help="Additional OpenSCAD -D override. May be repeated.",
    )
    parser.add_argument(
        "--no-clean-stl",
        dest="clean_stl",
        action="store_false",
        help="Skip ASCII-to-binary STL cleanup before slicing.",
    )
    parser.set_defaults(clean_stl=True)
    parser.add_argument(
        "--viewer-exe",
        help="Path to prusa-gcodeviewer.exe. Defaults to the PrusaSlicer install beside prusa-slicer-console.exe.",
    )
    parser.add_argument(
        "--open-viewer",
        dest="open_viewer",
        action="store_true",
        help="Open Prusa G-code Viewer after slicing. This is the default.",
    )
    parser.add_argument(
        "--no-open-viewer",
        dest="open_viewer",
        action="store_false",
        help="Do not launch Prusa G-code Viewer.",
    )
    parser.set_defaults(open_viewer=True)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    repo_root = _repo_root()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    base_config = _load_json(config_path)
    config, output_dir, name = _make_config(args, repo_root, base_config)
    output_dir_abs = repo_path(repo_root, str(output_dir))
    output_dir_abs.mkdir(parents=True, exist_ok=True)

    print(f"Building {name}")
    print(f"Output directory: {output_dir_abs}")

    build = build_scad(config, repo_root)
    if build.get("status") != "pass":
        print(f"OpenSCAD failed: {build.get('error')}", file=sys.stderr)
        return 1
    print(f"STL created: {config['output_stl']}")

    stl_clean: dict[str, Any]
    if args.clean_stl:
        stl_clean = clean_stl(repo_path(repo_root, config["output_stl"]))
        if stl_clean.get("status") == "fail":
            print(f"STL cleanup failed: {stl_clean.get('error')}", file=sys.stderr)
            return 1
        print(f"STL cleanup: {stl_clean.get('status')}")
    else:
        stl_clean = {"status": "skipped", "reason": "--no-clean-stl was supplied"}

    slicer = slice_prusa(config, repo_root)
    if slicer.get("status") != "pass":
        print(f"PrusaSlicer failed: {slicer.get('error')}", file=sys.stderr)
        return 1
    print(f"G-code created: {config['output_gcode']}")

    viewer = _open_viewer(args, config, repo_root)
    if viewer.get("status") == "pass":
        print(f"Opened Prusa G-code Viewer: {viewer['gcode']}")
    elif args.open_viewer:
        print(f"Viewer launch skipped: {viewer.get('reason')}")

    summary = {
        "status": "pass",
        "name": name,
        "config": str(config_path),
        "output_dir": str(output_dir_abs),
        "stl": str(repo_path(repo_root, config["output_stl"])),
        "gcode": str(repo_path(repo_root, config["output_gcode"])),
        "build": build,
        "stl_clean": stl_clean,
        "slicer": slicer,
        "viewer": viewer,
    }
    summary_path = output_dir_abs / "pipeline-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
