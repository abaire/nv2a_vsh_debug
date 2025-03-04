"""Provides functions to lay out information about a single register."""

# ruff: noqa: RUF012 Mutable class attributes should be annotated with `typing.ClassVar`

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.widgets import Static

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.console import RenderableType

    from nv2a_debug.simulator import Register


class _RegisterSetPanel(Static):
    COMPONENT_CLASSES = {
        "registersetpanel--register",
        "registersetpanel--value",
        "registersetpanel--border",
    }

    DEFAULT_CSS = """
    _RegisterSetPanel .registersetpanel--register {
        background: $surface;
        color: $text;
    }
    _RegisterSetPanel .registersetpanel--value {
        background: $surface;
        color: $text;
    }
    _RegisterSetPanel .registersetpanel--border {
    }
    """

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self._title: str = title
        self._registers: list[Register] | None = None
        self._name_modifier: Callable[[str], str] | None = None

    def set_registers(
        self,
        registers: list[Register],
        name_modifier: Callable[[str], str] | None = None,
    ):
        self._registers = registers
        self._name_modifier = name_modifier

    def render(self) -> RenderableType:
        if not self._registers:
            return ""
        register_lines = [self._build_renderables(r) for r in self._registers]
        if not register_lines:
            return ""
        content = layout_register_lines(register_lines, self.size.width)
        return Panel(
            content,
            title=self._title,
            border_style=self.get_component_rich_style("registersetpanel--border"),
        )

    def _build_renderables(self, register: Register) -> list[Text]:
        ret = [
            Text.assemble(
                (
                    self._name_modifier(register.name) if self._name_modifier else register.name,
                    self.get_component_rich_style("registersetpanel--register"),
                )
            )
        ]

        value_style = self.get_component_rich_style("registersetpanel--value")
        ret.append(Text(f" {register.x}", value_style))
        ret.append(Text(f" {register.y}", value_style))
        ret.append(Text(f" {register.z}", value_style))
        ret.append(Text(f" {register.w}", value_style))

        return ret


def layout_register_lines(register_lines: list[list[Text]], max_width: int) -> Table:
    """Lays out a list of register text blocks in a grid, attempting to fit within the given number of columns.

    Arguments:
        register_lines - list of Lists of Text instances following the form [register_name, x, y, z, w].
        max_width - The maximum number of text cells available per line.
    """
    label_cell_len, value_cell_len = _measure_register_lines(register_lines)

    value_width = (value_cell_len + 1) * (len(register_lines[0]) - 1)
    total_width = label_cell_len + value_width + 1

    grid = Table.grid()
    grid.add_column()

    if total_width < max_width:
        # Lay out each line as a single row.
        for line in register_lines:
            grid.add_row(_layout_xyzw(line, label_cell_len, value_cell_len))
    else:
        xy_width = sum([x.cell_len for x in register_lines[0][0:3]])
        if xy_width < max_width:
            for line in register_lines:
                grid.add_row(_layout_xy_zw(line, label_cell_len, value_cell_len))
        else:
            for line in register_lines:
                grid.add_row(_layout_x_y_z_w(line, label_cell_len, value_cell_len))

    return grid


def _measure_register_lines(register_lines: list[list[Text]]) -> tuple[int, int]:
    """Returns a tuple of (max register name len, max value len) across all the given lines."""
    if not register_lines:
        return 0, 0

    max_cell_lens = [0] * len(register_lines[0])

    for line in register_lines:
        for i in range(len(max_cell_lens)):
            max_cell_lens[i] = max(max_cell_lens[i], line[i].cell_len)

    return max_cell_lens[0], max(*max_cell_lens[1:])


def _layout_xyzw(line: list[Text], label_cell_len: int, value_cell_len: int) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)

    grid.add_row(*line)

    return grid


def _layout_xy_zw(line: list[Text], label_cell_len: int, value_cell_len: int) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)

    grid.add_row(*line[0:3])
    for index in range(3, len(line), 2):
        grid.add_row(" ", *line[index : index + 2])

    return grid


def _layout_x_y_z_w(line: list[Text], label_cell_len: int, value_cell_len: int) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)

    grid.add_row(*line[0:2])
    for element in line[2:]:
        grid.add_row(" ", element)
    return grid
