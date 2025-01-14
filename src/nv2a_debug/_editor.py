"""Provides functionality to render the editor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from nv2a_debug._code_panel import _CodePanel
from nv2a_debug._input_panel import _InputPanel
from nv2a_debug._output_panel import _OutputPanel

if TYPE_CHECKING:
    from textual.app import ComposeResult

    from nv2a_debug import simulator


class _Editor(Static):
    """Renders the editor UI."""

    DEFAULT_CSS = """
    _Editor {
        height: 1fr;
        width: 1fr;
    }

    _Editor _CodePanel{
        height: 1fr;
        width: 1fr;
    }

    _Editor _InputPanel{
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._trace: simulator.Trace | None = None

        self._code_panel = _CodePanel()
        self._input_panel = _InputPanel()
        self._output_panel = _OutputPanel()

    def set_shader_trace(self, shader_trace: simulator.Trace):
        self._trace = shader_trace
        self._code_panel.set_shader_trace(shader_trace)

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal():
                yield self._code_panel
                yield self._input_panel
            yield self._output_panel
        self._code_panel.focus()

    def on__code_panel_active_line_changed(self, message: _CodePanel.ActiveLineChanged) -> None:
        if message.step is None:
            msg = f"on__code_panel_active_line_changed called with invalid message {message!r}, missing `step`"
            raise ValueError(msg)

        self._output_panel.set_step(message.step)
        self._input_panel.set_step(message.step)


#     def export(self, filename: str, input_resolver):
#         with open(filename, "w", encoding="ascii") as outfile:
#             print("; Inputs:", file=outfile)
#             for input in sorted(self._active_inputs.keys()):
#                 value = ""
#                 if input_resolver:
#                     value = f" = {input_resolver(input)}"
#                 print(f"; {input}{value}", file=outfile)
#
#             print("", file=outfile)
#
#             for line in self._active_source:
#                 print(line[1][0], file=outfile)
