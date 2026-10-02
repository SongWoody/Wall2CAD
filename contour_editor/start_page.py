"""Start page and device-local recently opened project paths."""
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QPushButton, QVBoxLayout, QWidget)


class RecentProjects:
    def __init__(self, settings=None):
        self.settings = settings if settings is not None else QSettings("Wall2CAD", "ContourEditor")

    def paths(self):
        value = self.settings.value("recentProjects", [])
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return list(dict.fromkeys(p for p in value if isinstance(p, str) and p))[:10]

    def remember(self, path):
        path = str(Path(path).resolve())
        self.settings.setValue("recentProjects", [path, *[p for p in self.paths() if p != path]][:10])
        self.settings.sync()

    def clear(self):
        self.settings.remove("recentProjects")
        self.settings.sync()


class StartPage(QWidget):
    newRequested = pyqtSignal()
    openRequested = pyqtSignal()
    recentRequested = pyqtSignal(str)

    def __init__(self, recents, parent=None):
        super().__init__(parent)
        self.recents = recents
        self.setObjectName("startPage")
        self.setStyleSheet("""
            QWidget#startPage { background: #f3f6f8; color: #20313c; }
            QLabel { color: #20313c; }
            QPushButton { padding: 12px 22px; border: 1px solid #cbd6dd;
                          border-radius: 6px; background: white; color: #20313c; }
            QPushButton:hover { background: #e7eff3; }
            QPushButton#primary { background: #176b66; color: white; border-color: #176b66; }
            QPushButton#primary:hover { background: #12544f; }
            QPushButton:disabled { color: #8c9ba5; background: #e9eef1; }
            QListWidget { background: white; color: #20313c; border: 1px solid #d4dfe5;
                          border-radius: 6px; padding: 6px; }
            QListWidget::item { padding: 12px; }
            QListWidget::item:selected { background: #dbeeea; color: #164e49; }
        """)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()
        content = QWidget()
        content.setMaximumWidth(850)
        layout = QVBoxLayout(content)
        layout.addStretch(1)
        brand = QLabel("WALL2CAD")
        brand.setStyleSheet("color: #176b66; font-size: 15px; font-weight: bold;")
        layout.addWidget(brand)
        title = QLabel("돌 윤곽 작업을 시작하세요")
        title.setStyleSheet("font-size: 30px; font-weight: bold; margin-top: 12px;")
        layout.addWidget(title)
        subtitle = QLabel("사진과 윤곽으로 새 작업을 만들거나, 저장한 프로젝트를 이어서 편집하세요.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #586c79; font-size: 15px; margin: 8px 0 22px;")
        layout.addWidget(subtitle)
        actions = QHBoxLayout()
        self.new_button = QPushButton("새 프로젝트 만들기")
        self.new_button.setObjectName("primary")
        self.new_button.clicked.connect(self.newRequested.emit)
        self.open_button = QPushButton("프로젝트 열기…")
        self.open_button.clicked.connect(self.openRequested.emit)
        actions.addWidget(self.new_button)
        actions.addWidget(self.open_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addSpacing(28)
        heading = QLabel("최근 프로젝트")
        heading.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(heading)
        self.empty = QLabel("아직 저장하거나 연 프로젝트가 없습니다.\n새 프로젝트를 만들거나 다른 PC에서 가져온 프로젝트를 여세요.")
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet("color: #586c79; padding: 24px 0;")
        layout.addWidget(self.empty)
        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        self.list.setMaximumHeight(350)
        self.list.itemActivated.connect(lambda item: self.recentRequested.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.list.itemSelectionChanged.connect(self.update_open_button)
        layout.addWidget(self.list)
        recent_actions = QHBoxLayout()
        self.recent_open = QPushButton("선택한 프로젝트 열기")
        self.recent_open.clicked.connect(self.open_selected)
        self.clear_button = QPushButton("목록 비우기")
        self.clear_button.setToolTip("최근 목록만 지웁니다. 프로젝트 파일은 유지됩니다.")
        self.clear_button.clicked.connect(self.clear_recent)
        recent_actions.addWidget(self.recent_open)
        recent_actions.addStretch()
        recent_actions.addWidget(self.clear_button)
        layout.addLayout(recent_actions)
        layout.addStretch(1)
        outer.addWidget(content, 1)
        outer.addStretch()
        self.reload()

    def update_open_button(self):
        self.recent_open.setEnabled(bool(self.list.selectedItems()))

    def open_selected(self):
        item = self.list.currentItem()
        if item:
            self.recentRequested.emit(item.data(Qt.ItemDataRole.UserRole))

    def clear_recent(self):
        self.recents.clear()
        self.reload()

    def reload(self):
        self.list.clear()
        for path in self.recents.paths():
            file = Path(path)
            title = file.name.removesuffix(".wall2cad.json")
            missing = " · 파일을 찾을 수 없음" if not file.is_file() else ""
            item = QListWidgetItem(f"{title}{missing}\n{file}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self.list.addItem(item)
        has_recent = self.list.count() > 0
        self.list.setVisible(has_recent)
        self.empty.setVisible(not has_recent)
        self.recent_open.setVisible(has_recent)
        self.clear_button.setVisible(has_recent)
        self.update_open_button()


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 프로젝트 만들기")
        self.resize(620, 300)
        layout = QVBoxLayout(self)
        intro = QLabel("편집할 사진과 추출된 돌 윤곽을 선택하세요.\n현재 버전은 저장된 윤곽을 편집하며, 사진에서 자동 추출하는 기능은 아직 연결되지 않았습니다.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.image_path = QLineEdit()
        self.contours_path = QLineEdit()
        self.image_path.setPlaceholderText("현장 사진 파일")
        self.contours_path.setPlaceholderText("추출한 돌 윤곽 JSON 파일")
        for label, field, file_filter in (
            ("사진", self.image_path, "사진 (*.jpeg *.jpg *.png *.tif *.tiff *.bmp)"),
            ("돌 윤곽", self.contours_path, "윤곽 JSON (*.json)"),
        ):
            layout.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            button = QPushButton("파일 선택…")
            button.clicked.connect(lambda checked=False, target=field, pattern=file_filter: self.browse(target, pattern))
            row.addWidget(button)
            layout.addLayout(row)
            field.textChanged.connect(self.update_create_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.create_button = buttons.addButton("프로젝트 만들기", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(12)
        layout.addWidget(buttons)
        self.update_create_button()

    def browse(self, field, file_filter):
        selected, _ = QFileDialog.getOpenFileName(self, "파일 선택", field.text() or self.image_path.text(), file_filter)
        if selected:
            field.setText(selected)

    def update_create_button(self):
        self.create_button.setEnabled(all(Path(field.text().strip()).is_file()
                                          for field in (self.image_path, self.contours_path)))
