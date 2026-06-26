from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


Facet = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def _read_binary_stl(path: Path) -> list[Facet]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"STL is too small: {path}")
    tri_count = struct.unpack("<I", data[80:84])[0]
    expected_size = 84 + tri_count * 50
    if expected_size != len(data):
        raise ValueError(f"STL does not look like binary STL: {path}")

    facets: list[Facet] = []
    for i in range(tri_count):
        offset = 84 + i * 50 + 12
        vertices = []
        for j in range(3):
            vertices.append(struct.unpack("<fff", data[offset + j * 12 : offset + (j + 1) * 12]))
        facets.append((vertices[0], vertices[1], vertices[2]))
    return facets


def _bounds(facets: list[Facet]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    xs, ys, zs = [], [], []
    for facet in facets:
        for x, y, z in facet:
            xs.append(x)
            ys.append(y)
            zs.append(z)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _plane_segments(facets: list[Facet], z_plane: float) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    eps = 1e-7
    for facet in facets:
        points: list[tuple[float, float]] = []
        vertices = [facet[0], facet[1], facet[2], facet[0]]
        for a, b in zip(vertices, vertices[1:]):
            za = a[2] - z_plane
            zb = b[2] - z_plane
            if abs(za) < eps and abs(zb) < eps:
                continue
            if za * zb > 0:
                continue
            if abs(za - zb) < eps:
                continue
            t = -za / (zb - za)
            if -eps <= t <= 1 + eps:
                x = a[0] + t * (b[0] - a[0])
                y = a[1] + t * (b[1] - a[1])
                point = (x, y)
                if not any(math.hypot(point[0] - p[0], point[1] - p[1]) < 1e-5 for p in points):
                    points.append(point)
        if len(points) == 2:
            segments.append((points[0], points[1]))
    return segments


def plot_sections(stl: Path, output: Path, z_values: list[float], title: str) -> None:
    facets = _read_binary_stl(stl)
    mn, mx = _bounds(facets)
    cols = min(4, len(z_values))
    rows = math.ceil(len(z_values) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.5 * rows), squeeze=False, sharex=True, sharey=True)
    for ax in axes.flat:
        ax.set_axis_off()

    for ax, z_plane in zip(axes.flat, z_values):
        ax.set_axis_on()
        segments = _plane_segments(facets, z_plane)
        for (x0, y0), (x1, y1) in segments:
            ax.plot([x0, x1], [y0, y1], color="#111827", linewidth=0.45, alpha=0.75)
        ax.set_title(f"Z={z_plane:.1f} mm\n{len(segments)} segs", fontsize=10)
        ax.set_aspect("equal", adjustable="box")
        ax.grid(True, alpha=0.18)
        ax.set_xlim(mn[0] - 5, mx[0] + 5)
        ax.set_ylim(mn[1] - 5, mx[1] + 5)

    fig.suptitle(title)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot X/Y sections through a binary STL at model Z stations.")
    parser.add_argument("stl", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="STL sections")
    parser.add_argument("--z", nargs="*", type=float)
    parser.add_argument("--count", type=int, default=12)
    args = parser.parse_args()

    facets = _read_binary_stl(args.stl)
    mn, mx = _bounds(facets)
    if args.z:
        z_values = args.z
    else:
        z_min, z_max = mn[2], mx[2]
        step = (z_max - z_min) / max(args.count + 1, 2)
        z_values = [z_min + step * (i + 1) for i in range(args.count)]
    plot_sections(args.stl, args.output, z_values, args.title)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
