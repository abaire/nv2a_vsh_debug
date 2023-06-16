"""Provides functionality to browse the input state."""

from typing import Dict
from typing import Optional

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.css import query
from textual.messages import Message
from textual.reactive import reactive
from textual.widgets import ContentSwitcher
from textual.widgets import DataTable
from textual.widgets import Static

from nv2adbg._error_message import _CenteredErrorMessage
from nv2adbg._shader_program import _ShaderProgram


class _ProgramVertexViewer(Static):
    """Provides a browsing interface to view and select vertices from mesh inputs."""

    DEFAULT_CSS = """
    _ProgramVertexViewer {
        height: 1fr;
        width: 1fr;
    }

    _ProgramVertexViewer DataTable {
        height: 1fr;
    }

    _ProgramVertexViewer DataTable > .datatable--hover {
        background: $background;
    }
    """

    BINDINGS = [
        ("space", "set_active_vertex", "Select active vertex"),
    ]

    _active_content = reactive("no-content", init=False)

    def __init__(self):
        super().__init__()
        self._program: Optional[_ShaderProgram] = None

        self._vertex_table = DataTable(id="content")
        self._vertex_table.add_columns(
            "Index",
            "v0",
            "v1",
            "v2",
            "v3",
            "v4",
            "v5",
            "v6",
            "v7",
            "v8",
            "v9",
            "v10",
            "v11",
            "v12",
            "v13",
            "v14",
            "v15",
        )
        self._vertex_table.cursor_type = "row"
        self._vertex_table.zebra_stripes = True

        self._row_index_to_vertex_id: Dict[int, int] = {}

    def set_program(self, program: Optional[_ShaderProgram]):
        self._program = program
        self._populate()
        self.update()

    def on_mount(self) -> None:
        self._populate()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="no-content"):
            yield self._vertex_table

            yield _CenteredErrorMessage(
                "No vertex data available, load a mesh via the File menu.",
                id="no-content",
            )

    def _action_set_active_vertex(self):
        self._vertex_table.action_select_cursor()

    def _on_data_table_row_selected(self, event: DataTable.RowSelected):
        vertex_index = self._row_index_to_vertex_id[event.cursor_row]
        if self._program.set_active_vertex_index(vertex_index):
            self.post_message(self.ActiveVertexChanged(vertex_index))

    def _populate(self):
        try:
            self._row_index_to_vertex_id.clear()
            self._vertex_table.clear()
            if not self._program or not self._program.mesh_inputs_file:
                self._active_content = "no-content"
                return

            ordered_vertices = self._program.get_deduped_ordered_vertices()

            for row, vertex in enumerate(ordered_vertices):
                self._row_index_to_vertex_id[row] = int(vertex["VTX"])
                self._vertex_table.add_row(
                    vertex["IDX"],
                    *[_render_vertex(vertex, f"v{idx}") for idx in range(0, 16)],
                )

            self._active_content = "content"

        except query.NoMatches:
            # The table is not loaded yet.
            pass

    def _watch__active_content(self, _old_val: str, new_val: str):
        del _old_val
        self.query_one(ContentSwitcher).current = new_val

    class ActiveVertexChanged(Message):
        """Sent when the selected vertex changes.

        Properties:
            vertex: int - The offset of the active vertex within the _ShaderProgram's vertex_inputs.
        """

        def __init__(self, vertex: int) -> None:
            super().__init__()
            self.vertex = vertex


def _render_vertex(vertex_dict: dict, vertex_prefix: str) -> RenderableType:
    x = vertex_dict.get(f"{vertex_prefix}.x")
    if x is None:
        return Text("N/A", "dim")

    y = vertex_dict.get(f"{vertex_prefix}.y", "??")
    z = vertex_dict.get(f"{vertex_prefix}.z", "??")
    w = vertex_dict.get(f"{vertex_prefix}.w", "??")

    return f"{x}, {y}, {z}, {w}"
