from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QAction, QImage, QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QLabel, QListWidget, QMainWindow,
                             QMessageBox, QSizePolicy, QSplitter, QStackedWidget, QToolBar, QVBoxLayout, QWidget)

from .canvas import Canvas
from .model import Document
from .start_page import NewProjectDialog, RecentProjects, StartPage


class EditorWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.document = None
        self.recents = RecentProjects(settings)
        self.resize(1440, 900)
        self.setWindowTitle("Wall2CAD · 윤곽 편집기")
        self.canvas = Canvas()
        self.list = QListWidget()
        self.list.setMinimumWidth(190)
        self.list.itemSelectionChanged.connect(self.select_from_list)
        self.list.itemDoubleClicked.connect(lambda item: self.canvas.focus_stone(item.data(Qt.ItemDataRole.UserRole)))
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        heading = QLabel("돌 윤곽")
        heading.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px 0;")
        side.addWidget(heading)
        self.count = QLabel("사진 · 윤곽을 불러오세요")
        side.addWidget(self.count)
        search_hint = QLabel("클릭: 선택 · 더블클릭: 확대\n주황: 겹친 돌 · 빨강: 겹친 영역\n●: 수정됨 · 편집 후 겹침 갱신")
        search_hint.setStyleSheet("color: #647581; padding-bottom: 8px;")
        side.addWidget(search_hint)
        side.addWidget(self.list)
        self.detail = QLabel("선택한 돌 없음")
        self.detail.setWordWrap(True)
        side.addWidget(self.detail)
        side.addWidget(QLabel("좌표: 원본 사진 픽셀\nDXF: 단위 없음 · 닫힌 선"))
        splitter = QSplitter()
        splitter.addWidget(sidebar)
        splitter.addWidget(self.canvas)
        splitter.setSizes([230, 1210])
        splitter.setStretchFactor(1, 1)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter, 1)
        hint = QLabel("  돌 클릭 → 정점 드래그  |  선 더블클릭: 점 추가  |  Delete: 선택 정점 삭제  |  휠: 확대  |  Space+드래그 / 가운데 버튼: 이동  |  Esc: 이동 취소")
        hint.setWordWrap(True)
        hint.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        hint.setStyleSheet("padding: 9px; background: #e8eef1; color: #294251;")
        layout.addWidget(hint)
        self.editor_page = central
        self.start_page = StartPage(self.recents)
        self.start_page.newRequested.connect(self.open_candidates)
        self.start_page.openRequested.connect(self.open_project)
        self.start_page.recentRequested.connect(self.open_project_path)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.start_page)
        self.pages.addWidget(self.editor_page)
        self.setCentralWidget(self.pages)
        self.zoom_label = QLabel("100%")
        self.statusBar().addPermanentWidget(self.zoom_label)
        self.canvas.zoomChanged.connect(lambda scale: self.zoom_label.setText(f"{scale * 100:.1f}%"))
        self.canvas.selectionChanged.connect(self.sync_selection)
        self.canvas.edited.connect(self.refresh)
        self.canvas.notice.connect(lambda message: self.statusBar().showMessage(message, 10000))

        files = self.menuBar().addMenu("파일")
        edit = self.menuBar().addMenu("편집")
        view = self.menuBar().addMenu("보기")
        top = QToolBar("파일")
        top.setMovable(False)
        self.addToolBar(top)

        def action(label, callback, menu, toolbar=None, shortcut=None):
            result = QAction(label, self)
            result.triggered.connect(callback)
            if shortcut:
                result.setShortcut(shortcut)
            menu.addAction(result)
            if toolbar:
                toolbar.addAction(result)
            return result

        action("새 프로젝트", self.open_candidates, files, top, QKeySequence.StandardKey.New)
        action("프로젝트 열기", self.open_project, files, top, QKeySequence.StandardKey.Open)
        self.home_action = action("프로젝트 닫기 · 시작 화면", self.go_home, files, top)
        self.save_action = action("저장", self.save_project, files, top, QKeySequence.StandardKey.Save)
        self.save_as_action = action("다른 이름으로 저장", lambda: self.save_project(save_as=True), files, shortcut=QKeySequence.StandardKey.SaveAs)
        top.addSeparator()
        self.export_action = action("DXF 내보내기", self.export_dxf, files, top)
        self.addToolBarBreak()
        edits = QToolBar("윤곽 편집")
        edits.setMovable(False)
        self.addToolBar(edits)
        self.editor_toolbars = (top, edits)
        self.undo_action = action("실행 취소", self.undo, edit, edits, QKeySequence.StandardKey.Undo)
        self.redo_action = action("다시 실행", self.redo, edit, edits, QKeySequence.StandardKey.Redo)
        edits.addSeparator()
        self.delete_vertex_action = action("정점 삭제", self.canvas.delete_vertex, edit, edits, QKeySequence("Delete"))
        self.delete_vertex_action.setShortcuts([QKeySequence("Delete"), QKeySequence("Backspace")])
        self.delete_stone_action = action("돌 삭제", self.canvas.delete_stone, edit, edits)
        edits.addSeparator()
        action("전체 보기", self.canvas.fit, view, edits, QKeySequence("F"))
        for label, field, default in [("사진", "show_image", True), ("윤곽", "show_lines", True), ("겹친 영역", "show_overlaps", True), ("선택 돌 원본 비교", "show_original", False)]:
            box = QCheckBox(label)
            box.setChecked(default)
            box.setStyleSheet("padding: 0 8px;")
            box.toggled.connect(lambda checked, name=field: self.toggle_view(name, checked))
            edits.addWidget(box)
        self.refresh()

    def toggle_view(self, field, checked):
        self.canvas.cancel_drag()
        setattr(self.canvas, field, checked)
        self.canvas.update()

    def error(self, exc):
        QMessageBox.warning(self, "작업을 완료하지 못했습니다", str(exc))

    def attach(self, document):
        image = QImage(str(document.image_path))
        if image.isNull() or (image.width(), image.height()) != (document.width, document.height):
            raise ValueError("사진을 읽을 수 없거나 프로젝트의 사진 크기와 다릅니다.")
        self.document = document
        self.canvas.set_document(document, image)
        self.pages.setCurrentWidget(self.editor_page)
        if document.path:
            self.recents.remember(document.path)
        self.refresh()
        QTimer.singleShot(0, self.canvas.fit)

    def load_candidates(self, image_path, candidates_path):
        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError("사진을 읽을 수 없습니다.")
        self.attach(Document.from_candidates(image_path, image.width(), image.height(), candidates_path))

    def may_discard(self):
        if not self.document or not self.document.dirty:
            return True
        result = QMessageBox.question(self, "편집 내용 저장", "저장하지 않은 작업이 있습니다. 저장할까요?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Save)
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        return result == QMessageBox.StandardButton.Discard

    def open_candidates(self):
        if not self.may_discard():
            return
        dialog = NewProjectDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.load_candidates(dialog.image_path.text().strip(), dialog.contours_path.text().strip())
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.error(exc)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "편집 프로젝트 열기", "", "Wall2CAD (*.wall2cad.json);;JSON (*.json)")
        if path:
            self.open_project_path(path)

    def open_project_path(self, path):
        if not self.may_discard():
            return
        if not Path(path).is_file():
            self.error("프로젝트 파일을 찾을 수 없습니다. ‘프로젝트 열기’에서 이동한 파일을 선택하세요.\n" + str(path))
            return
        try:
            try:
                document = Document.load(path)
            except FileNotFoundError:
                image, _ = QFileDialog.getOpenFileName(self, "이동된 원본 사진 찾기 (동일한 파일)", str(Path(path).parent), "사진 (*.jpeg *.jpg *.png *.tif *.tiff *.bmp)")
                if not image:
                    return
                document = Document.load(path, image_override=image)
                document.clean_cursor = -1  # Persist the newly resolved photo location.
            self.attach(document)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.error(exc)

    def go_home(self):
        if not self.may_discard():
            return
        self.canvas.cancel_drag()
        self.document = None
        self.canvas.set_document(None, None)
        self.pages.setCurrentWidget(self.start_page)
        self.start_page.reload()
        self.statusBar().clearMessage()
        self.refresh()

    def save_project(self, checked=False, *, save_as=False):
        if not self.document:
            return False
        path = self.document.path
        if save_as or path is None:
            suggested = path or self.document.image_path.with_suffix(".wall2cad.json")
            name, _ = QFileDialog.getSaveFileName(self, "편집 프로젝트 저장", str(suggested), "Wall2CAD (*.wall2cad.json)")
            if not name:
                return False
            path = Path(name)
            if not str(path).endswith(".wall2cad.json"):
                path = Path(str(path) + ".wall2cad.json")
                if path.exists() and QMessageBox.question(self, "덮어쓰기", f"{path.name} 파일을 덮어쓸까요?") != QMessageBox.StandardButton.Yes:
                    return False
        try:
            self.document.save(path)
            self.recents.remember(path)
            self.refresh()
            self.statusBar().showMessage(f"프로젝트 저장: {path}", 10000)
            return True
        except (OSError, ValueError) as exc:
            self.error(exc)
            return False

    def export_dxf(self):
        if not self.document:
            return
        base = self.document.path or self.document.image_path
        suggested = base.parent / (base.name.split(".")[0] + "_edited.dxf")
        name, _ = QFileDialog.getSaveFileName(self, "수정한 윤곽 DXF 저장", str(suggested), "DXF (*.dxf)")
        if not name:
            return
        path = Path(name)
        if path.suffix.lower() != ".dxf":
            path = Path(str(path) + ".dxf")
            if path.exists() and QMessageBox.question(self, "덮어쓰기", f"{path.name} 파일을 덮어쓸까요?") != QMessageBox.StandardButton.Yes:
                return
        try:
            self.document.export_dxf(path)
            self.statusBar().showMessage(f"DXF 저장 완료: {len(self.document.active)}개 닫힌 선 · 픽셀 좌표 · {path}", 15000)
        except (OSError, ValueError) as exc:
            self.error(exc)

    def undo(self):
        if self.document:
            self.canvas.select(self.document.undo())
            self.refresh()

    def redo(self):
        if self.document:
            self.canvas.select(self.document.redo())
            self.refresh()

    def select_from_list(self):
        items = self.list.selectedItems()
        if items:
            self.canvas.select(items[0].data(Qt.ItemDataRole.UserRole))

    def sync_selection(self):
        stone = self.canvas.current()
        self.list.blockSignals(True)
        self.list.clearSelection()
        for i in range(self.list.count()):
            item = self.list.item(i)
            if stone and item.data(Qt.ItemDataRole.UserRole) == stone.id:
                item.setSelected(True)
                self.list.scrollToItem(item)
        self.list.blockSignals(False)
        vertex = self.canvas.vertex
        self.detail.setText(f"{stone.id} · 정점 {len(stone.points)}개" + (f"\n선택 정점: {vertex + 1}" if vertex is not None else "") if stone else "선택한 돌 없음")
        if stone:
            others = sorted(self.document.overlaps.get(stone.id, ()))
            self.detail.setText(self.detail.text() + "\n겹침: " + (", ".join(others) if others else "없음"))
        self.delete_vertex_action.setEnabled(stone is not None and vertex is not None)
        self.delete_stone_action.setEnabled(stone is not None)

    def refresh(self):
        doc = self.document
        for toolbar in self.editor_toolbars:
            toolbar.setVisible(doc is not None)
        self.zoom_label.setVisible(doc is not None)
        self.home_action.setEnabled(doc is not None)
        self.list.blockSignals(True)
        scroll = self.list.verticalScrollBar().value()
        self.list.clear()
        if doc:
            for stone in doc.active:
                edited = " ●" if stone.points != stone.original else ""
                neighbors = sorted(doc.overlaps.get(stone.id, ()))
                overlap = f" · 겹침 {len(neighbors)}" if neighbors else ""
                self.list.addItem(stone.id + edited + overlap)
                item = self.list.item(self.list.count() - 1)
                item.setData(Qt.ItemDataRole.UserRole, stone.id)
                item.setToolTip("겹침: " + (", ".join(neighbors) if neighbors else "없음"))
            self.count.setText(f"남은 돌 {len(doc.active)} / {len(doc.stones)}\n겹친 돌 {sum(bool(v) for v in doc.overlaps.values())} · {len(doc.overlap_regions)}쌍")
        self.list.verticalScrollBar().setValue(scroll)
        self.list.blockSignals(False)
        for action in (self.save_action, self.save_as_action, self.export_action):
            action.setEnabled(doc is not None)
        self.undo_action.setEnabled(doc is not None and doc.cursor > 0)
        self.redo_action.setEnabled(doc is not None and doc.cursor < len(doc.history))
        name = (doc.path.name if doc.path else "새 편집 프로젝트") if doc else "시작"
        self.setWindowTitle(f"{'* ' if doc and doc.dirty else ''}{name} — Wall2CAD")
        self.sync_selection()
        self.canvas.update()

    def closeEvent(self, event):
        if self.may_discard():
            event.accept()
        else:
            event.ignore()
