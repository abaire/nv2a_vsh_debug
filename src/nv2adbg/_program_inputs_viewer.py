"""Provides functionality to browse the input state."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.css import query
from textual.reactive import reactive
from textual.widgets import ContentSwitcher
from textual.widgets import DataTable
from textual.widgets import Static

from nv2adbg import simulator
from nv2adbg._error_message import _CenteredErrorMessage


class _ProgramInputsViewer(Static):
    """Provides a browsing interface to view input registers and vertices."""

    DEFAULT_CSS = """
    _ProgramInputsViewer {
        height: 1fr;
        width: 1fr;
    }

    _ProgramInputsViewer DataTable {
        height: 1fr;
    }
    """

    _active_content = reactive("no-content", init=False)

    def __init__(self):
        super().__init__()
        self._context: Optional[simulator.Context] = None

        self._inputs_table = DataTable(id="inputs-table")
        self._inputs_table.add_columns("Input", "x", "y", "z", "w")
        self._inputs_table.cursor_type = "row"
        self._inputs_table.zebra_stripes = True

        self._constants_table = DataTable(id="constants-table")
        self._constants_table.add_columns("Constant", "x", "y", "z", "w")
        self._constants_table.cursor_type = "row"
        self._constants_table.zebra_stripes = True

    def set_context(self, context: simulator.Context):
        self._context = context
        self._populate_table()
        self.update()

    def on_mount(self) -> None:
        self._populate_table()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="no-content"):
            with Horizontal(id="content"):
                yield self._inputs_table
                yield self._constants_table

            yield _CenteredErrorMessage(
                "No input context available, load data via the File menu.",
                id="no-content",
            )

    def _populate_table(self):
        try:
            self._inputs_table.clear()
            self._constants_table.clear()

            if self._context:
                for register in self._context.inputs:
                    self._inputs_table.add_row(
                        register.name, register.x, register.y, register.z, register.w
                    )
                for register in self._context.constants:
                    self._constants_table.add_row(
                        register.name, register.x, register.y, register.z, register.w
                    )
                self._active_content = "content"
            else:
                self._active_content = "no-content"

        except query.NoMatches:
            # The table is not loaded yet.
            pass

    def _watch__active_content(self, _old_val: str, new_val: str):
        del _old_val
        self.query_one(ContentSwitcher).current = new_val
