"""Shrink the India state boundary file so the map loads quickly.

Usage (run once, on your computer):
    python tools/shrink_geojson.py assets/india_states_original.geojson assets/india_states.geojson

Keeps only the state-name property and simplifies the borders (tolerance 0.01 degrees, about 1 km).
Uses only the Python standard library, so nothing needs to be installed."""
import json
import math
import sys

NAME_KEYS = ("st_nm", "ST_NM", "NAME_1", "state", "STATE", "name", "NAME")


def _rdp(points, eps):
    """Ramer-Douglas-Peucker: drops points that are closer than ``eps`` to the simplified line."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        x1, y1 = points[i][:2]
        x2, y2 = points[j][:2]
        dx, dy = x2 - x1, y2 - y1
        norm = math.hypot(dx, dy)
        best, best_d = -1, 0.0
        for k in range(i + 1, j):
            x, y = points[k][:2]
            d = math.hypot(x - x1, y - y1) if norm == 0 else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
            if d > best_d:
                best, best_d = k, d
        if best != -1 and best_d > eps:
            keep[best] = True
            stack.append((i, best))
            stack.append((best, j))
    return [p for p, k in zip(points, keep) if k]


def _ring(ring, tol):
    out = _rdp(ring, tol)
    return out if len(out) >= 4 else ring          # tiny islands: keep the original outline


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.01
    with open(src, encoding="utf-8") as fh:
        geo = json.load(fh)
    points_before = points_after = 0
    for f in geo["features"]:
        f["properties"] = {k: v for k, v in (f.get("properties") or {}).items() if k in NAME_KEYS}
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        new_polys = []
        for poly in polys:
            new_rings = []
            for ring in poly:
                points_before += len(ring)
                r = _ring(ring, tol)
                points_after += len(r)
                new_rings.append(r)
            new_polys.append(new_rings)
        g["coordinates"] = new_polys[0] if g["type"] == "Polygon" else new_polys
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(geo, fh, separators=(",", ":"))
    print(f"points {points_before:,} -> {points_after:,}; written to {dst}")


if __name__ == "__main__":
    main()