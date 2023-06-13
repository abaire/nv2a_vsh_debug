"""Provides functionality to render the editor."""

from typing import Dict
from typing import Optional
from typing import Set

from textual.app import ComposeResult
from textual.containers import Center
from textual.containers import Horizontal
from textual.containers import Middle
from textual.containers import Vertical
from textual.widgets import Label
from textual.widgets import Static

from nv2adbg import simulator
from nv2adbg._code_panel import _CodePanel
from nv2adbg._input_panel import _InputPanel
from nv2adbg._output_panel import _OutputPanel


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

    def __init__(self):
        super().__init__()
        self._trace: Optional[simulator.Trace] = None

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

    def on__code_panel_active_line_changed(
        self, message: _CodePanel.ActiveLineChanged
    ) -> None:
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
