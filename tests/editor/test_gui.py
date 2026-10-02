import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from contour_editor.window import EditorWindow


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def window(app, tmp_path):
    image = QImage(400, 300, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.gray)
    photo = tmp_path / "photo.png"
    image.save(str(photo))
    contours = tmp_path / "candidates.json"
    contours.write_text(json.dumps([
        {"id": "S001", "points": [[50, 50], [150, 50], [150, 150], [50, 150]]},
        {"id": "S002", "points": [[220, 50], [320, 50], [320, 150], [220, 150]]},
    ]))
    w = EditorWindow()
    w.show()
    w.load_candidates(photo, contours)
    app.processEvents()
    yield w
    w.document.clean_cursor = w.document.cursor
    w.close()
    app.processEvents()


def click(canvas, point):
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=canvas.to_screen(point).toPoint())


def test_mouse_edit_add_delete_undo_and_neighbor_preservation(window, app):
    c, doc = window.canvas, window.document
    original = doc.stones["S001"].original
    neighbor = doc.stones["S002"].points
    click(c, (100, 100))
    assert c.selected == "S001"
    start, end = c.to_screen((50, 50)).toPoint(), c.to_screen((65, 65)).toPoint()
    QTest.mousePress(c, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(c, end)
    assert doc.stones["S001"].points == original  # Preview must not change model.
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, pos=end)
    assert doc.stones["S001"].points != original
    assert doc.stones["S002"].points == neighbor
    assert doc.cursor == 1
    window.undo_action.trigger()
    assert doc.stones["S001"].points == original
    window.redo_action.trigger()
    assert doc.stones["S001"].points != original
    QTest.mouseDClick(c, Qt.MouseButton.LeftButton, pos=c.to_screen((150, 100)).toPoint())
    assert len(doc.stones["S001"].points) == 5
    assert window.delete_vertex_action.isEnabled()
    QTest.keyClick(c, Qt.Key.Key_Delete)
    assert len(doc.stones["S001"].points) == 4
    window.delete_stone_action.trigger()
    assert len(doc.active) == 1
    window.undo_action.trigger()
    assert len(doc.active) == 2 and c.selected == "S001"


def test_invalid_drag_reverted_and_escape_cancels(window):
    c, doc = window.canvas, window.document
    click(c, (100, 100))
    original = doc.stones["S001"].points
    QTest.mousePress(c, Qt.MouseButton.LeftButton, pos=c.to_screen((50, 50)).toPoint())
    QTest.mouseMove(c, c.to_screen((180, 100)).toPoint())
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, pos=c.to_screen((180, 100)).toPoint())
    assert doc.stones["S001"].points == original
    assert "교차" in window.statusBar().currentMessage()
    QTest.mousePress(c, Qt.MouseButton.LeftButton, pos=c.to_screen((50, 50)).toPoint())
    QTest.mouseMove(c, c.to_screen((60, 60)).toPoint())
    QTest.keyClick(c, Qt.Key.Key_Escape)
    QTest.mouseRelease(c, Qt.MouseButton.LeftButton, pos=c.to_screen((60, 60)).toPoint())
    assert doc.stones["S001"].points == original


def test_pan_and_hidden_lines_do_not_edit(window):
    c, doc = window.canvas, window.document
    before = c.offset
    QTest.mousePress(c, Qt.MouseButton.MiddleButton, pos=QPoint(100, 100))
    QTest.mouseMove(c, QPoint(140, 120))
    QTest.mouseRelease(c, Qt.MouseButton.MiddleButton, pos=QPoint(140, 120))
    assert c.offset != before
    window.toggle_view("show_lines", False)
    click(c, (100, 100))
    assert c.selected is None and doc.cursor == 0


def test_unsaved_close_cancel_then_save_failure_keeps_window(window, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    assert not window.close()
    assert window.isVisible()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save)
    monkeypatch.setattr(window, "save_project", lambda: False)
    assert not window.may_discard()


def test_overlap_list_detail_and_area_overlay_update(window, app):
    c, doc = window.canvas, window.document
    window.toggle_view("show_image", False)
    # A thin overlap, previously excluded by the 5% threshold.
    doc.change("S002", points=[(149, 50), (320, 50), (320, 150), (149, 150)])
    window.refresh()
    c.select("S001")
    app.processEvents()
    assert "겹침 1" in window.list.item(0).text()
    assert "S002" in window.detail.text()
    assert "2 · 1쌍" in window.count.text()
    c.select(None)
    pixel = c.to_screen((149.5, 100)).toPoint()
    highlighted = c.grab().toImage().pixelColor(pixel)
    window.toggle_view("show_overlaps", False)
    plain = c.grab().toImage().pixelColor(pixel)
    assert highlighted != plain
    c.select("S002")
    c.delete_stone()
    assert "겹침" not in window.list.item(0).text()
    window.undo()
    assert "겹침 1" in window.list.item(0).text()
