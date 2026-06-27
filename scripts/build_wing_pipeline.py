from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_scad import build_scad, repo_path
from clean_stl import clean_stl
from slice_prusa import slice_prusa
from test_gcode_x_extents import evaluate_extents, parse_layer_extents, write_plot

ESTIMATE_RE = re.compile(r"^;\s*([^=]+?)\s*=\s*(.+?)\s*$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def _tag_number(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def _lightening_pattern_value(pattern: str) -> int:
    return {"circle": 0, "arch-slot": 1}[pattern]


def _lightening_pattern_tag(pattern: str) -> str:
    return {"circle": "circ", "arch-slot": "arch"}[pattern]


def _parse_gcode_estimates(path: Path) -> dict[str, float | str]:
    estimates: dict[str, float | str] = {}
    if not path.exists():
        return estimates

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = ESTIMATE_RE.match(line.strip())
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key not in {
            "filament used [mm]",
            "filament used [cm3]",
            "total filament used [g]",
            "filament_density",
            "filament_type",
        }:
            continue
        out_key = (
            key.replace(" [", "_")
            .replace("]", "")
            .replace(" ", "_")
            .replace("/", "_")
            .replace("total_", "reported_total_")
        )
        try:
            estimates[out_key] = float(value)
        except ValueError:
            estimates[out_key] = value
    return estimates


def _estimate_weights(config: dict[str, Any], gcode: Path) -> dict[str, Any]:
    estimates = _parse_gcode_estimates(gcode)
    filament_cm3 = estimates.get("filament_used_cm3")
    standard_density = float(config.get("standard_pla_density_g_cm3", 1.24))
    lw_density = float(
        config.get(
            "lw_pla_density_g_cm3",
            standard_density * float(config.get("lw_pla_weight_factor", 0.4)),
        )
    )
    result: dict[str, Any] = {
        "gcode_estimates": estimates,
        "standard_pla_density_g_cm3": standard_density,
        "lw_pla_density_g_cm3": lw_density,
    }
    if isinstance(filament_cm3, float):
        result.update(
            {
                "filament_used_cm3": filament_cm3,
                "standard_pla_g": filament_cm3 * standard_density,
                "lw_pla_g": filament_cm3 * lw_density,
                "lw_pla_savings_percent": 100 * (1 - (lw_density / standard_density)),
            }
        )
    return result


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
    return str(config["prusa_profile"])


def _run_x_extent_test(
    args: argparse.Namespace, config: dict[str, Any], repo_root: Path, output_dir: Path
) -> dict[str, Any]:
    if not args.x_extent_test:
        return {"status": "skipped", "reason": "--no-x-extent-test was supplied"}

    gcode = repo_path(repo_root, config["output_gcode"])
    rows = parse_layer_extents(gcode)
    report = evaluate_extents(
        rows,
        max_jump_mm=args.max_x_extent_jump_mm,
        max_local_residual_mm=args.max_x_extent_local_residual_mm,
        window_layers=args.x_extent_window_layers,
        ignore_first_layers=args.x_extent_ignore_first_layers,
        ignore_last_layers=args.x_extent_ignore_last_layers,
    )
    report["gcode"] = str(gcode)
    json_path = output_dir / "x_extent_artifact_test.json"
    plot_path = output_dir / "x_extent_artifact_test.png"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_plot(rows, report, plot_path)
    report["json"] = str(json_path)
    report["plot"] = str(plot_path)
    return report


def _default_name(args: argparse.Namespace) -> str:
    pattern_tag = f"p{_lightening_pattern_tag(args.lightening_pattern)}"
    if args.lightening_pattern == "arch-slot":
        if args.arch_slot_count > 0:
            pattern_tag = "_".join(
                [
                    pattern_tag,
                    f"ac{args.arch_slot_count}",
                    f"ag{_tag_number(args.arch_slot_gap_mm)}",
                    f"clr{_tag_number(args.arch_slot_skin_clearance_mm)}",
                    f"ah{_tag_number(args.arch_slot_height_fraction)}",
                    f"amin{_tag_number(args.arch_slot_min_height_mm)}",
                ]
            )
        else:
            pattern_tag = "_".join(
                [
                    pattern_tag,
                    f"aw{_tag_number(args.arch_slot_width_mm)}",
                    f"ah{_tag_number(args.arch_slot_height_fraction)}",
                    f"amin{_tag_number(args.arch_slot_min_height_mm)}",
                ]
            )
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
            pattern_tag,
            "ssOff"
            if not args.spar_support_stations
            else f"ss{_tag_number(args.spar_support_station_spacing_mm)}x{_tag_number(args.spar_support_station_width_mm)}",
        ]
    )


def _make_config(
    args: argparse.Namespace, repo_root: Path, base_config: dict[str, Any]
) -> tuple[dict[str, Any], Path, str]:
    name = args.name or _default_name(args)
    artifact_stem = name if args.name else "wing"
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
        "mode3_lightening_pattern": _lightening_pattern_value(args.lightening_pattern),
        "mode3_arch_slot_width_mm": args.arch_slot_width_mm,
        "mode3_arch_slot_height_fraction": args.arch_slot_height_fraction,
        "mode3_arch_slot_min_height_mm": args.arch_slot_min_height_mm,
        "mode3_arch_slot_count": args.arch_slot_count,
        "mode3_arch_slot_gap_mm": args.arch_slot_gap_mm,
        "mode3_arch_slot_skin_clearance_mm": args.arch_slot_skin_clearance_mm,
        "mode3_arch_slot_contour_samples": args.arch_slot_contour_samples,
        "mode3_spar_support_stations_enabled": args.spar_support_stations,
        "mode3_spar_support_station_spacing_mm": args.spar_support_station_spacing_mm,
        "mode3_spar_support_station_width_mm": args.spar_support_station_width_mm,
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
            "output_stl": str(output_dir / f"{artifact_stem}.stl"),
            "output_gcode": str(output_dir / f"{artifact_stem}.gcode"),
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
        help="PrusaSlicer profile path. Defaults to the profile in the base JSON config.",
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
        "--lightening-pattern",
        choices=["circle", "arch-slot"],
        default="arch-slot",
        help="Mode 3 lightening cutter pattern. 'circle' keeps the previous disk cutters; 'arch-slot' uses rounded slots.",
    )
    parser.add_argument("--arch-slot-width-mm", type=float, default=6)
    parser.add_argument("--arch-slot-height-fraction", type=float, default=0.85)
    parser.add_argument("--arch-slot-min-height-mm", type=float, default=5)
    parser.add_argument("--arch-slot-count", type=int, default=6)
    parser.add_argument("--arch-slot-gap-mm", type=float, default=2)
    parser.add_argument("--arch-slot-skin-clearance-mm", type=float, default=2)
    parser.add_argument("--arch-slot-contour-samples", type=int, default=10)
    parser.add_argument(
        "--spar-support-stations",
        dest="spar_support_stations",
        action="store_true",
        help="Leave periodic support station bands through the mode 3 spar no-go moat. This is the default.",
    )
    parser.add_argument(
        "--no-spar-support-stations",
        dest="spar_support_stations",
        action="store_false",
        help="Use a continuous spar no-go moat with no support station bands.",
    )
    parser.set_defaults(spar_support_stations=True)
    parser.add_argument("--spar-support-station-spacing-mm", type=float, default=125)
    parser.add_argument("--spar-support-station-width-mm", type=float, default=12)
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
        "--x-extent-test",
        dest="x_extent_test",
        action="store_true",
        help="Run the fast actual xmin/xmax artifact test after slicing. This is the default.",
    )
    parser.add_argument(
        "--no-x-extent-test",
        dest="x_extent_test",
        action="store_false",
        help="Skip the fast actual xmin/xmax artifact test.",
    )
    parser.set_defaults(x_extent_test=True)
    parser.add_argument("--max-x-extent-jump-mm", type=float, default=2.0)
    parser.add_argument("--max-x-extent-local-residual-mm", type=float, default=2.0)
    parser.add_argument("--x-extent-window-layers", type=int, default=9)
    parser.add_argument("--x-extent-ignore-first-layers", type=int, default=8)
    parser.add_argument("--x-extent-ignore-last-layers", type=int, default=0)
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

    weight_estimate = _estimate_weights(config, repo_path(repo_root, config["output_gcode"]))
    if "lw_pla_g" in weight_estimate:
        print(
            "Estimated weight: "
            f"{weight_estimate['lw_pla_g']:.1f} g LW-PLA "
            f"({weight_estimate['standard_pla_g']:.1f} g standard PLA equivalent)"
        )

    x_extent_test = _run_x_extent_test(args, config, repo_root, output_dir_abs)
    if x_extent_test.get("status") == "pass":
        worst = x_extent_test.get("worst_jumps", [{}])[0]
        worst_jump = worst.get("jump_mm", 0.0)
        print(f"X extent artifact test: pass (worst jump {worst_jump:.3f} mm)")
    elif x_extent_test.get("status") == "skipped":
        print(f"X extent artifact test skipped: {x_extent_test.get('reason')}")
    else:
        print(
            "X extent artifact test failed: "
            f"{x_extent_test.get('failure_count')} failures; plot {x_extent_test.get('plot')}",
            file=sys.stderr,
        )
        summary = {
            "status": "fail",
            "name": name,
            "config": str(config_path),
            "output_dir": str(output_dir_abs),
            "stl": str(repo_path(repo_root, config["output_stl"])),
            "gcode": str(repo_path(repo_root, config["output_gcode"])),
            "build": build,
            "stl_clean": stl_clean,
            "slicer": slicer,
            "x_extent_test": x_extent_test,
            "weight_estimate": weight_estimate,
            "viewer": {"status": "skipped", "reason": "x extent artifact test failed"},
        }
        summary_path = output_dir_abs / "pipeline-summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Summary: {summary_path}")
        return 1

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
        "x_extent_test": x_extent_test,
        "weight_estimate": weight_estimate,
        "viewer": viewer,
    }
    summary_path = output_dir_abs / "pipeline-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
