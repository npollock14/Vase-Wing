from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


MOVE_RE = re.compile(r"([A-Za-z])([-+]?\d*\.?\d+)")
ESTIMATE_RE = re.compile(r"^;\s*([^=]+?)\s*=\s*(.+?)\s*$")
CONFIG_RE = re.compile(r"^;\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")


@dataclass
class LayerBin:
    index: int
    z: float
    points: list[tuple[float, float]] = field(default_factory=list)
    segments: list[tuple[float, float, float, float]] = field(default_factory=list)


def _tokens(code: str) -> dict[str, float | str]:
    values: dict[str, float | str] = {}
    for key, value in MOVE_RE.findall(code):
        key = key.upper()
        if key in {"G", "M"}:
            values[key] = f"{key}{int(float(value))}"
        else:
            values[key] = float(value)
    return values


def _xy_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _expected_bounds(config: dict[str, Any], z: float, x_offset: float) -> tuple[float, float, float]:
    root = float(config["root_chord_mm"])
    tip = float(config["tip_chord_mm"])
    length = max(float(config["coupon_length_mm"]), 1e-9)
    frac = min(max(z / length, 0.0), 1.0)
    chord = root - (root - tip) * frac
    center = float(config.get("center_line_percent", 0.0)) / 100.0
    model_min = root * center - chord * center
    return x_offset + model_min, x_offset + model_min + chord, chord


def _detect_internal_paths(bins: list[LayerBin], config: dict[str, Any]) -> dict[str, Any]:
    margin = float(config.get("internal_path_margin_mm", 1.0))
    x_bin_mm = max(float(config.get("internal_path_x_bin_mm", 2.0)), 0.1)
    edge_keepout = float(config.get("internal_path_edge_keepout_mm", 8.0))
    min_layers = int(config.get("min_internal_path_layers", 3))
    min_length = float(config.get("min_internal_path_length_mm", 10.0))
    require = bool(config.get("require_internal_paths", False))

    layer_hits: list[dict[str, Any]] = []
    total_internal_length = 0.0

    for b in bins:
        if not b.points or not b.segments:
            continue
        xs = [p[0] for p in b.points]
        layer_min_x = min(xs)
        layer_max_x = max(xs)
        envelopes: dict[int, list[float]] = {}
        for px, py in b.points:
            idx = int(math.floor(px / x_bin_mm))
            if idx not in envelopes:
                envelopes[idx] = [py, py]
            else:
                envelopes[idx][0] = min(envelopes[idx][0], py)
                envelopes[idx][1] = max(envelopes[idx][1], py)

        internal_length = 0.0
        for x0, y0, x1, y1 in b.segments:
            mx = (x0 + x1) / 2
            my = (y0 + y1) / 2
            if mx < layer_min_x + edge_keepout or mx > layer_max_x - edge_keepout:
                continue
            idx = int(math.floor(mx / x_bin_mm))
            if idx not in envelopes:
                continue
            min_y, max_y = envelopes[idx]
            if max_y - min_y < margin * 2:
                continue
            if min_y + margin < my < max_y - margin:
                internal_length += math.hypot(x1 - x0, y1 - y0)

        if internal_length >= min_length:
            layer_hits.append({"layer": b.index, "z": b.z, "internal_path_length_mm": internal_length})
            total_internal_length += internal_length

    passes = len(layer_hits) >= min_layers
    status = "pass" if passes else ("fail" if require else "skipped")
    return {
        "status": status,
        "required": require,
        "layers_with_internal_paths": len(layer_hits),
        "min_required_layers": min_layers,
        "min_internal_path_length_mm": min_length,
        "total_internal_path_length_mm": total_internal_length,
        "sample_layers": layer_hits[:25],
        "reason": None
        if passes
        else "No sustained rib/path-like extrusion was detected; small spar-slot paths alone should not satisfy this check",
    }


def _parse_estimates(text: str) -> dict[str, Any]:
    estimate_keys = {
        "filament used [mm]": ("filament_used_mm", float),
        "filament used [cm3]": ("filament_used_cm3", float),
        "total filament used [g]": ("filament_used_g", float),
        "total filament cost": ("filament_cost", float),
        "estimated printing time (normal mode)": ("print_time_normal", str),
        "estimated printing time (silent mode)": ("print_time_silent", str),
        "estimated first layer printing time (normal mode)": ("first_layer_time_normal", str),
        "estimated first layer printing time (silent mode)": ("first_layer_time_silent", str),
    }
    estimates: dict[str, Any] = {}
    for line in text.splitlines():
        match = ESTIMATE_RE.match(line.strip())
        if not match:
            continue
        raw_key, raw_value = match.group(1).strip(), match.group(2).strip()
        if raw_key not in estimate_keys:
            continue
        out_key, parser = estimate_keys[raw_key]
        try:
            estimates[out_key] = parser(raw_value)
        except ValueError:
            estimates[out_key] = raw_value
    return estimates


def _parse_slicer_config(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = CONFIG_RE.match(line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _profile_checks(text: str) -> dict[str, Any]:
    cfg = _parse_slicer_config(text)
    checks = {
        "spiral_vase": cfg.get("spiral_vase") == "1",
        "perimeters": cfg.get("perimeters") == "1",
        "fill_density": cfg.get("fill_density") in {"0%", "0"},
        "top_solid_layers": cfg.get("top_solid_layers") == "0",
        "bottom_solid_layers": cfg.get("bottom_solid_layers") == "0",
        "support_material": cfg.get("support_material") == "0",
        "retract_length": cfg.get("retract_length") in {"0", "0.0"},
        "filament_retract_length": cfg.get("filament_retract_length") in {"0", "0.0"},
        "retract_lift": cfg.get("retract_lift") in {"0", "0.0"},
        "slice_closing_radius": cfg.get("slice_closing_radius") in {"0", "0.0"},
        "binary_gcode": cfg.get("binary_gcode") in {None, "0"},
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "settings": {key: cfg.get(key) for key in checks},
    }


def inspect_gcode(path: Path, config: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "stage": "gcode",
        "status": "fail",
        "path": str(path),
        "zero_retraction": {},
        "continuity": {},
        "edge_coverage": {},
        "fusion_gaps": {"status": "skipped", "reason": "No intentional fusion regions configured"},
    }
    if not path.exists():
        result["error"] = "G-code does not exist"
        return result

    raw = path.read_bytes()
    if b"\x00" in raw[:1024]:
        result["error"] = "G-code appears to be binary"
        return result
    text = raw.decode("utf-8", errors="replace")
    slicer_estimates = _parse_estimates(text)
    feature_type_counts = Counter(re.findall(r";TYPE:([^\r\n]+)", text))
    disallowed_feature_types = {
        "Solid infill",
        "Top solid infill",
        "Internal infill",
        "Bridge infill",
        "Support material",
    }
    disallowed_features = {
        name: count for name, count in feature_type_counts.items() if name.strip() in disallowed_feature_types
    }
    profile = _profile_checks(text)

    absolute_e = True
    x = y = z = e = None
    layer_index = -1
    current_bin: LayerBin | None = None
    bins: list[LayerBin] = []
    last_extruding_end: tuple[float, float] | None = None

    g10_count = 0
    g11_count = 0
    negative_e_moves: list[dict[str, Any]] = []
    absolute_e_decreases: list[dict[str, Any]] = []
    unexpected_travels: list[dict[str, Any]] = []
    path_discontinuities: list[dict[str, Any]] = []
    extrusion_segments: list[dict[str, float | int]] = []

    max_nonextrude_xy = float(config.get("max_nonextrude_xy_mm", 1.0))
    max_path_gap = float(config.get("max_path_gap_mm", 1.0))
    layer_height = float(config.get("layer_height_mm", 0.25))

    def ensure_bin(z_value: float | None) -> LayerBin:
        nonlocal current_bin, layer_index
        z_for_bin = 0.0 if z_value is None else z_value
        if current_bin is None:
            layer_index = max(layer_index, 0)
            current_bin = LayerBin(layer_index, z_for_bin)
            bins.append(current_bin)
        return current_bin

    for line_no, line in enumerate(text.splitlines(), start=1):
        comment = ""
        code = line
        if ";" in line:
            code, comment = line.split(";", 1)
            comment = comment.strip()

        if comment.startswith("LAYER_CHANGE"):
            layer_index += 1
            current_bin = LayerBin(layer_index, 0.0 if z is None else z)
            bins.append(current_bin)
        elif comment.startswith("Z:"):
            try:
                z = float(comment[2:])
                ensure_bin(z).z = z
            except ValueError:
                pass

        values = _tokens(code)
        op = values.get("G") or values.get("M")
        if op == "M82":
            absolute_e = True
            continue
        if op == "M83":
            absolute_e = False
            continue
        if op == "G10":
            g10_count += 1
            continue
        if op == "G11":
            g11_count += 1
            continue
        if op == "G92":
            if "E" in values:
                e = float(values["E"])
            continue
        if op not in {"G0", "G1"}:
            continue

        old_x, old_y, old_z, old_e = x, y, z, e
        new_x = float(values["X"]) if "X" in values else x
        new_y = float(values["Y"]) if "Y" in values else y
        new_z = float(values["Z"]) if "Z" in values else z
        e_delta = 0.0
        if "E" in values:
            new_e = float(values["E"])
            if absolute_e:
                if e is not None and new_e < e - 1e-7:
                    absolute_e_decreases.append({"line": line_no, "from": e, "to": new_e})
                e_delta = 0.0 if e is None else new_e - e
                e = new_e
            else:
                e_delta = new_e
                e = (0.0 if e is None else e) + new_e
            if e_delta < -1e-7:
                negative_e_moves.append({"line": line_no, "delta_e": e_delta})

        xy_changed = (
            old_x is not None
            and old_y is not None
            and new_x is not None
            and new_y is not None
            and _xy_dist((old_x, old_y), (new_x, new_y)) > 1e-7
        )

        if e_delta > 1e-7 and old_x is not None and old_y is not None and new_x is not None and new_y is not None:
            b = ensure_bin(new_z)
            b.z = 0.0 if new_z is None else new_z
            start = (old_x, old_y)
            end = (new_x, new_y)
            if last_extruding_end is not None:
                gap = _xy_dist(start, last_extruding_end)
                if gap > max_path_gap:
                    path_discontinuities.append(
                        {"line": line_no, "layer": b.index, "z": b.z, "gap_mm": gap, "x": start[0], "y": start[1]}
                    )
            b.points.extend([start, end])
            b.segments.append((start[0], start[1], end[0], end[1]))
            extrusion_segments.append({"layer": b.index, "z": b.z, "x0": start[0], "y0": start[1], "x1": end[0], "y1": end[1]})
            last_extruding_end = end
        elif xy_changed and last_extruding_end is not None and old_x is not None and old_y is not None and new_x is not None and new_y is not None:
            dist = _xy_dist((old_x, old_y), (new_x, new_y))
            if dist > max_nonextrude_xy:
                unexpected_travels.append({"line": line_no, "z": 0.0 if new_z is None else new_z, "distance_mm": dist})

        x, y, z = new_x, new_y, new_z

    layer_summaries: list[dict[str, Any]] = []
    for b in bins:
        if not b.points:
            continue
        xs = [p[0] for p in b.points]
        actual_min = min(xs)
        actual_max = max(xs)
        layer_summaries.append(
            {
                "layer": b.index,
                "z": b.z,
                "actual_min_x": actual_min,
                "actual_max_x": actual_max,
                "actual_chord": actual_max - actual_min,
            }
        )

    x_offset = 0.0
    if layer_summaries:
        n = max(1, min(int(config.get("offset_calibration_layers", 8)), len(layer_summaries)))
        offsets = []
        for row in layer_summaries[:n]:
            expected_min, _, _ = _expected_bounds(config, row["z"], 0.0)
            offsets.append(row["actual_min_x"] - expected_min)
        x_offset = median(offsets)

    max_extent_error = float(config.get("max_extent_error_mm", 1.0))
    max_jump = float(config.get("max_layer_extent_jump_mm", 1.0))
    extent_failures: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for row in layer_summaries:
        expected_min, expected_max, expected_chord = _expected_bounds(config, row["z"], x_offset)
        row["expected_min_x"] = expected_min
        row["expected_max_x"] = expected_max
        row["expected_chord"] = expected_chord
        row["leading_edge_error_mm"] = row["actual_min_x"] - expected_min
        row["trailing_edge_error_mm"] = expected_max - row["actual_max_x"]
        row["chord_shortfall_mm"] = expected_chord - row["actual_chord"]
        row["failure_reasons"] = []
        if abs(row["leading_edge_error_mm"]) > max_extent_error:
            row["failure_reasons"].append("leading_edge_extent")
        if abs(row["trailing_edge_error_mm"]) > max_extent_error:
            row["failure_reasons"].append("trailing_edge_extent")
        if row["chord_shortfall_mm"] > max_extent_error:
            row["failure_reasons"].append("chord_shortfall")
        if previous is not None:
            min_jump = abs(row["leading_edge_error_mm"] - previous["leading_edge_error_mm"])
            max_jump_value = abs(row["trailing_edge_error_mm"] - previous["trailing_edge_error_mm"])
            chord_jump = abs(row["chord_shortfall_mm"] - previous["chord_shortfall_mm"])
            row["leading_edge_jump_mm"] = min_jump
            row["trailing_edge_jump_mm"] = max_jump_value
            row["chord_error_jump_mm"] = chord_jump
            if min_jump > max_jump:
                row["failure_reasons"].append("leading_edge_jump")
            if max_jump_value > max_jump:
                row["failure_reasons"].append("trailing_edge_jump")
            if chord_jump > max_jump:
                row["failure_reasons"].append("chord_error_jump")
        if row["failure_reasons"]:
            extent_failures.append(
                {
                    "layer": row["layer"],
                    "z": row["z"],
                    "reasons": row["failure_reasons"],
                    "actual_min_x": row["actual_min_x"],
                    "actual_max_x": row["actual_max_x"],
                    "expected_min_x": row["expected_min_x"],
                    "expected_max_x": row["expected_max_x"],
                }
            )
        previous = row

    zero_pass = not (g10_count or g11_count or negative_e_moves or absolute_e_decreases)
    continuity_pass = not (unexpected_travels or path_discontinuities)
    edge_status = "skipped"
    if config.get("require_edge_checks", True):
        edge_status = "pass" if layer_summaries and not extent_failures else "fail"

    feature_pass = not disallowed_features
    profile_pass = profile["status"] == "pass"
    internal_structure = _detect_internal_paths(bins, config)
    internal_pass = internal_structure["status"] in {"pass", "skipped"}
    result["status"] = (
        "pass"
        if zero_pass and continuity_pass and feature_pass and profile_pass and internal_pass and edge_status in {"pass", "skipped"}
        else "fail"
    )
    result["zero_retraction"] = {
        "status": "pass" if zero_pass else "fail",
        "g10_count": g10_count,
        "g11_count": g11_count,
        "negative_e_moves": negative_e_moves[:50],
        "absolute_e_decreases": absolute_e_decreases[:50],
    }
    result["continuity"] = {
        "status": "pass" if continuity_pass else "fail",
        "unexpected_travel_count": len(unexpected_travels),
        "path_discontinuity_count": len(path_discontinuities),
        "unexpected_travel_moves": unexpected_travels[:50],
        "path_discontinuities": path_discontinuities[:50],
    }
    result["vase_profile"] = profile
    result["feature_types"] = {
        "status": "pass" if feature_pass else "fail",
        "counts": dict(feature_type_counts),
        "disallowed": disallowed_features,
    }
    result["internal_structure"] = internal_structure
    result["edge_coverage"] = {
        "status": edge_status,
        "x_offset_mm": x_offset,
        "layer_count": len(layer_summaries),
        "failure_count": len(extent_failures),
        "failures": extent_failures[:100],
    }
    result["layer_summaries"] = layer_summaries
    result["plot_segments"] = extrusion_segments
    result["slicer_estimates"] = slicer_estimates
    return result
