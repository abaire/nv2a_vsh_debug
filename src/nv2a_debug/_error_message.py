"""Provides functionality to display error messages."""

from rich.console import RenderableType
from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.widgets import Label


class _ErrorMessage(Label):
    """Label used to display an error message."""

    DEFAULT_CSS = """
    _ErrorMessage {
        border: double $error;
        padding: 2 4;
        content-align: center middle;
    }
    """

    def __init__(self, error_message: RenderableType):
        super().__init__(error_message)


class _CenteredErrorMessage(Middle):
    """Displays an error message centered within its parent area."""

    DEFAULT_CSS = """
    _ErrorMessage {
        border: double $error;
        padding: 2 4;
        content-align: center middle;
    }
    """

    def __init__(self, error_message: RenderableType, **kwargs):
        super().__init__(**kwargs)

        self._error_message = error_message

    def compose(self) -> ComposeResult:
        yield Center(_ErrorMessage(self._error_message))
