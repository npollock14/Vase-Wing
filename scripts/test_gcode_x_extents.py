from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any


MOVE_RE = re.compile(r"([A-Za-z])([-+]?\d*\.?\d+)")


@dataclass
class LayerExtent:
    layer: int
    z: float
    min_x: float
    max_x: float

    @property
    def chord(self) -> float:
        return self.max_x - self.min_x


def _tokens(code: str) -> dict[str, float | str]:
    values: dict[str, float | str] = {}
    for key, value in MOVE_RE.findall(code):
        key = key.upper()
        if key in {"G", "M"}:
            values[key] = f"{key}{int(float(value))}"
        else:
            values[key] = float(value)
    return values


def parse_layer_extents(path: Path) -> list[LayerExtent]:
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("rb") as handle:
        header = handle.read(1024)
    if b"\x00" in header:
        raise ValueError("G-code appears to be binary; export ASCII G-code for this test")

    absolute_e = True
    x = y = z = e = None
    layer = -1
    current: dict[str, Any] | None = None
    rows: list[LayerExtent] = []

    def start_layer(z_value: float | None) -> None:
        nonlocal current, layer
        layer += 1
        current = {"layer": layer, "z": 0.0 if z_value is None else z_value, "min_x": math.inf, "max_x": -math.inf}

    def ensure_layer(z_value: float | None) -> dict[str, Any]:
        if current is None:
            start_layer(z_value)
        assert current is not None
        if z_value is not None:
            current["z"] = z_value
        return current

    def flush_layer() -> None:
        nonlocal current
        if current is None:
            return
        if math.isfinite(current["min_x"]) and math.isfinite(current["max_x"]):
            rows.append(
                LayerExtent(
                    layer=int(current["layer"]),
                    z=float(current["z"]),
                    min_x=float(current["min_x"]),
                    max_x=float(current["max_x"]),
                )
            )
        current = None

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            code, _, comment = line.partition(";")
            comment = comment.strip()
            if comment.startswith("LAYER_CHANGE"):
                flush_layer()
                start_layer(z)
                continue
            if comment.startswith("Z:"):
                try:
                    z = float(comment[2:])
                    ensure_layer(z)["z"] = z
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
            if op == "G92":
                if "E" in values:
                    e = float(values["E"])
                continue
            if op not in {"G0", "G1"}:
                continue

            old_x, old_y, old_e = x, y, e
            new_x = float(values["X"]) if "X" in values else x
            new_y = float(values["Y"]) if "Y" in values else y
            new_z = float(values["Z"]) if "Z" in values else z
            e_delta = 0.0
            if "E" in values:
                new_e = float(values["E"])
                if absolute_e:
                    e_delta = 0.0 if old_e is None else new_e - old_e
                    e = new_e
                else:
                    e_delta = new_e
                    e = (0.0 if e is None else e) + new_e

            if e_delta > 1e-7 and old_x is not None and old_y is not None and new_x is not None and new_y is not None:
                bucket = ensure_layer(new_z)
                bucket["min_x"] = min(bucket["min_x"], old_x, new_x)
                bucket["max_x"] = max(bucket["max_x"], old_x, new_x)

            x, y, z = new_x, new_y, new_z

    flush_layer()
    return rows


def _local_median(rows: list[LayerExtent], index: int, radius: int) -> tuple[float, float, float] | None:
    start = max(0, index - radius)
    end = min(len(rows), index + radius + 1)
    neighbors = rows[start:index] + rows[index + 1 : end]
    if len(neighbors) < max(2, radius):
        return None
    return (
        median(row.min_x for row in neighbors),
        median(row.max_x for row in neighbors),
        median(row.chord for row in neighbors),
    )


def evaluate_extents(
    rows: list[LayerExtent],
    max_jump_mm: float,
    max_local_residual_mm: float,
    window_layers: int,
    ignore_first_layers: int,
    ignore_last_layers: int,
) -> dict[str, Any]:
    radius = max(1, window_layers // 2)
    first = max(0, ignore_first_layers)
    last = len(rows) - max(0, ignore_last_layers)
    checked_indexes = set(range(first, max(first, last)))
    failures: list[dict[str, Any]] = []
    worst_jumps: list[dict[str, Any]] = []
    worst_residuals: list[dict[str, Any]] = []

    previous: LayerExtent | None = None
    for index, row in enumerate(rows):
        if previous is not None and index in checked_indexes:
            min_jump = abs(row.min_x - previous.min_x)
            max_jump = abs(row.max_x - previous.max_x)
            chord_jump = abs(row.chord - previous.chord)
            jump = max(min_jump, max_jump, chord_jump)
            item = {
                "layer": row.layer,
                "z": row.z,
                "jump_mm": jump,
                "min_jump_mm": min_jump,
                "max_jump_mm": max_jump,
                "chord_jump_mm": chord_jump,
                "min_x": row.min_x,
                "max_x": row.max_x,
            }
            worst_jumps.append(item)
            if jump > max_jump_mm:
                failures.append({"reason": "extent_jump", **item})
        previous = row

    for index, row in enumerate(rows):
        if index not in checked_indexes:
            continue
        local = _local_median(rows, index, radius)
        if local is None:
            continue
        med_min, med_max, med_chord = local
        min_residual = abs(row.min_x - med_min)
        max_residual = abs(row.max_x - med_max)
        chord_residual = abs(row.chord - med_chord)
        residual = max(min_residual, max_residual, chord_residual)
        item = {
            "layer": row.layer,
            "z": row.z,
            "residual_mm": residual,
            "min_residual_mm": min_residual,
            "max_residual_mm": max_residual,
            "chord_residual_mm": chord_residual,
            "min_x": row.min_x,
            "max_x": row.max_x,
            "local_median_min_x": med_min,
            "local_median_max_x": med_max,
        }
        worst_residuals.append(item)
        if residual > max_local_residual_mm:
            failures.append({"reason": "local_extent_spike", **item})

    worst_jumps.sort(key=lambda item: item["jump_mm"], reverse=True)
    worst_residuals.sort(key=lambda item: item["residual_mm"], reverse=True)
    failures.sort(key=lambda item: max(item.get("jump_mm", 0.0), item.get("residual_mm", 0.0)), reverse=True)

    return {
        "status": "pass" if not failures else "fail",
        "layer_count": len(rows),
        "checked_layer_count": len(checked_indexes),
        "thresholds": {
            "max_jump_mm": max_jump_mm,
            "max_local_residual_mm": max_local_residual_mm,
            "window_layers": window_layers,
            "ignore_first_layers": ignore_first_layers,
            "ignore_last_layers": ignore_last_layers,
        },
        "failure_count": len(failures),
        "failures": failures[:25],
        "worst_jumps": worst_jumps[:10],
        "worst_residuals": worst_residuals[:10],
    }


def write_plot(rows: list[LayerExtent], report: dict[str, Any], path: Path) -> None:
    import matplotlib.pyplot as plt

    failed_layers = {item["layer"] for item in report.get("failures", [])}
    bad = [row for row in rows if row.layer in failed_layers]

    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot([row.z for row in rows], [row.min_x for row in rows], label="actual min X", color="#2563eb", linewidth=1.2)
    ax.plot([row.z for row in rows], [row.max_x for row in rows], label="actual max X", color="#dc2626", linewidth=1.2)
    if bad:
        ax.scatter([row.z for row in bad], [row.min_x for row in bad], color="black", s=12, label="flagged layer")
        ax.scatter([row.z for row in bad], [row.max_x for row in bad], color="black", s=12)
    ax.set_title("Actual X Extents Artifact Test")
    ax.set_xlabel("Z / span height (mm)")
    ax.set_ylabel("G-code X (mm)")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _print_summary(report: dict[str, Any]) -> None:
    print(f"X extent artifact test: {report['status'].upper()}")
    print(f"Layers checked: {report['checked_layer_count']} / {report['layer_count']}")
    print(
        "Thresholds: "
        f"jump <= {report['thresholds']['max_jump_mm']} mm, "
        f"local residual <= {report['thresholds']['max_local_residual_mm']} mm, "
        f"window = {report['thresholds']['window_layers']} layers"
    )
    print(f"Failures: {report['failure_count']}")
    if report["failures"]:
        print("Worst failures:")
        for item in report["failures"][:8]:
            metric = item.get("jump_mm", item.get("residual_mm", 0.0))
            print(
                f"  {item['reason']} L{item['layer']} z={item['z']:.2f} "
                f"metric={metric:.3f} actual=[{item['min_x']:.3f},{item['max_x']:.3f}]"
            )
        return
    if report["worst_jumps"]:
        item = report["worst_jumps"][0]
        print(
            "Worst jump: "
            f"L{item['layer']} z={item['z']:.2f} {item['jump_mm']:.3f} mm "
            f"actual=[{item['min_x']:.3f},{item['max_x']:.3f}]"
        )
    if report["worst_residuals"]:
        item = report["worst_residuals"][0]
        print(
            "Worst local residual: "
            f"L{item['layer']} z={item['z']:.2f} {item['residual_mm']:.3f} mm "
            f"actual=[{item['min_x']:.3f},{item['max_x']:.3f}]"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail fast when actual per-layer G-code xmin/xmax extents show artifact spikes."
    )
    parser.add_argument("gcode", type=Path, help="ASCII G-code file to check")
    parser.add_argument("--max-jump-mm", type=float, default=2.0, help="Maximum allowed neighboring-layer extent jump")
    parser.add_argument(
        "--max-local-residual-mm",
        type=float,
        default=2.0,
        help="Maximum allowed deviation from the local rolling median extent",
    )
    parser.add_argument("--window-layers", type=int, default=9, help="Odd-ish rolling median window size")
    parser.add_argument("--ignore-first-layers", type=int, default=8, help="Root layers to skip for startup transients")
    parser.add_argument("--ignore-last-layers", type=int, default=0, help="Tip layers to skip if the end cap is intentionally noisy")
    parser.add_argument("--min-layers", type=int, default=20, help="Minimum extrusion layers required for a valid test")
    parser.add_argument("--json-out", type=Path, help="Optional path for machine-readable results")
    parser.add_argument("--plot", type=Path, help="Optional path for a quick xmin/xmax plot with failed layers marked")
    args = parser.parse_args(argv)

    try:
        rows = parse_layer_extents(args.gcode)
    except Exception as exc:  # noqa: BLE001 - CLI should present parse errors plainly.
        print(f"Failed to parse G-code extents: {exc}", file=sys.stderr)
        return 2

    if len(rows) < args.min_layers:
        print(f"Only found {len(rows)} extrusion layers; need at least {args.min_layers}", file=sys.stderr)
        return 2

    report = evaluate_extents(
        rows,
        max_jump_mm=args.max_jump_mm,
        max_local_residual_mm=args.max_local_residual_mm,
        window_layers=args.window_layers,
        ignore_first_layers=args.ignore_first_layers,
        ignore_last_layers=args.ignore_last_layers,
    )
    report["gcode"] = str(args.gcode)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.plot:
        write_plot(rows, report, args.plot)
    _print_summary(report)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())