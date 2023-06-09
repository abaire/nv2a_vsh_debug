"""Provides functionality to browse the input state."""

from typing import Optional

import textual.css.query
from textual.app import ComposeResult
from textual.containers import Center
from textual.containers import Middle
from textual.widgets import DataTable
from textual.widgets import Label
from textual.widgets import Static

from nv2adbg import simulator


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

    #center_message {
        height: 1fr;
        width: 1fr;
    }

    #empty_message {
        border: double $error;
        padding: 2 4;
        content-align: center middle;
    }
    """

    def __init__(self):
        super().__init__()
        self._context: Optional[simulator.Context] = None

    def set_context(self, context: simulator.Context):
        self._context = context
        self.update()
        self._populate_table()

    def on_mount(self) -> None:
        self._populate_table()

    def compose(self) -> ComposeResult:
        if self._context:
            table = DataTable()
            table.add_columns("Register", "x", "y", "z", "w")
            table.cursor_type = "row"
            table.zebra_stripes = True
            table.focus()
            yield table
        else:
            yield Middle(
                Center(
                    Label(
                        "No input context available, load data via the File menu.",
                        id="empty_message",
                    )
                ),
                id="center_message",
            )

    def _populate_table(self):
        try:
            table = self.query_one(DataTable)
            table.clear()

            if self._context:
                for register in self._context.constants:
                    table.add_row(
                        register.name, register.x, register.y, register.z, register.w
                    )

        except textual.css.query.NoMatches:
            # The table is not loaded yet.
            pass
