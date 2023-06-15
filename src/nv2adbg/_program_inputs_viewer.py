"""Provides functionality to browse the input state."""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.containers import VerticalScroll
from textual.css import query
from textual.reactive import reactive
from textual.widgets import ContentSwitcher
from textual.widgets import Static

from nv2adbg._error_message import _CenteredErrorMessage
from nv2adbg._register_view import _RegisterSetPanel
from nv2adbg.simulator import Context


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

    #inputs-table .registersetpanel--register {
        color: $success;
        text-style: bold;
    }

    #constants-table .registersetpanel--border {
        color: $warning;
    }

    #constants-table .registersetpanel--register {
        color: $success;
        text-style: bold;
    }
    """

    _active_content = reactive("no-content", init=False)

    def __init__(self):
        super().__init__()
        self._context: Optional[Context] = None

        self._inputs_table = _RegisterSetPanel("Inputs", id="inputs-table")
        self._constants_table = _RegisterSetPanel("Constants", id="constants-table")

    def set_context(self, context: Context):
        self._context = context
        self._populate()
        self.update()

    def on_mount(self) -> None:
        self._populate()

    def compose(self) -> ComposeResult:
        with ContentSwitcher(initial="no-content"):
            with Horizontal(id="content"):
                with VerticalScroll():
                    yield self._inputs_table
                with VerticalScroll():
                    yield self._constants_table

            yield _CenteredErrorMessage(
                "No input context available, load data via the File menu.",
                id="no-content",
            )

    def _populate(self):
        try:
            if self._context:
                self._inputs_table.set_registers(self._context.inputs)

                def rename_constant_register(name: str) -> str:
                    return f"c[{name[1:]}]"

                self._constants_table.set_registers(
                    self._context.constants, rename_constant_register
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
