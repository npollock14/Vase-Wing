from __future__ import annotations

import struct
from pathlib import Path
from typing import Any


def _bounds_from_vertices(vertices: list[tuple[float, float, float]]) -> dict[str, Any]:
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    mn = [min(xs), min(ys), min(zs)]
    mx = [max(xs), max(ys), max(zs)]
    return {"min": mn, "max": mx, "size": [mx[i] - mn[i] for i in range(3)]}


def inspect_stl(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"stage": "stl", "status": "fail", "path": str(path)}
    if not path.exists():
        result["error"] = "STL does not exist"
        return result
    data = path.read_bytes()
    result["bytes"] = len(data)
    if len(data) < 84:
        result["error"] = "STL is too small"
        return result

    vertices: list[tuple[float, float, float]] = []
    tri_count = struct.unpack("<I", data[80:84])[0]
    expected_binary_size = 84 + tri_count * 50
    if expected_binary_size == len(data):
        result["format"] = "binary"
        for i in range(tri_count):
            offset = 84 + i * 50 + 12
            for j in range(3):
                vertices.append(struct.unpack("<fff", data[offset + j * 12 : offset + (j + 1) * 12]))
    else:
        result["format"] = "ascii"
        text = data.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) == 4 and parts[0].lower() == "vertex":
                try:
                    vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except ValueError:
                    pass

    if not vertices:
        result["error"] = "No STL vertices found"
        return result
    result["status"] = "pass"
    result["vertex_count"] = len(vertices)
    result["triangle_count"] = len(vertices) // 3
    result["bounding_box"] = _bounds_from_vertices(vertices)
    result["watertightness"] = "skipped: install trimesh for topology checks"
    return result
