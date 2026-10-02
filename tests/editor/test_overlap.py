from types import SimpleNamespace

import pytest

from contour_editor.overlap import find_overlaps, polygon_parts


def stone(key, points):
    return SimpleNamespace(id=key, points=points)


@pytest.mark.parametrize("other, area", [
    ([(9.99, 0), (20, 0), (20, 10), (9.99, 10)], 0.1),  # 0.1%, below old 5% rule.
    ([(10, 0), (20, 0), (20, 10), (10, 10)], 0),  # Shared boundary only.
    ([(10, 10), (20, 10), (20, 20), (10, 20)], 0),  # Point contact only.
    ([(11, 0), (20, 0), (20, 10), (11, 10)], 0),
    ([(2, 2), (8, 2), (8, 8), (2, 8)], 36),  # Containment also needs review.
    ([(0, 0), (10, 0), (10, 10), (0, 10)], 100),
])
def test_overlap_area_including_thin_slivers_and_contacts(other, area):
    a = stone("a", [(0, 0), (10, 0), (10, 10), (0, 10)])
    b = stone("b", other)
    neighbors, regions = find_overlaps([a, b])
    if area:
        assert neighbors == {"a": {"b"}, "b": {"a"}}
        assert regions[("a", "b")].area == pytest.approx(area)
    else:
        assert neighbors == {"a": set(), "b": set()}
        assert not regions


def test_concave_polygons_with_disconnected_intersections():
    u = stone("u", [(0, 0), (10, 0), (10, 10), (8, 10), (8, 2), (2, 2), (2, 10), (0, 10)])
    bar = stone("bar", [(-1, 4), (11, 4), (11, 6), (-1, 6)])
    neighbors, regions = find_overlaps([u, bar])
    geometry = regions[("bar", "u")]
    assert geometry.area == 8
    assert len(list(polygon_parts(geometry))) == 2
    assert neighbors["bar"] == {"u"}
