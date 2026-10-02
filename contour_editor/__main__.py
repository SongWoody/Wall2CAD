import argparse
from pathlib import Path
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from .model import Document
from .window import EditorWindow


def main():
    parser = argparse.ArgumentParser(description="Wall2CAD 돌 윤곽 편집기 (추론 없이 저장된 좌표 편집)")
    parser.add_argument("project", nargs="?", type=Path, help="저장한 .wall2cad.json")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--contours", type=Path)
    parser.add_argument("--sample", action="store_true", help="저장소 밖 building_001 합격 기준본 열기")
    args = parser.parse_args()
    if sum([bool(args.project), args.sample, bool(args.image or args.contours)]) > 1:
        parser.error("project, --sample, --image/--contours 중 하나를 선택하세요.")
    if bool(args.image) != bool(args.contours):
        parser.error("--image와 --contours를 함께 지정하세요.")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Wall2CAD Contour Editor")
    app.setStyle("Fusion")
    window = EditorWindow()
    try:
        if args.sample:
            workspace = Path(__file__).resolve().parents[2]
            window.load_candidates(workspace / "inputoutput/building_001_input.jpeg",
                                   workspace / "docs/baselines/building_001_v1/candidates.json")
        elif args.image:
            window.load_candidates(args.image, args.contours)
        elif args.project:
            window.attach(Document.load(args.project))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        QMessageBox.critical(window, "불러오기 실패", str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
