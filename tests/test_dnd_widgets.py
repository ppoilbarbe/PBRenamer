"""Tests for the drag-and-drop-enabled tree/list widgets."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QTreeWidgetItem

from pbrenamer.ui.dnd_widgets import DirectoryTreeView, FileListWidget


class _FakeIndex:
    """Stand-in for QModelIndex — avoids exercising QFileSystemModel's
    background-thread population, which segfaults when queried without a
    running event loop pumping it (as in these synchronous widget tests)."""

    def __init__(self, valid: bool = True) -> None:
        self._valid = valid

    def isValid(self) -> bool:  # noqa: N802
        return self._valid


class _FakeFsModel:
    """Minimal stand-in exposing only the QFileSystemModel API dropEvent/
    startDrag use."""

    def __init__(self, mapping: dict, mime: QMimeData | None = None) -> None:
        self._mapping = mapping
        self._mime = mime

    def filePath(self, idx) -> str:  # noqa: N802
        return self._mapping[idx]

    def mimeData(self, indexes) -> QMimeData | None:  # noqa: N802
        return self._mime


class _FakeDrag:
    """Records constructor/method calls in place of a real QDrag, whose
    .exec() would start a real (blocking) native drag-and-drop loop."""

    instances: list[_FakeDrag] = []

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.mime_data = None
        self.exec_args = None
        _FakeDrag.instances.append(self)

    def setMimeData(self, mime) -> None:  # noqa: N802
        self.mime_data = mime

    def exec(self, supported_actions, default_action):
        self.exec_args = (supported_actions, default_action)
        return Qt.DropAction.IgnoreAction


def _drop_event(paths: list[str], action=Qt.DropAction.MoveAction) -> QDropEvent:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    event = QDropEvent(
        QPointF(0, 0),
        action,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # QDropEvent does not itself hold a Python reference to `mime` — keep one
    # alive on the event object, otherwise it can be garbage-collected before
    # dropEvent() reads it back via event.mimeData(), causing a segfault.
    event._mime_keepalive = mime
    return event


def _no_url_event() -> QDropEvent:
    mime = QMimeData()
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    event._mime_keepalive = mime
    return event


def _remote_url_event() -> QDropEvent:
    """A drop carrying URLs, but none of them a local file (e.g. a web link)."""
    mime = QMimeData()
    mime.setUrls([QUrl("http://example.com/file.txt")])
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    event._mime_keepalive = mime
    return event


# ---------------------------------------------------------------------------
# DirectoryTreeView
# ---------------------------------------------------------------------------


class TestDirectoryTreeView:
    def _make_view(self, qtbot):
        view = DirectoryTreeView()
        qtbot.addWidget(view)
        return view

    def test_drop_on_valid_directory_emits_signal(self, qtbot, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        src = tmp_path / "file.txt"
        src.write_text("x")
        view = self._make_view(qtbot)
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({idx: str(sub)})
        view.indexAt = lambda pos: idx

        received = []
        view.files_dropped.connect(lambda *args: received.append(args))
        event = _drop_event([str(src)])
        view.dropEvent(event)

        assert event.isAccepted()
        assert received == [([str(src)], str(sub), True)]

    def test_drop_with_copy_action(self, qtbot, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        src = tmp_path / "file.txt"
        src.write_text("x")
        view = self._make_view(qtbot)
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({idx: str(sub)})
        view.indexAt = lambda pos: idx

        received = []
        view.files_dropped.connect(lambda *args: received.append(args))
        view.dropEvent(_drop_event([str(src)], action=Qt.DropAction.CopyAction))

        assert received == [([str(src)], str(sub), False)]

    def test_drop_on_invalid_index_ignored(self, qtbot, tmp_path):
        view = self._make_view(qtbot)
        view.indexAt = lambda pos: _FakeIndex(valid=False)

        received = []
        view.files_dropped.connect(lambda *args: received.append(args))
        event = _drop_event([str(tmp_path / "file.txt")])
        view.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drop_without_urls_ignored(self, qtbot, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        view = self._make_view(qtbot)
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({idx: str(sub)})
        view.indexAt = lambda pos: idx

        received = []
        view.files_dropped.connect(lambda *args: received.append(args))
        event = _no_url_event()
        view.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drop_with_no_local_paths_ignored(self, qtbot, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        view = self._make_view(qtbot)
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({idx: str(sub)})
        view.indexAt = lambda pos: idx

        received = []
        view.files_dropped.connect(lambda *args: received.append(args))
        event = _remote_url_event()
        view.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drag_enter_requires_urls(self, qtbot):
        view = self._make_view(qtbot)
        event = _no_url_event()
        view.dragEnterEvent(event)
        assert not event.isAccepted()

    def test_drag_enter_accepts_urls(self, qtbot):
        view = self._make_view(qtbot)
        event = _drop_event(["/tmp/whatever"])
        view.dragEnterEvent(event)
        assert event.isAccepted()

    def test_drag_move_accepts_valid_index_with_urls(self, qtbot):
        view = self._make_view(qtbot)
        view.indexAt = lambda pos: _FakeIndex()
        event = _drop_event(["/tmp/whatever"])
        view.dragMoveEvent(event)
        assert event.isAccepted()

    def test_drag_move_rejects_invalid_index(self, qtbot):
        view = self._make_view(qtbot)
        view.indexAt = lambda pos: _FakeIndex(valid=False)
        event = _drop_event(["/tmp/whatever"])
        view.dragMoveEvent(event)
        assert not event.isAccepted()

    def test_drag_move_rejects_no_urls(self, qtbot):
        view = self._make_view(qtbot)
        view.indexAt = lambda pos: _FakeIndex()
        event = _no_url_event()
        view.dragMoveEvent(event)
        assert not event.isAccepted()

    def test_start_drag_sets_cursors_and_execs(self, qtbot, tmp_path, monkeypatch):
        import pbrenamer.ui.dnd_widgets as _dndmod

        _FakeDrag.instances.clear()
        monkeypatch.setattr(_dndmod, "QDrag", _FakeDrag)
        cursor_calls = []
        monkeypatch.setattr(
            _dndmod, "set_drag_cursors", lambda drag: cursor_calls.append(drag)
        )

        view = self._make_view(qtbot)
        mime = QMimeData()
        f = tmp_path / "a.txt"
        f.write_text("x")
        mime.setUrls([QUrl.fromLocalFile(str(f))])
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({idx: str(tmp_path)}, mime=mime)
        view.selectedIndexes = lambda: [idx]

        view.startDrag(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        assert len(_FakeDrag.instances) == 1
        drag = _FakeDrag.instances[0]
        assert drag.mime_data is mime
        assert cursor_calls == [drag]
        assert drag.exec_args == (
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            view.defaultDropAction(),
        )

    def test_start_drag_noop_without_selection(self, qtbot, monkeypatch):
        import pbrenamer.ui.dnd_widgets as _dndmod

        _FakeDrag.instances.clear()
        monkeypatch.setattr(_dndmod, "QDrag", _FakeDrag)

        view = self._make_view(qtbot)
        view.selectedIndexes = lambda: []
        view.startDrag(Qt.DropAction.MoveAction)

        assert _FakeDrag.instances == []

    def test_start_drag_noop_when_model_mime_data_is_none(self, qtbot, monkeypatch):
        import pbrenamer.ui.dnd_widgets as _dndmod

        _FakeDrag.instances.clear()
        monkeypatch.setattr(_dndmod, "QDrag", _FakeDrag)

        view = self._make_view(qtbot)
        idx = _FakeIndex()
        view.model = lambda: _FakeFsModel({}, mime=None)
        view.selectedIndexes = lambda: [idx]
        view.startDrag(Qt.DropAction.MoveAction)

        assert _FakeDrag.instances == []


# ---------------------------------------------------------------------------
# FileListWidget
# ---------------------------------------------------------------------------


class TestFileListWidget:
    def _make_widget(self, qtbot, current_dir: str | None = None):
        widget = FileListWidget()
        qtbot.addWidget(widget)
        widget.current_dir_getter = (lambda: current_dir) if current_dir else None
        return widget

    def _add_item(self, widget, path: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([path, ""])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        widget.addTopLevelItem(item)
        return item

    def test_mime_data_contains_real_file_urls(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot)
        f = tmp_path / "a.txt"
        f.write_text("x")
        item = self._add_item(widget, str(f))
        mime = widget.mimeData([item])
        assert mime.hasUrls()
        assert mime.urls()[0].toLocalFile() == str(f)

    def test_drop_on_directory_row_targets_that_directory(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot, current_dir=str(tmp_path))
        sub = tmp_path / "sub"
        sub.mkdir()
        dir_item = self._add_item(widget, str(sub))
        widget.itemAt = lambda pos: dir_item
        widget.dropIndicatorPosition = lambda: (
            QAbstractItemView.DropIndicatorPosition.OnItem
        )

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        src = tmp_path / "file.txt"
        src.write_text("x")
        event = _drop_event([str(src)])
        widget.dropEvent(event)

        assert event.isAccepted()
        assert received == [([str(src)], str(sub), True)]

    def test_drop_on_file_row_targets_its_parent_directory(self, qtbot, tmp_path):
        nested = tmp_path / "nested"
        nested.mkdir()
        neighbour = nested / "neighbour.txt"
        neighbour.write_text("x")
        widget = self._make_widget(qtbot, current_dir=str(tmp_path))
        file_item = self._add_item(widget, str(neighbour))
        widget.itemAt = lambda pos: file_item
        widget.dropIndicatorPosition = lambda: (
            QAbstractItemView.DropIndicatorPosition.OnItem
        )

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        src = tmp_path / "file.txt"
        src.write_text("x")
        widget.dropEvent(_drop_event([str(src)]))

        assert received == [([str(src)], str(nested), True)]

    def test_drop_on_blank_space_uses_current_dir(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot, current_dir=str(tmp_path))
        widget.itemAt = lambda pos: None

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        src = tmp_path / "file.txt"
        src.write_text("x")
        widget.dropEvent(_drop_event([str(src)]))

        assert received == [([str(src)], str(tmp_path), True)]

    def test_drop_without_current_dir_getter_ignored(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot)  # no current_dir_getter set
        widget.itemAt = lambda pos: None

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        event = _drop_event([str(tmp_path / "file.txt")])
        widget.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drop_without_urls_ignored(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot, current_dir=str(tmp_path))
        widget.itemAt = lambda pos: None

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        event = _no_url_event()
        widget.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drop_with_no_local_paths_ignored(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot, current_dir=str(tmp_path))
        widget.itemAt = lambda pos: None

        received = []
        widget.files_dropped.connect(lambda *args: received.append(args))
        event = _remote_url_event()
        widget.dropEvent(event)

        assert not event.isAccepted()
        assert received == []

    def test_drag_enter_accepts_urls(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot)
        event = _drop_event([str(tmp_path / "file.txt")])
        widget.dragEnterEvent(event)
        assert event.isAccepted()

    def test_drag_enter_requires_urls(self, qtbot):
        widget = self._make_widget(qtbot)
        event = _no_url_event()
        widget.dragEnterEvent(event)
        assert not event.isAccepted()

    def test_drag_move_accepts_urls(self, qtbot, tmp_path):
        widget = self._make_widget(qtbot)
        event = _drop_event([str(tmp_path / "file.txt")])
        widget.dragMoveEvent(event)
        assert event.isAccepted()

    def test_drag_move_rejects_no_urls(self, qtbot):
        widget = self._make_widget(qtbot)
        event = _no_url_event()
        widget.dragMoveEvent(event)
        assert not event.isAccepted()

    def test_start_drag_sets_cursors_and_execs(self, qtbot, tmp_path, monkeypatch):
        import pbrenamer.ui.dnd_widgets as _dndmod

        _FakeDrag.instances.clear()
        monkeypatch.setattr(_dndmod, "QDrag", _FakeDrag)
        cursor_calls = []
        monkeypatch.setattr(
            _dndmod, "set_drag_cursors", lambda drag: cursor_calls.append(drag)
        )

        widget = self._make_widget(qtbot)
        f = tmp_path / "a.txt"
        f.write_text("x")
        item = self._add_item(widget, str(f))
        item.setSelected(True)

        widget.startDrag(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

        assert len(_FakeDrag.instances) == 1
        drag = _FakeDrag.instances[0]
        assert drag.mime_data.urls()[0].toLocalFile() == str(f)
        assert cursor_calls == [drag]
        assert drag.exec_args == (
            Qt.DropAction.CopyAction | Qt.DropAction.MoveAction,
            widget.defaultDropAction(),
        )

    def test_start_drag_noop_without_selection(self, qtbot, monkeypatch):
        import pbrenamer.ui.dnd_widgets as _dndmod

        _FakeDrag.instances.clear()
        monkeypatch.setattr(_dndmod, "QDrag", _FakeDrag)

        widget = self._make_widget(qtbot)
        widget.startDrag(Qt.DropAction.MoveAction)

        assert _FakeDrag.instances == []
