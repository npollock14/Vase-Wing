from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from build_scad import repo_path


def _status_icon(status: str | None) -> str:
    return "PASS" if status == "pass" else "SKIP" if status == "skipped" else "FAIL"


def _json_safe_report(report: dict[str, Any]) -> dict[str, Any]:
    cleaned = copy.deepcopy(report)
    gcode = cleaned.get("gcode")
    if isinstance(gcode, dict):
        gcode.pop("plot_segments", None)
    return cleaned


def write_json_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe_report(report), indent=2), encoding="utf-8")


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    build = report.get("build", {})
    clean = report.get("stl_clean", {})
    stl = report.get("stl", {})
    slicer = report.get("slicer", {})
    gcode = report.get("gcode", {})
    zero = gcode.get("zero_retraction", {})
    continuity = gcode.get("continuity", {})
    vase_profile = gcode.get("vase_profile", {})
    feature_types = gcode.get("feature_types", {})
    internal_structure = gcode.get("internal_structure", {})
    edge = gcode.get("edge_coverage", {})
    fusion = gcode.get("fusion_gaps", {})
    estimates = gcode.get("slicer_estimates", {})

    lines = [
        "# Vase Validation Report",
        "",
        f"Overall: **{_status_icon(report.get('status'))}**",
        "",
        "## Stages",
        "",
        f"- OpenSCAD build: **{_status_icon(build.get('status'))}**",
        f"- STL cleanup: **{_status_icon(clean.get('status'))}**",
        f"- STL inspection: **{_status_icon(stl.get('status'))}**",
        f"- PrusaSlicer: **{_status_icon(slicer.get('status'))}**",
        f"- Vase profile settings: **{_status_icon(vase_profile.get('status'))}**",
        f"- Slicer feature types: **{_status_icon(feature_types.get('status'))}**",
        f"- Internal rib/path detection: **{_status_icon(internal_structure.get('status'))}**",
        f"- Zero retraction: **{_status_icon(zero.get('status'))}**",
        f"- Path continuity: **{_status_icon(continuity.get('status'))}**",
        f"- Edge extent: **{_status_icon(edge.get('status'))}**",
        f"- Fusion gaps: **{_status_icon(fusion.get('status'))}**",
        "",
        "## Outputs",
        "",
        f"- STL: `{build.get('output_stl', '')}`",
        f"- G-code: `{slicer.get('output_gcode', '')}`",
        f"- Extent plot: `{report.get('extent_plot', '')}`",
        f"- XY preview: `{report.get('extrusion_xy_preview', '')}`",
        f"- Z sample preview: `{report.get('extrusion_z_samples', '')}`",
        "",
        "## G-code Summary",
        "",
        f"- G10 retracts: `{zero.get('g10_count', 0)}`",
        f"- G11 unretracts: `{zero.get('g11_count', 0)}`",
        f"- Negative extrusion moves: `{len(zero.get('negative_e_moves', []))}`",
        f"- Absolute E decreases: `{len(zero.get('absolute_e_decreases', []))}`",
        f"- Unexpected travel moves: `{continuity.get('unexpected_travel_count', 0)}`",
        f"- Path discontinuities: `{continuity.get('path_discontinuity_count', 0)}`",
        f"- Feature types: `{feature_types.get('counts', {})}`",
        f"- Layers with internal paths: `{internal_structure.get('layers_with_internal_paths', 0)}`",
        f"- Edge failure layers: `{edge.get('failure_count', 0)}`",
        "",
        "## Internal Structure",
        "",
        f"- Required: `{internal_structure.get('required', False)}`",
        f"- Layers with detected internal paths: `{internal_structure.get('layers_with_internal_paths', 0)}`",
        f"- Required layers: `{internal_structure.get('min_required_layers', 0)}`",
        f"- Total detected internal path length: `{internal_structure.get('total_internal_path_length_mm', 0.0):.3f}` mm",
        f"- Note: `{internal_structure.get('reason') or 'Internal path-like extrusion detected.'}`",
        "",
        "## STL Cleanup",
        "",
        f"- Degenerate triangles removed: `{clean.get('degenerate_triangles_removed', 0)}`",
        f"- Triangles out: `{clean.get('triangles_out', 'unknown')}`",
        f"- Cleaned STL bytes: `{clean.get('cleaned_bytes', 'unknown')}`",
        "",
        "## Slicer Estimates",
        "",
        f"- Filament used: `{estimates.get('filament_used_mm', 'unknown')}` mm",
        f"- Filament volume: `{estimates.get('filament_used_cm3', 'unknown')}` cm3",
        f"- Filament mass: `{estimates.get('filament_used_g', 'unknown')}` g",
        f"- Print time, normal mode: `{estimates.get('print_time_normal', 'unknown')}`",
        f"- Print time, silent mode: `{estimates.get('print_time_silent', 'unknown')}`",
        f"- First layer time, normal mode: `{estimates.get('first_layer_time_normal', 'unknown')}`",
        "",
    ]

    failures = edge.get("failures", [])
    if failures:
        lines.extend(["## Worst Edge Failures", ""])
        for item in failures[:15]:
            lines.append(
                "- Layer {layer} Z={z:.3f}: {reasons} "
                "actual=[{amin:.3f}, {amax:.3f}] expected=[{emin:.3f}, {emax:.3f}]".format(
                    layer=item.get("layer"),
                    z=float(item.get("z", 0.0)),
                    reasons=", ".join(item.get("reasons", [])),
                    amin=float(item.get("actual_min_x", 0.0)),
                    amax=float(item.get("actual_max_x", 0.0)),
                    emin=float(item.get("expected_min_x", 0.0)),
                    emax=float(item.get("expected_max_x", 0.0)),
                )
            )
        lines.append("")

    if report.get("status") != "pass":
        lines.extend(
            [
                "## Suggested Next Action",
                "",
                "Open `extent_plot.png` first. Spikes in `actual_min_x` usually mean a leading-edge artifact; "
                "spikes in `actual_max_x` usually mean a trailing-edge artifact. If zero-retraction failed, "
                "fix the Prusa profile before interpreting geometry issues.",
                "",
            ]
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def write_extent_plot(gcode: dict[str, Any], path: Path) -> None:
    rows = gcode.get("layer_summaries", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No extrusion layers found", ha="center", va="center")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return

    z = [r["z"] for r in rows]
    actual_min = [r["actual_min_x"] for r in rows]
    actual_max = [r["actual_max_x"] for r in rows]
    expected_min = [r["expected_min_x"] for r in rows]
    expected_max = [r["expected_max_x"] for r in rows]
    bad = [r for r in rows if r.get("failure_reasons")]

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(z, actual_min, label="actual min X", color="#2563eb", linewidth=1.2)
    ax.plot(z, actual_max, label="actual max X", color="#dc2626", linewidth=1.2)
    ax.plot(z, expected_min, label="expected min X", color="#93c5fd", linestyle="--", linewidth=1.0)
    ax.plot(z, expected_max, label="expected max X", color="#fca5a5", linestyle="--", linewidth=1.0)
    if bad:
        ax.scatter([r["z"] for r in bad], [r["actual_min_x"] for r in bad], color="black", s=12, label="flagged layer")
        ax.scatter([r["z"] for r in bad], [r["actual_max_x"] for r in bad], color="black", s=12)
    ax.set_title("Printed X Extents Over Z")
    ax.set_xlabel("Z / span height (mm)")
    ax.set_ylabel("G-code X (mm)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def write_xy_preview(gcode: dict[str, Any], path: Path) -> None:
    segments = gcode.get("plot_segments", [])
    bad_layers = {item["layer"] for item in gcode.get("edge_coverage", {}).get("failures", [])}
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    if not segments:
        ax.text(0.5, 0.5, "No extrusion segments found", ha="center", va="center")
    else:
        for seg in segments:
            color = "#dc2626" if seg["layer"] in bad_layers else "#f97316"
            alpha = 0.9 if seg["layer"] in bad_layers else 0.18
            lw = 0.8 if seg["layer"] in bad_layers else 0.25
            ax.plot([seg["x0"], seg["x1"]], [seg["y0"], seg["y1"]], color=color, alpha=alpha, linewidth=lw)
    ax.set_title("Top-Down Extrusion Preview")
    ax.set_xlabel("G-code X (mm)")
    ax.set_ylabel("G-code Y (mm)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.2)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_z_sample_preview(gcode: dict[str, Any], path: Path) -> None:
    rows = gcode.get("layer_summaries", [])
    segments = gcode.get("plot_segments", [])
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharex=True, sharey=True)
    if not rows or not segments:
        for ax in axes:
            ax.text(0.5, 0.5, "No extrusion layers found", ha="center", va="center")
            ax.set_axis_off()
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        return

    sample_indices = [0, len(rows) // 2, len(rows) - 1]
    sample_rows = [rows[i] for i in sample_indices]
    segment_by_layer: dict[int, list[dict[str, float | int]]] = {}
    for seg in segments:
        segment_by_layer.setdefault(int(seg["layer"]), []).append(seg)

    for ax, row, label in zip(axes, sample_rows, ["Bottom", "Middle", "Top"]):
        layer = int(row["layer"])
        local_segments = segment_by_layer.get(layer, [])
        if not local_segments:
            ax.text(0.5, 0.5, f"No layer {layer} segments", ha="center", va="center")
        else:
            for seg in local_segments:
                ax.plot([seg["x0"], seg["x1"]], [seg["y0"], seg["y1"]], color="#f97316", alpha=0.85, linewidth=0.65)
        ax.set_title(f"{label}: layer {layer}, Z={float(row['z']):.2f} mm")
        ax.set_xlabel("G-code X (mm)")
        ax.grid(True, alpha=0.2)
        ax.set_aspect("equal", adjustable="box")
    axes[0].set_ylabel("G-code Y (mm)")
    fig.suptitle("Extrusion Samples by Z")
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_reports(report: dict[str, Any], config: dict[str, Any], repo_root: Path) -> None:
    json_path = repo_path(repo_root, config["report_json"])
    md_path = repo_path(repo_root, config["report_md"])
    extent_path = repo_path(repo_root, config["extent_plot"])
    xy_path = repo_path(repo_root, config["extrusion_xy_preview"])
    z_samples_path = repo_path(repo_root, config["extrusion_z_samples"])
    report["report_json"] = str(json_path)
    report["report_md"] = str(md_path)
    report["extent_plot"] = str(extent_path)
    report["extrusion_xy_preview"] = str(xy_path)
    report["extrusion_z_samples"] = str(z_samples_path)
    if "gcode" in report:
        write_extent_plot(report["gcode"], extent_path)
        write_xy_preview(report["gcode"], xy_path)
        write_z_sample_preview(report["gcode"], z_samples_path)
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)
