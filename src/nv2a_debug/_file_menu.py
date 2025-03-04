"""Provides functionality to render the File menu."""

# ruff: noqa: RUF012 Mutable class attributes should be annotated with `typing.ClassVar`

from __future__ import annotations

import os.path
from typing import TYPE_CHECKING, cast

from textual import on
from textual.containers import Center, Horizontal
from textual.screen import ModalScreen
from textual.validation import ValidationResult, Validator
from textual.widgets import Button, Input, Label

if TYPE_CHECKING:
    from collections.abc import Callable

    from textual.app import ComposeResult


class _FileMenu(ModalScreen):
    """Renders the file input menu."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    _FileMenu {
        layout: grid;
        grid-columns: 28 1fr;
        grid-size: 2;
        background: black;
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

        self._apply_button = Button("Apply", variant="primary", id="apply", disabled=True)

    def on_mount(self) -> None:
        self._check_validation()

    def _check_validation(self):
        self._apply_button.disabled = any(
            [not i.validate(i.value).is_valid for i in self.query(Input)]  # noqa: C419 Unnecessary list comprehension
        )

    @on(Input.Changed)
    def _update_validation(self, event: Input.Changed) -> None:
        if not event.validation_result or not event.validation_result.is_valid:
            self._apply_button.disabled = True
        else:
            self._check_validation()

    def compose(self) -> ComposeResult:
        def _row(input_id: str, label: str, placeholder: str, value: str):
            yield Label(label, classes="label")
            yield Input(
                placeholder=placeholder,
                value=value,
                id=input_id,
                validators=[ExistingFile()],
            )

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
            yield Center(self._apply_button)

    def _on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "apply":
            self._on_accept(
                cast(Input, self.get_widget_by_id("source")).value,
                cast(Input, self.get_widget_by_id("inputs")).value,
                cast(Input, self.get_widget_by_id("mesh")).value,
                cast(Input, self.get_widget_by_id("constants")).value,
            )
        elif event.button.id == "cancel":
            self._on_cancel()

    def _action_cancel(self):
        self._on_cancel()


class ExistingFile(Validator):
    """Validator to confirm that a string is the path to a valid file."""

    def validate(self, value: str) -> ValidationResult:
        """Check that a string points at a valid file."""

        if not value or os.path.isfile(value):
            return self.success()

        return self.failure("No such file")
