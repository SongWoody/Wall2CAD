"""Editable vectors, geometry checks, history and portable project persistence.

Coordinates always remain in original image pixels (origin at top left).
The image and imported candidate file are read-only source assets.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

Point = tuple[float, float]
Points = tuple[Point, ...]


def points_from(value) -> Points:
    try:
        result = tuple((float(x), float(y)) for x, y in value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("좌표는 [x, y] 쌍이어야 합니다.") from exc
    if len(result) > 1 and result[0] == result[-1]:
        result = result[:-1]
    return result


def cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def on_segment(a, b, p):
    return (abs(cross(a, b, p)) <= 1e-8
            and min(a[0], b[0]) - 1e-8 <= p[0] <= max(a[0], b[0]) + 1e-8
            and min(a[1], b[1]) - 1e-8 <= p[1] <= max(a[1], b[1]) + 1e-8)


def intersects(a, b, c, d):
    ca, cb, cc, cd = cross(a, b, c), cross(a, b, d), cross(c, d, a), cross(c, d, b)
    return (((ca > 0 > cb or cb > 0 > ca) and (cc > 0 > cd or cd > 0 > cc))
            or on_segment(a, b, c) or on_segment(a, b, d)
            or on_segment(c, d, a) or on_segment(c, d, b))


def validate_polygon(points: Points, width: int, height: int):
    if len(points) < 3:
        raise ValueError("닫힌 돌 윤곽에는 정점이 3개 이상 필요합니다.")
    if not all(math.isfinite(x) and math.isfinite(y) for x, y in points):
        raise ValueError("유한한 좌표만 사용할 수 있습니다.")
    if not all(0 <= x <= width and 0 <= y <= height for x, y in points):
        raise ValueError("정점은 사진 범위 안에 있어야 합니다.")
    if len(set(points)) != len(points):
        raise ValueError("서로 겹치는 정점은 사용할 수 없습니다.")
    n = len(points)
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        # Adjacent edges may meet, but must not double back over one another.
        c = points[(i + 2) % n]
        if on_segment(a, b, c) or on_segment(b, c, a):
            raise ValueError("서로 겹치는 선분은 사용할 수 없습니다.")
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if intersects(a, b, points[j], points[(j + 1) % n]):
                raise ValueError("윤곽선이 자기 자신과 교차합니다. 수정 위치를 바꿔 주세요.")
    area2 = sum(points[i][0] * points[(i + 1) % n][1]
                - points[(i + 1) % n][0] * points[i][1] for i in range(n))
    if abs(area2) < 1e-6:
        raise ValueError("면적이 없는 윤곽은 사용할 수 없습니다.")


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_write(path: Path, writer):
    path = Path(path).resolve()
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    try:
        writer(Path(name))
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass
class Stone:
    id: str
    original: Points
    points: Points
    metadata: dict
    deleted: bool = False


@dataclass(frozen=True)
class Change:
    stone_id: str
    before: tuple[Points, bool]
    after: tuple[Points, bool]
    label: str


class Document:
    def __init__(self, image_path, width, height, stones, source_path=None, image_hash=None):
        self.image_path = Path(image_path).resolve()
        self.width, self.height = int(width), int(height)
        if self.width <= 0 or self.height <= 0:
            raise ValueError("사진 크기가 올바르지 않습니다.")
        self.stones = {stone.id: stone for stone in stones}
        if len(self.stones) != len(stones) or not all(self.stones):
            raise ValueError("돌 ID는 비어 있지 않고 서로 달라야 합니다.")
        for stone in stones:
            for points in (stone.original, stone.points):
                try:
                    validate_polygon(points, self.width, self.height)
                except ValueError as exc:
                    raise ValueError(f"{stone.id}: {exc}") from exc
        self.source_path = Path(source_path).resolve() if source_path else None
        self.image_hash = image_hash or file_hash(self.image_path)
        self.path: Path | None = None
        self.history: list[Change] = []
        self.cursor = 0
        self.clean_cursor = -1  # Imported candidates have not been saved as a project.

    @classmethod
    def from_candidates(cls, image_path, width, height, candidates_path):
        records = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError("후보 JSON에는 돌 목록이 필요합니다.")
        stones = []
        for record in records:
            pts = points_from(record["points"])
            metadata = deepcopy({k: v for k, v in record.items() if k not in ("id", "points")})
            stones.append(Stone(str(record["id"]), pts, pts, metadata))
        return cls(image_path, width, height, stones, candidates_path)

    @property
    def dirty(self):
        return self.cursor != self.clean_cursor

    @property
    def active(self):
        return [s for s in self.stones.values() if not s.deleted]

    def change(self, stone_id, *, points=None, deleted=None, label="윤곽 수정"):
        stone = self.stones[stone_id]
        new_points = points_from(points) if points is not None else stone.points
        new_deleted = stone.deleted if deleted is None else bool(deleted)
        validate_polygon(new_points, self.width, self.height)
        before, after = (stone.points, stone.deleted), (new_points, new_deleted)
        if before == after:
            return False
        if self.clean_cursor > self.cursor:
            self.clean_cursor = -1
        del self.history[self.cursor:]
        self.history.append(Change(stone_id, before, after, label))
        self.cursor += 1
        stone.points, stone.deleted = after
        return True

    def undo(self):
        if self.cursor == 0:
            return None
        self.cursor -= 1
        change = self.history[self.cursor]
        self.stones[change.stone_id].points, self.stones[change.stone_id].deleted = change.before
        return change.stone_id

    def redo(self):
        if self.cursor == len(self.history):
            return None
        change = self.history[self.cursor]
        self.stones[change.stone_id].points, self.stones[change.stone_id].deleted = change.after
        self.cursor += 1
        return change.stone_id

    def protect_sources(self, path):
        path = Path(path).resolve()
        if path in (self.image_path, self.source_path):
            raise ValueError("원본 사진·후보 파일에는 덮어쓸 수 없습니다.")

    def save(self, path):
        path = Path(path).resolve()
        self.protect_sources(path)
        try:
            image_ref = Path(os.path.relpath(self.image_path, path.parent)).as_posix()
        except ValueError:  # Windows: image and project on different drives.
            image_ref = str(self.image_path)
        data = {
            "format": "wall2cad-contours", "version": 1,
            "coordinates": "image-pixels-top-left",
            "image": {"path": image_ref, "width": self.width, "height": self.height,
                      "sha256": self.image_hash},
            "source_candidates": str(self.source_path) if self.source_path else None,
            "stones": [{"id": s.id, "original": s.original, "points": s.points,
                        "metadata": s.metadata, "deleted": s.deleted}
                       for s in self.stones.values()],
        }
        atomic_write(path, lambda tmp: tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"))
        self.path, self.clean_cursor = path, self.cursor

    @classmethod
    def load(cls, path, image_override=None):
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        if (data.get("format") != "wall2cad-contours" or data.get("version") != 1
                or data.get("coordinates") != "image-pixels-top-left"):
            raise ValueError("지원하지 않는 편집 프로젝트 형식입니다.")
        info = data["image"]
        image_path = Path(image_override).resolve() if image_override else (path.parent / info["path"]).resolve()
        if file_hash(image_path) != info["sha256"]:
            raise ValueError("사진이 저장 당시 원본과 다릅니다. 같은 원본 사진을 선택해 주세요.")
        stones = [Stone(str(s["id"]), points_from(s["original"]), points_from(s["points"]),
                        s["metadata"], bool(s["deleted"])) for s in data["stones"]]
        document = cls(image_path, info["width"], info["height"], stones,
                       data.get("source_candidates"), info["sha256"])
        document.path, document.clean_cursor = path, 0
        return document

    def export_dxf(self, path):
        import ezdxf

        path = Path(path).resolve()
        self.protect_sources(path)
        if path == self.path:
            raise ValueError("DXF는 편집 프로젝트와 다른 파일로 저장하세요.")
        if not self.active:
            raise ValueError("출력할 돌 윤곽이 없습니다.")
        drawing = ezdxf.new("R2010")
        drawing.units = 0
        drawing.appids.new("WALL2CAD_REVIEW")
        drawing.layers.new("STONE_CANDIDATE", dxfattribs={"color": 3})
        drawing.layers.new("REVIEW_OVERLAP", dxfattribs={"color": 30})
        for stone in self.active:
            validate_polygon(stone.points, self.width, self.height)
            layer = "REVIEW_OVERLAP" if stone.metadata.get("layer") == "REVIEW_OVERLAP" else "STONE_CANDIDATE"
            entity = drawing.modelspace().add_lwpolyline(
                [(x, self.height - y) for x, y in stone.points], close=True,
                dxfattribs={"layer": layer})
            entity.set_xdata("WALL2CAD_REVIEW", [(1000, stone.id)])
        atomic_write(path, lambda tmp: drawing.saveas(tmp))
