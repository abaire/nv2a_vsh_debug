"""Provides functionality to render the File menu."""

from rich import console
from rich.layout import Layout
from rich.prompt import Prompt
from rich.text import Text
from typing import Tuple, Union

from nv2adbg._shader_program import _ShaderProgram


class _FileMenu:
    """Renders the file input menu."""

    def __init__(self, program: _ShaderProgram):
        self._program = program
        self._cursor_pos = 0
        self._entries = []
        self._entry_titles = [
            " Source             ",
            " Inputs             ",
            " Renderdoc Inputs   ",
            " Renderdoc Constants",
        ]
        self._active_prompt = None
        self._reset_values()
        self._reset_action_index = None
        self._activate_action_index = None
        self._update_entries()

    def create_keymap(self, on_complete):
        """Returns a keymap used to interact with this menu.

        Arguments:
            on_complete: Method to be invoked when the menu should be closed.
        """

        def activate():
            if self.activate():
                on_complete()

        return {
            "up": lambda: self._navigate(-1),
            "down": lambda: self._navigate(1),
            "enter": activate,
            "tab": activate,
        }

    def _navigate(self, delta: int):
        self._cursor_pos = (self._cursor_pos + delta) % len(self._entries)

    def activate(self) -> bool:
        """Activates the currently highlighted submenu entry. Returns True if the menu should be exited."""
        if self._cursor_pos == self._activate_action_index:
            self._program.source_file = self._values[0]
            self._program.inputs_file = self._values[1]
            self._program.mesh_inputs_file = self._values[2]
            self._program.constants_file = self._values[3]
            return True

        if self._cursor_pos == self._reset_action_index:
            self._reset_values()
            return True

        self._active_prompt = self._entry_titles[self._cursor_pos]
        return False

    def _reset_values(self):
        self._values = [
            self._program.source_file,
            self._program.inputs_file,
            self._program.mesh_inputs_file,
            self._program.constants_file,
        ]

    def _process_input(self, value: str):
        if not value:
            return
        self._values[self._cursor_pos] = value

    def render(self, con: console.Console, root: Layout, target_name: str):
        """Renders this file menu instance to the given Console with the given root Layout."""
        render_map = root.render(con, con.options)

        target = root[target_name]
        region = render_map[target].region

        if self._active_prompt:
            con.clear()
            value = Prompt.ask(self._active_prompt, console=con)
            self._process_input(value)
            self._active_prompt = None
            con.clear()

        self._update_entries()

        def _build(index, value) -> Union[str, Tuple[str, str]]:
            if index == self._cursor_pos:
                return value, "bold"
            return value

        entries = [
            Layout(Text.assemble(_build(i, v)), size=1)
            for i, v in enumerate(self._entries)
        ]

        target.split_column(*entries)

    def _update_entries(self):
        self._entries = [
            f"{title}: {value}"
            for title, value in zip(self._entry_titles, self._values)
        ]
        self._entries.extend(
            [
                "<Apply>",
                "<Cancel>",
            ]
        )

        self._activate_action_index = len(self._entries) - 2
        self._reset_action_index = self._activate_action_index + 1
