import json
from pathlib import Path

import ezdxf
import pytest

from contour_editor.model import Document, validate_polygon


@pytest.fixture
def document(tmp_path):
    photo = tmp_path / "photo.jpeg"
    photo.write_bytes(b"test image identity; no raster decoding in model")
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([
        {"id": "S001", "points": [[10, 10], [80, 10], [80, 80], [10, 80]], "layer": "STONE_CANDIDATE"},
        {"id": "S002", "points": [[100, 10], [180, 10], [180, 80], [100, 80]], "layer": "REVIEW_OVERLAP"},
    ]))
    return Document.from_candidates(photo, 200, 100, candidates)


def test_edits_preserve_neighbors_and_originals_with_undo(document):
    a, b = document.active
    original, neighbor = a.original, b.points
    document.change(a.id, points=[(20, 20), *a.points[1:]], label="move")
    assert b.points == neighbor and a.original == original
    moved = a.points
    document.change(b.id, deleted=True)
    assert len(document.active) == 1
    document.undo()
    assert not b.deleted
    document.undo()
    assert a.points == original
    document.redo()
    assert a.points == moved


@pytest.mark.parametrize("points", [
    [(0, 0), (10, 0)],
    [(0, 0), (10, 10), (0, 10), (10, 0)],
    [(0, 0), (10, 0), (5, 0), (5, 10)],
    [(0, 0), (10, 0), (0, 0), (0, 10)],
    [(0, 0), (float("nan"), 0), (0, 10)],
    [(-1, 0), (10, 0), (0, 10)],
])
def test_invalid_edits_are_transactional(document, points):
    before = document.stones["S001"].points
    with pytest.raises(ValueError):
        document.change("S001", points=points)
    assert document.stones["S001"].points == before
    assert document.cursor == 0


def test_straight_edge_vertex_allowed():
    validate_polygon(((0, 0), (5, 0), (10, 0), (10, 10), (0, 10)), 100, 100)


def test_round_trip_keeps_original_edit_deletion_and_relative_photo(document, tmp_path):
    document.change("S001", points=[(20, 20), (80, 10), (80, 80), (10, 80)])
    document.change("S002", deleted=True)
    path = tmp_path / "review.wall2cad.json"
    document.save(path)
    assert not document.dirty
    loaded = Document.load(path)
    assert not loaded.dirty
    assert loaded.stones == document.stones
    assert json.loads(path.read_text())["image"]["path"] == "photo.jpeg"
    assert loaded.stones["S001"].original != loaded.stones["S001"].points
    document.undo()
    assert document.dirty
    document.redo()
    assert not document.dirty
    document.undo()
    document.change("S001", points=document.stones["S001"].original)
    assert document.dirty  # A new branch must not inherit an abandoned save point.


def test_dxf_contains_only_active_closed_shapes_with_correct_y(document, tmp_path):
    document.change("S001", points=[(20, 20), (80, 10), (80, 80), (10, 80)])
    document.change("S002", deleted=True)
    path = tmp_path / "edited.dxf"
    document.export_dxf(path)
    drawing = ezdxf.readfile(path)
    entities = list(drawing.modelspace())
    assert drawing.units == 0 and len(entities) == 1
    entity = entities[0]
    assert entity.closed
    assert list(entity.get_points("xy")) == [(x, 100 - y) for x, y in document.active[0].points]
    assert entity.get_xdata("WALL2CAD_REVIEW")[0].value == "S001"
    assert not drawing.audit().has_errors


def test_sources_protected_and_wrong_photo_rejected(document, tmp_path):
    for source in (document.source_path, document.image_path):
        before = source.read_bytes()
        with pytest.raises(ValueError):
            document.save(source)
        with pytest.raises(ValueError):
            document.export_dxf(source)
        assert source.read_bytes() == before
    path = tmp_path / "review.wall2cad.json"
    document.save(path)
    document.image_path.write_bytes(b"different photo")
    with pytest.raises(ValueError, match="사진"):
        Document.load(path)


def test_failed_save_preserves_previous_file(document, tmp_path, monkeypatch):
    path = tmp_path / "review.wall2cad.json"
    document.save(path)
    before = path.read_bytes()
    document.change("S001", deleted=True)
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr("contour_editor.model.os.replace", fail)
    with pytest.raises(OSError):
        document.save(path)
    assert document.dirty and path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["candidates.json", "photo.jpeg", "review.wall2cad.json"]


def test_current_overlap_follows_edits_history_deletion_save_and_export(document, tmp_path):
    # Imported REVIEW_OVERLAP is stale: these two squares initially do not overlap.
    assert not document.has_overlap("S002")
    document.change("S002", points=[(79, 10), (180, 10), (180, 80), (79, 80)])
    assert document.overlaps["S001"] == {"S002"}
    assert document.overlap_regions[("S001", "S002")].area == 70
    document.undo()
    assert not document.has_overlap("S001")
    document.redo()
    assert document.has_overlap("S001")
    document.change("S002", deleted=True)
    assert not document.has_overlap("S001") and not document.overlap_regions
    document.undo()
    path = tmp_path / "overlap.wall2cad.json"
    document.save(path)
    restored = Document.load(path)
    assert restored.overlaps == document.overlaps
    output = tmp_path / "overlap.dxf"
    restored.export_dxf(output)
    assert all(e.dxf.layer == "REVIEW_OVERLAP" for e in ezdxf.readfile(output).modelspace())
    restored.change("S002", points=restored.stones["S002"].original)
    restored.export_dxf(output)
    assert all(e.dxf.layer == "STONE_CANDIDATE" for e in ezdxf.readfile(output).modelspace())
    assert restored.stones["S002"].metadata["layer"] == "REVIEW_OVERLAP"
