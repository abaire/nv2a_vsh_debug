#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

import argparse
import collections
import copy
import logging
import os
import sys

import rich
from rich import console
from rich.layout import Layout
from rich.text import Text
from rich.live import Live

_Register = collections.namedtuple("_Register", ["name", "x", "y", "z", "w"])

_OUTPUTS = [
    "oPos",
    "oD0",
    "oD1",
    "oFog",
    "oPts",
    "oB0",
    "oB1",
    "oTex0",
    "oTex1",
    "oTex2",
    "oTex3",
]

class _Context:
    """Holds the current register context."""
    def __init__(self):
        self._temp_registers = []
        for i in range(11):
            self._temp_registers.append(_Register(f"r{i}", 0, 0, 0, 1))

        self._input_registers = []
        for i in range(15):
            self._input_registers.append(_Register(f"v{i}", 0, 0, 0, 0))

        self._address_register = _Register(f"a0", 0, None, None, None)

        self._constant_registers = []
        for i in range(192):
            self._constant_registers.append(_Register(f"c{i}", 0, 0, 0, 0))

        self._output_registers = []
        for name in _OUTPUTS:
            self._output_registers.append(_Register(name, 0, 0, 0, 0))

        self._flat_registers = []
        self._flat_registers.extend(self._temp_registers)
        self._flat_registers.extend(self._input_registers)
        self._flat_registers.append(self._address_register)
        self._flat_registers.extend(self._constant_registers)
        self._flat_registers.extend(self._output_registers)

    @property
    def registers(self):
        return self._flat_registers

    def duplicate(self):
        return copy.deepcopy(self)


class _App:
    def __init__(self):
        self._context = _Context()
        self._console = console.Console()
        self._root = Layout()

        self._root.split_column(
            Layout(name="menu", size=1),
            Layout(name="source"),
            Layout(name="registers")
        )

        self._root["source"].split_row(
            Layout(name="source#line", size=4),
            Layout(name="source#content"),
            Layout(name="source#scrollbar", size=1),
        )

        self._root["registers"].split_row(
            Layout(name="registers#content"),
            Layout(name="registers#scrollbar", size=1),
        )

        self._root["menu"].update(Text("[F]ile", style="bold magenta", justify="left"))

    def _update_registers(self):
        registers = self._context.registers

        @console.group()
        def get_panels():
            for reg in registers:
                yield Text(f"{reg.name} {reg.x} {reg.y} {reg.z} {reg.w}")
        self._root["registers#content"].update(get_panels())


    def render(self):
        rich.print(self._root)


def _main(args):
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if args.input and not os.path.isfile(args.input):
        print(f"Failed to open input file '{args.input}'", file=sys.stderr)
        return 1

    app = _App()
    app._update_registers()
    app.render()

    #     with Live(layout, screen=False, redirect_stderr=False) as live:
    #         try:
    #             while True:
    #                 sleep(1)
    #         except KeyboardInterrupt:
    #             pass

    return 0


def entrypoint():
    """The main entrypoint for this program."""

    def _parse_args():
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "input",
            nargs="?",
            metavar="source_path",
            help="Source file to assemble.",
        )

        parser.add_argument(
            "-v",
            "--verbose",
            help="Enables verbose logging information",
            action="store_true",
        )

        return parser.parse_args()

    sys.exit(_main(_parse_args()))


if __name__ == "__main__":
    entrypoint()
