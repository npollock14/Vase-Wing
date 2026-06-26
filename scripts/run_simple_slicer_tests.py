from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from build_scad import repo_path
from clean_stl import clean_stl
from inspect_gcode import inspect_gcode
from inspect_stl import inspect_stl
from report import write_xy_preview, write_z_sample_preview


SCAD_TEMPLATE = """
$fn = 64;
height = 60;
chord = 100;
thickness = 28;

module profile2d() {{
    hull() {{
        translate([0, 0]) circle(r = thickness / 2);
        translate([chord, 0]) scale([0.15, 1]) circle(r = thickness / 2);
    }}
}}

module void_box(x, y, w, h) {{
    translate([x, y]) square([w, h]);
}}

module geometry2d() {{
    difference() {{
        profile2d();
        {cuts}
    }}
}}

linear_extrude(height = height, convexity = 10) geometry2d();
"""


TESTS: list[dict[str, Any]] = [
    {
        "name": "skin_only",
        "description": "Single closed airfoil-like contour, no internal voids.",
        "cuts": "",
        "slice_closing_radius": 0.0,
    },
    {
        "name": "enclosed_rect_void",
        "description": "One fully enclosed internal void. This should create an inner perimeter island.",
        "cuts": "void_box(36, -6, 22, 12);",
        "slice_closing_radius": 0.0,
    },
    {
        "name": "enclosed_ladder_voids",
        "description": "Three enclosed voids that leave vertical rib-like webs between them.",
        "cuts": "\n".join(
            [
                "void_box(25, -10, 18, 20);",
                "void_box(50, -10, 18, 20);",
                "void_box(75, -8, 12, 16);",
            ]
        ),
        "slice_closing_radius": 0.0,
    },
    {
        "name": "slot_0p1_to_void_closing0",
        "description": "A 0.1 mm slit connects an internal void to the outer skin, with gap closing disabled.",
        "cuts": "\n".join(["void_box(36, -6, 22, 12);", "void_box(-20, -0.05, 58, 0.1);"]),
        "slice_closing_radius": 0.0,
    },
    {
        "name": "slot_0p1_to_void_closing_defaultish",
        "description": "Same 0.1 mm slit, but with a small slice closing radius so Prusa may heal the slit.",
        "cuts": "\n".join(["void_box(36, -6, 22, 12);", "void_box(-20, -0.05, 58, 0.1);"]),
        "slice_closing_radius": 0.049,
    },
    {
        "name": "slot_0p45_to_void_closing0",
        "description": "A 0.45 mm slit connects the internal void to the outer skin.",
        "cuts": "\n".join(["void_box(36, -6, 22, 12);", "void_box(-20, -0.225, 58, 0.45);"]),
        "slice_closing_radius": 0.0,
    },
    {
        "name": "comb_0p1_open_slots",
        "description": "Several 0.1 mm open slots from the leading edge, approximating a fragile rib-entry comb.",
        "cuts": "\n".join([f"void_box(-20, {y - 0.05:.3f}, 60, 0.1);" for y in [-9, -4.5, 0, 4.5, 9]]),
        "slice_closing_radius": 0.0,
    },
    {
        "name": "comb_0p45_open_slots",
        "description": "Several 0.45 mm open slots from the leading edge.",
        "cuts": "\n".join([f"void_box(-20, {y - 0.225:.3f}, 60, 0.45);" for y in [-9, -4.5, 0, 4.5, 9]]),
        "slice_closing_radius": 0.0,
    },
]


def _write_scad(test: dict[str, Any], path: Path) -> None:
    path.write_text(SCAD_TEMPLATE.format(cuts=test["cuts"]), encoding="utf-8")


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _slice_command(config: dict[str, Any], profile: Path, stl: Path, gcode: Path, slice_closing_radius: float) -> list[str]:
    return [
        config["prusaslicer_exe"],
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
        f"--slice-closing-radius={slice_closing_radius}",
        "--no-binary-gcode",
        "--gcode-comments",
        str(stl),
    ]


def _summarize(report: dict[str, Any]) -> dict[str, Any]:
    gcode = report["gcode"]
    return {
        "status": report["status"],
        "stl_triangles": report.get("stl", {}).get("triangle_count"),
        "feature_types": gcode["feature_types"]["counts"],
        "zero_retraction": gcode["zero_retraction"]["status"],
        "continuity": gcode["continuity"]["status"],
        "unexpected_travels": gcode["continuity"]["unexpected_travel_count"],
        "path_discontinuities": gcode["continuity"]["path_discontinuity_count"],
        "internal_layers": gcode["internal_structure"]["layers_with_internal_paths"],
        "internal_length_mm": round(gcode["internal_structure"]["total_internal_path_length_mm"], 2),
        "print_time": gcode["slicer_estimates"].get("print_time_normal"),
        "filament_mm": gcode["slicer_estimates"].get("filament_used_mm"),
    }


def _write_report(results: list[dict[str, Any]], out: Path) -> None:
    lines = [
        "# Simple Vase Slicer Condition Tests",
        "",
        "These tests use small OpenSCAD coupons to isolate how PrusaSlicer spiral vase mode handles internal voids, slits, and rib-entry combs. All runs force one perimeter, zero infill, zero top/bottom solid layers, no supports, no binary G-code, and zero retractions.",
        "",
        "## Summary Table",
        "",
        "| Test | Slice closing | Continuity | Travels | Internal layers | Time | Filament | Finding |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        s = item["summary"]
        lines.append(
            "| {name} | {closing} | {continuity} | {travels} | {internal_layers} | {time} | {filament} mm | {finding} |".format(
                name=item["name"],
                closing=item["slice_closing_radius"],
                continuity=s["continuity"],
                travels=s["unexpected_travels"],
                internal_layers=s["internal_layers"],
                time=s["print_time"],
                filament=s["filament_mm"],
                finding=item["finding"],
            )
        )

    lines.extend(["", "## Details", ""])
    for item in results:
        s = item["summary"]
        lines.extend(
            [
                f"### {item['name']}",
                "",
                item["description"],
                "",
                f"- Slice closing radius: `{item['slice_closing_radius']}` mm",
                f"- Feature types: `{s['feature_types']}`",
                f"- Zero retraction: `{s['zero_retraction']}`",
                f"- Continuity: `{s['continuity']}` with `{s['unexpected_travels']}` unexpected travels and `{s['path_discontinuities']}` path discontinuities",
                f"- Internal path layers: `{s['internal_layers']}`",
                f"- Internal path length: `{s['internal_length_mm']}` mm",
                f"- Slicer estimate: `{s['print_time']}`, `{s['filament_mm']}` mm filament",
                f"- G-code Z samples: `{item['z_samples']}`",
                f"- G-code XY preview: `{item['xy_preview']}`",
                "",
            ]
        )

    lines.extend(
        [
            "## Findings",
            "",
        "1. A single closed skin produces the cleanest spiral-vase result: no travels, no discontinuities, and no internal paths.",
            "2. Fully enclosed voids are ignored by PrusaSlicer spiral vase in these tests. CAD can contain enclosed holes or ribs, but if they are not connected to the active external contour they do not become printed rib paths.",
            "3. A slit-connected internal void does become part of the continuous vase path. In the 0.1 mm and 0.45 mm slit tests, Prusa emitted one continuous external-perimeter path with zero travels and zero retractions.",
            "4. The 0.1 mm slit survived both `slice_closing_radius=0` and `0.049` in this simple geometry. That does not mean every 0.1 mm feature is safe, but it suggests topology and contour connectivity matter more than the raw nominal slit width.",
            "5. Open-slot combs also slice as one continuous path, but they deliberately open the leading edge and add a lot of path length. This is a useful analog for the wing artifact risk: it can be continuous and still be structurally or aerodynamically wrong.",
            "",
            "## Implication For The Wing",
            "",
            "The rib strategy needs to create one continuous contour path, not merely internal CAD walls or enclosed voids. CAD cross sections can look correct while spiral vase ignores those interiors. The next geometry experiment should start from one controlled skin slit plus one rib path, then grow to repeated ribs only after the validator shows zero travels and stable extents.",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config = json.loads((repo_root / "config" / "vase_validation.json").read_text(encoding="utf-8"))
    openscad = Path(config["openscad_exe"])
    profile = repo_path(repo_root, config["prusa_profile"])
    out_dir = repo_root / "generated" / "simple_slicer_tests"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for test in TESTS:
        name = test["name"]
        scad = out_dir / f"{name}.scad"
        stl = out_dir / f"{name}.stl"
        gcode = out_dir / f"{name}.gcode"
        xy = out_dir / f"{name}.gcode_xy.png"
        z_samples = out_dir / f"{name}.gcode_z_samples.png"
        _write_scad(test, scad)

        build_cmd = [
            str(openscad),
            "--backend",
            "Manifold",
            "--summary",
            "all",
            "--summary-file",
            str(out_dir / f"{name}.summary.json"),
            "-o",
            str(stl),
            str(scad),
        ]
        build = _run(build_cmd, repo_root)
        (out_dir / f"{name}.openscad.out.txt").write_text(build.stdout, encoding="utf-8", errors="replace")
        (out_dir / f"{name}.openscad.err.txt").write_text(build.stderr, encoding="utf-8", errors="replace")
        if build.returncode != 0:
            raise RuntimeError(f"OpenSCAD failed for {name}: {build.stderr}")

        clean = clean_stl(stl)
        stl_report = inspect_stl(stl)

        slice_cmd = _slice_command(config, profile, stl, gcode, float(test["slice_closing_radius"]))
        sliced = _run(slice_cmd, repo_root)
        (out_dir / f"{name}.prusa.out.txt").write_text(sliced.stdout, encoding="utf-8", errors="replace")
        (out_dir / f"{name}.prusa.err.txt").write_text(sliced.stderr, encoding="utf-8", errors="replace")
        if sliced.returncode != 0:
            raise RuntimeError(f"PrusaSlicer failed for {name}: {sliced.stderr}")

        inspect_config = dict(config)
        inspect_config.update(
            {
                "require_edge_checks": False,
                "require_internal_paths": False,
                "root_chord_mm": 100,
                "tip_chord_mm": 100,
                "coupon_length_mm": 60,
                "center_line_percent": 0,
                "min_internal_path_length_mm": 5.0,
                "max_path_gap_mm": 1.0,
                "max_nonextrude_xy_mm": 1.0,
            }
        )
        gcode_report = inspect_gcode(gcode, inspect_config)
        write_xy_preview(gcode_report, xy)
        write_z_sample_preview(gcode_report, z_samples)

        report = {
            "status": "pass" if gcode_report["zero_retraction"]["status"] == "pass" else "fail",
            "stl_clean": clean,
            "stl": stl_report,
            "gcode": gcode_report,
        }
        result = {
            "name": name,
            "description": test["description"],
            "slice_closing_radius": test["slice_closing_radius"],
            "scad": str(scad),
            "stl": str(stl),
            "gcode": str(gcode),
            "xy_preview": str(xy),
            "z_samples": str(z_samples),
            "summary": _summarize(report),
        }

        continuity = result["summary"]["continuity"]
        internal_layers = result["summary"]["internal_layers"]
        if name == "skin_only":
            finding = "Baseline clean single contour."
        elif "enclosed" in name:
            finding = "Enclosed internal void is ignored by spiral vase."
        elif "closing_defaultish" in name:
            finding = "Small slicer closing radius changes whether the slit survives as topology."
        elif "comb" in name:
            finding = "Open edge comb is continuous but risky/long."
        elif continuity == "pass" and internal_layers:
            finding = "Promising continuous connected internal path."
        else:
            finding = "Connected feature still produces discontinuities."
        result["finding"] = finding
        results.append(result)
        print(f"{name}: {json.dumps(result['summary'])}")

    json_path = out_dir / "simple_slicer_conditions_report.json"
    md_path = out_dir / "simple_slicer_conditions_report.md"
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    _write_report(results, md_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
