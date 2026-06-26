from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any


def _normal(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> tuple[float, float, float] | None:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-9:
        return None
    return nx / length, ny / length, nz / length


def _read_ascii_facets(path: Path) -> list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]:
    facets = []
    current: list[tuple[float, float, float]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4 and parts[0].lower() == "vertex":
                try:
                    current.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except ValueError:
                    current = []
            if len(current) == 3:
                facets.append((current[0], current[1], current[2]))
                current = []
    return facets


def _write_binary_stl(path: Path, facets: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]) -> None:
    header = b"Cleaned by Vase-Wing validation".ljust(80, b" ")
    with path.open("wb") as f:
        f.write(header)
        f.write(struct.pack("<I", len(facets)))
        for a, b, c in facets:
            n = _normal(a, b, c)
            if n is None:
                continue
            f.write(struct.pack("<fff", *n))
            f.write(struct.pack("<fff", *a))
            f.write(struct.pack("<fff", *b))
            f.write(struct.pack("<fff", *c))
            f.write(struct.pack("<H", 0))


def clean_stl(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"stage": "stl_clean", "status": "skipped", "path": str(path)}
    if not path.exists():
        result["status"] = "fail"
        result["error"] = "STL does not exist"
        return result

    head = path.read_bytes()[:256]
    if not head.lstrip().lower().startswith(b"solid"):
        result["reason"] = "STL already appears to be binary"
        return result

    original_bytes = path.stat().st_size
    facets = _read_ascii_facets(path)
    kept = []
    removed_degenerate = 0
    for facet in facets:
        if _normal(*facet) is None:
            removed_degenerate += 1
            continue
        kept.append(facet)

    if not kept:
        result["status"] = "fail"
        result["error"] = "No non-degenerate triangles found"
        return result

    tmp = path.with_suffix(path.suffix + ".tmp")
    _write_binary_stl(tmp, kept)
    tmp.replace(path)

    result.update(
        {
            "status": "pass",
            "format": "binary",
            "original_bytes": original_bytes,
            "cleaned_bytes": path.stat().st_size,
            "triangles_in": len(facets),
            "triangles_out": len(kept),
            "degenerate_triangles_removed": removed_degenerate,
        }
    )
    return result
