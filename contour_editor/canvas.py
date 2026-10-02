"""Photo canvas. Drag previews never mutate the saved vector model."""
from __future__ import annotations

import math
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF, QTransform
from PyQt6.QtWidgets import QWidget

from .overlap import polygon_parts


def nearest_segment(points, pos):
    best = (float("inf"), 0, points[0])
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        t = max(0, min(1, ((pos[0] - a[0]) * dx + (pos[1] - a[1]) * dy) / (dx * dx + dy * dy)))
        p = (a[0] + t * dx, a[1] + t * dy)
        distance = math.dist(p, pos)
        if distance < best[0]:
            best = distance, i, p
    return best


class Canvas(QWidget):
    selectionChanged = pyqtSignal()
    edited = pyqtSignal()
    notice = pyqtSignal(str)
    zoomChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.document = None
        self.image = None
        self.selected = None
        self.vertex = None
        self.preview = None
        self.scale = 1.0
        self.offset = QPointF()
        self.show_image = True
        self.show_lines = True
        self.show_original = False
        self.show_overlaps = True
        self.space = False
        self.pan_start = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)

    def set_document(self, document, image):
        self.document, self.image = document, image
        self.selected, self.vertex, self.preview = None, None, None
        self.fit()
        self.selectionChanged.emit()

    def transform(self):
        return QTransform(self.scale, 0, 0, self.scale, self.offset.x(), self.offset.y())

    def to_image(self, pos):
        p = self.transform().inverted()[0].map(QPointF(pos))
        return p.x(), p.y()

    def to_screen(self, point):
        return self.transform().map(QPointF(*point))

    def fit(self):
        if not self.document:
            return
        self.cancel_drag()
        w, h = self.document.width, self.document.height
        self.scale = min((self.width() - 40) / w, (self.height() - 40) / h)
        self.offset = QPointF((self.width() - w * self.scale) / 2, (self.height() - h * self.scale) / 2)
        self.zoomChanged.emit(self.scale)
        self.update()

    def focus_stone(self, stone_id):
        self.select(stone_id)
        stone = self.current()
        if stone is None:
            return
        xs, ys = zip(*stone.points)
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        self.scale = min(5, (self.width() - 160) / max(1, w), (self.height() - 160) / max(1, h))
        self.offset = QPointF(self.width() / 2 - (max(xs) + min(xs)) / 2 * self.scale,
                              self.height() / 2 - (max(ys) + min(ys)) / 2 * self.scale)
        self.zoomChanged.emit(self.scale)
        self.update()

    def current(self):
        stone = self.document.stones.get(self.selected) if self.document else None
        return stone if stone and not stone.deleted else None

    def select(self, stone_id):
        self.cancel_drag()
        self.selected, self.vertex = stone_id, None
        self.selectionChanged.emit()
        self.update()

    def cancel_drag(self):
        self.preview = None
        self.pan_start = None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#182126"))
        if self.document is None:
            p.setPen(QColor("#c6d2d8"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       "사진과 윤곽 JSON을 열거나\n저장한 편집 프로젝트를 여세요.")
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setTransform(self.transform())
        rect = QRectF(0, 0, self.document.width, self.document.height)
        if self.show_image:
            p.drawImage(rect, self.image)
        else:
            p.fillRect(rect, QColor("#28363f"))
        if not self.show_lines:
            return
        visible = self.transform().inverted()[0].mapRect(QRectF(self.rect()))
        # Keep selected outlines/handles above the intersection highlight. During
        # a drag the index still represents committed geometry, so hide it briefly.
        if self.show_overlaps and self.preview is None:
            for geometry in self.document.overlap_regions.values():
                for part in polygon_parts(geometry):
                    path = QPainterPath()
                    path.setFillRule(Qt.FillRule.OddEvenFill)
                    for ring in (part.exterior, *part.interiors):
                        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in ring.coords]))
                        path.closeSubpath()
                    if not visible.intersects(path.boundingRect()):
                        continue
                    pen = QPen(QColor("#ff4058"), 2)
                    pen.setCosmetic(True)
                    p.setPen(pen)
                    p.setBrush(QColor(255, 64, 88, 130))
                    p.drawPath(path)
        stones = [s for s in self.document.active if s.id != self.selected]
        if self.current():
            stones.append(self.current())
        for stone in stones:
            selected = stone.id == self.selected
            points = self.preview if selected and self.preview is not None else stone.points
            poly = QPolygonF([QPointF(*v) for v in points])
            if not visible.intersects(poly.boundingRect()):
                continue
            if selected and self.show_original:
                pen = QPen(QColor("#fa71ed"), 1.5, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPolygon(QPolygonF([QPointF(*v) for v in stone.original]))
            color = "#ffee65" if selected else ("#ffab50" if self.document.has_overlap(stone.id) else "#5aefd0")
            pen = QPen(QColor(color), 2 if selected else 1.3)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(QColor(255, 238, 101, 25) if selected else Qt.BrushStyle.NoBrush)
            p.drawPolygon(poly)
            if selected:
                for i, v in enumerate(points):
                    radius = (5 if i == self.vertex else 3.5) / self.scale
                    p.setBrush(QColor("#ff6275") if i == self.vertex else QColor("#182126"))
                    p.drawEllipse(QPointF(*v), radius, radius)

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MouseButton.MiddleButton or (self.space and event.button() == Qt.MouseButton.LeftButton):
            self.cancel_drag()
            self.pan_start = (event.position(), QPointF(self.offset))
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton or not self.document or not self.show_lines:
            return
        pos = self.to_image(event.position())
        stone = self.current()
        if stone:
            distance, index = min((math.dist(v, pos), i) for i, v in enumerate(stone.points))
            if distance * self.scale <= 9:
                self.vertex = index
                self.preview = list(stone.points)
                self.selectionChanged.emit()
                self.update()
                return
        self.vertex = None
        hits = []
        for candidate in self.document.active:
            distance, _, _ = nearest_segment(candidate.points, pos)
            inside = QPolygonF([QPointF(*v) for v in candidate.points]).containsPoint(QPointF(*pos), Qt.FillRule.OddEvenFill)
            if distance * self.scale <= 8 or inside:
                hits.append((0 if distance * self.scale <= 8 else 1, distance, candidate.id))
        self.select(min(hits)[2] if hits else None)

    def mouseMoveEvent(self, event):
        if self.pan_start:
            start, offset = self.pan_start
            self.offset = offset + event.position() - start
            self.update()
        elif self.preview is not None and self.vertex is not None:
            x, y = self.to_image(event.position())
            self.preview[self.vertex] = (max(0, min(self.document.width, x)), max(0, min(self.document.height, y)))
            self.update()

    def mouseReleaseEvent(self, event):
        if self.pan_start:
            self.pan_start = None
            self.unsetCursor()
        elif event.button() == Qt.MouseButton.LeftButton and self.preview is not None:
            points = self.preview
            self.preview = None
            self.apply_points(points, "정점 이동")

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.show_lines or self.space:
            return
        stone = self.current()
        self.cancel_drag()
        if stone is None:
            return
        distance, index, point = nearest_segment(stone.points, self.to_image(event.position()))
        if distance * self.scale <= 12:
            points = list(stone.points)
            points.insert(index + 1, point)
            if self.apply_points(points, "정점 추가"):
                self.vertex = index + 1
                self.selectionChanged.emit()
                self.update()
        else:
            self.notice.emit("선 위를 더블클릭하면 정점을 추가합니다.")

    def apply_points(self, points, label):
        if self.current() is None:
            return False
        try:
            changed = self.document.change(self.selected, points=points, label=label)
        except ValueError as exc:
            self.notice.emit(str(exc))
            self.update()
            return False
        if changed:
            self.edited.emit()
        self.update()
        return changed

    def delete_vertex(self):
        self.cancel_drag()
        stone = self.current()
        if stone is not None and self.vertex is not None:
            points = list(stone.points)
            del points[self.vertex]
            self.vertex = None
            self.apply_points(points, "정점 삭제")
            self.selectionChanged.emit()

    def delete_stone(self):
        self.cancel_drag()
        if self.current():
            self.document.change(self.selected, deleted=True, label="돌 삭제")
            self.selected, self.vertex = None, None
            self.edited.emit()
            self.selectionChanged.emit()
            self.update()

    def wheelEvent(self, event):
        if self.document is None:
            return
        self.cancel_drag()
        pos = event.position()
        x, y = self.to_image(pos)
        minimum = min(self.width() / self.document.width, self.height() / self.document.height) / 4
        self.scale = max(minimum, min(10.0, self.scale * 1.2 ** (event.angleDelta().y() / 120)))
        self.offset = QPointF(pos.x() - x * self.scale, pos.y() - y * self.scale)
        self.zoomChanged.emit(self.scale)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_Escape:
            self.cancel_drag()
            self.vertex = None
            self.selectionChanged.emit()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space = False
            self.unsetCursor()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.space = False
        self.cancel_drag()
        self.unsetCursor()
        super().focusOutEvent(event)
