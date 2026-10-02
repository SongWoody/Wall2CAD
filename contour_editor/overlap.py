"""Positive-area intersections of current polygons, independent of import flags."""
from shapely.geometry import Polygon

# Numerical tolerance in original image square pixels, not an area-percentage gate.
AREA_EPSILON = 1e-6


def polygon_parts(geometry):
    """Yield only surfaces; intersections may also contain isolated lines/points."""
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def find_overlaps(stones):
    neighbors = {s.id: set() for s in stones}
    shapes = [(s.id, Polygon(s.points)) for s in stones]
    shapes = sorted(((key, shape, shape.bounds) for key, shape in shapes), key=lambda item: item[2][0])
    regions = {}
    for i, (key, shape, bounds) in enumerate(shapes):
        for other_key, other, other_bounds in shapes[i + 1:]:
            if other_bounds[0] >= bounds[2]:
                break
            if other_bounds[1] >= bounds[3] or bounds[1] >= other_bounds[3]:
                continue
            intersection = shape.intersection(other)
            if intersection.area > AREA_EPSILON:
                pair = tuple(sorted((key, other_key)))
                regions[pair] = intersection
                neighbors[key].add(other_key)
                neighbors[other_key].add(key)
    return neighbors, regions
