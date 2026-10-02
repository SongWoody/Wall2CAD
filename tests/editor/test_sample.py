"""Optional integration test using the accepted sample and external photo."""
from pathlib import Path

import ezdxf
import pytest

from contour_editor.model import Document, file_hash


WORKSPACE = Path(__file__).resolve().parents[3]
REPOSITORY = Path(__file__).resolve().parents[2]
IMAGE = WORKSPACE / "inputoutput/building_001_input.jpeg"
CANDIDATES = REPOSITORY / "docs/baselines/building_001_v1/candidates.json"


@pytest.mark.skipif(not IMAGE.exists() or not CANDIDATES.exists(), reason="Sample photo is external or accepted vectors are missing")
def test_accepted_319_contours_round_trip_and_edit_isolation(tmp_path):
    hashes = [file_hash(path) for path in (IMAGE, CANDIDATES)]
    doc = Document.from_candidates(IMAGE, 13788, 2574, CANDIDATES)
    assert len(doc.active) == 319
    assert {"S091", "S095"} <= doc.overlaps["S093"]
    for pair in (("S091", "S093"), ("S093", "S095")):
        assert doc.overlap_regions[pair].area > 0
        assert all(not doc.stones[key].metadata["overlap_with"] for key in pair)
    originals = {s.id: s.points for s in doc.active}
    baseline = tmp_path / "baseline.dxf"
    doc.export_dxf(baseline)

    def check_dxf(path, expected):
        drawing = ezdxf.readfile(path)
        entities = list(drawing.modelspace())
        assert len(entities) == len(expected)
        assert drawing.units == 0
        assert not drawing.audit().has_errors
        for entity, stone in zip(entities, expected):
            assert entity.closed
            assert list(entity.get_points("xy")) == [(x, doc.height - y) for x, y in stone.points]
            assert entity.get_xdata("WALL2CAD_REVIEW")[0].value == stone.id
            assert entity.dxf.layer == ("REVIEW_OVERLAP" if doc.has_overlap(stone.id) else "STONE_CANDIDATE")

    check_dxf(baseline, doc.active)
    pts = list(doc.stones["S001"].points)
    pts[0] = (pts[0][0] + 1, pts[0][1] + 1)
    doc.change("S001", points=pts)
    doc.change("S002", deleted=True)
    assert all(s.points == originals[s.id] for s in doc.stones.values() if s.id != "S001")
    project = tmp_path / "edit.wall2cad.json"
    doc.save(project)
    loaded = Document.load(project)
    assert doc.stones == loaded.stones
    edited = tmp_path / "edited.dxf"
    loaded.export_dxf(edited)
    assert len(loaded.active) == 318
    check_dxf(edited, loaded.active)
    doc.undo()
    doc.undo()
    assert all(not s.deleted and s.points == originals[s.id] for s in doc.stones.values())
    assert hashes == [file_hash(path) for path in (IMAGE, CANDIDATES)]
