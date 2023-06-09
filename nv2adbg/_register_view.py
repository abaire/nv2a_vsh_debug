"""Provides functions to lay out information about a single register."""

from typing import List
from typing import Tuple

from rich.table import Table
from rich.text import Text


def layout_register_lines(register_lines: List[List[Text]], max_width: int) -> Table:
    """Lays out a list of register text blocks in a grid, attempting to fit within the given number of columns.

    Arguments:
        register_lines - List of Lists of Text instances following the form [register_name, x, y, z, w].
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


def _measure_register_lines(register_lines: List[List[Text]]) -> Tuple[int, int]:
    """Returns a tuple of (max register name len, max value len) across all the given lines."""
    if not register_lines:
        return 0, 0

    max_cell_lens = [0] * len(register_lines[0])

    for line in register_lines:
        for i in range(len(max_cell_lens)):
            max_cell_lens[i] = max(max_cell_lens[i], line[i].cell_len)

    return max_cell_lens[0], max(*max_cell_lens[1:])


def _layout_xyzw(line: List[Text], label_cell_len: int, value_cell_len: int) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)

    grid.add_row(*line)

    return grid


def _layout_xy_zw(line: List[Text], label_cell_len: int, value_cell_len: int) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)
    grid.add_column(width=value_cell_len)

    grid.add_row(*line[0:3])
    for index in range(3, len(line), 2):
        grid.add_row(" ", *line[index : index + 2])

    return grid


def _layout_x_y_z_w(
    line: List[Text], label_cell_len: int, value_cell_len: int
) -> Table:
    grid = Table.grid()
    grid.add_column(width=label_cell_len, justify="right")
    grid.add_column(width=value_cell_len)

    grid.add_row(*line[0:2])
    for element in line[2:]:
        grid.add_row(" ", element)
    return grid
