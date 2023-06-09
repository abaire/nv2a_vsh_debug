"""Provides functionality to render the File menu."""

from typing import Callable

from textual.app import ComposeResult
from textual.containers import Center
from textual.containers import Horizontal
from textual.reactive import Reactive
from textual.screen import ModalScreen
from textual.widgets import Button
from textual.widgets import Input
from textual.widgets import Label


class _FileMenu(ModalScreen):
    """Renders the file input menu."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    _FileMenu {
        layout: grid;
        grid-columns: 28 1fr;
        grid-size: 2;
    }

    _FileMenu .label {
        padding: 1 2;
        text-align: right;
    }

    #buttonbar {
        column-span: 2;
    }
    """

    def __init__(
        self,
        on_accept: Callable[[str, str, str, str], None],
        on_cancel: Callable[[], None],
        source_file: str = "",
        inputs_file: str = "",
        mesh_inputs_file: str = "",
        constants_file: str = "",
    ):
        super().__init__()
        self._on_accept = on_accept
        self._on_cancel = on_cancel
        self._source_file = source_file
        self._inputs_file = inputs_file
        self._mesh_inputs_file = mesh_inputs_file
        self._constants_file = constants_file

    def compose(self) -> ComposeResult:
        def _row(input_id: str, label: str, placeholder: str, value: Reactive):
            yield Label(label, classes="label")
            yield Input(placeholder=placeholder, value=value, id=input_id)

        yield from _row(
            "source",
            "Source file",
            "File containing the nv2a program to debug",
            self._source_file,
        )
        yield from _row(
            "inputs",
            "JSON inputs file",
            "JSON file containing explicit initial state (see --emit-inputs template generation)",
            self._inputs_file,
        )
        yield from _row(
            "mesh",
            "Renderdoc inputs file",
            "CSV file containing mesh vertices as exported from RenderDoc",
            self._mesh_inputs_file,
        )
        yield from _row(
            "constants",
            "Renderdoc constants file",
            "CSV file containing the constant register values as exported from RenderDoc",
            self._constants_file,
        )

        with Horizontal(id="buttonbar"):
            yield Center(Button("Cancel", id="cancel"))
            yield Center(Button("Apply", variant="primary", id="apply"))

    def _on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._on_accept(
                self.get_widget_by_id("source").value,
                self.get_widget_by_id("inputs").value,
                self.get_widget_by_id("mesh").value,
                self.get_widget_by_id("constants").value,
            )
        elif event.button.id == "cancel":
            self._on_cancel()

    def _action_cancel(self):
        self._on_cancel()
