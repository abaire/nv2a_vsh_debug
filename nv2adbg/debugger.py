#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

import argparse
import json
import logging
import os
import sys

import sshkeyboard

import rich
from rich import console
from rich.jupyter import JupyterMixin
from rich.layout import Layout
from rich.rule import Rule
from rich.text import Text

import simulator

class _Editor:

    def __init__(self):
        self._scroll_start = 0
        self._cursor_pos = 0, 0
        self._source = []

    def render(self, con: console.Console, root: Layout, target_name: str):
        """Renders this editor instance to the given Console with the given root Layout. """
        render_map = root.render(con, con.options)

        target = root[target_name]
        region = render_map[target].region
        visible_rows = region.height

        target.split_row(
            Layout(name=f"{target.name}#line", size=4),
            Layout(name=f"{target.name}#content"),
            Layout(name=f"{target.name}#scrollbar", size=1),
        )

        @console.group()
        def get_line_numbers():
            for i in range(self._scroll_start + 1, self._scroll_start + 1 + visible_rows):
                yield Text(f"{i:>3}")
        root[f"{target.name}#line"].update(get_line_numbers())

        @console.group()
        def get_source():
            for i in range(self._scroll_start + 1, self._scroll_start + 1 + visible_rows):
                yield Text("")
        root[f"{target.name}#content"].update(get_source())


class _App:
    _MENU = "menu"
    _SOURCE = "source"
    _CONTEXT = "context"

    def __init__(self):
        self._context = simulator.Context()
        self._console = console.Console()
        self._root = Layout()
        self._editor = _Editor()
        self._active_layout = self._MENU

        self._source_start = 0
        self._context_start = 0
        self._running = False

        self._update()

        self._keymaps = {
            "": self._create_global_keymap(),
            self._MENU: self._create_menu_keymap(),
            self._SOURCE: self._create_source_keymap(),
            self._CONTEXT: self._create_context_keymap(),
        }

    def _create_global_keymap(self):
        #
        # HANDLE esc
        # HANDLE esc
        # HANDLE tab
        # HANDLE /
        # HANDLE backspace
        # HANDLE \
        # "space"
        #     HANDLE delete
        #     "\x1bOA": "up",
        #     "\x1bOB": "down",
        #     "\x1bOC": "right",
        #     "\x1bOD": "left",
        #     "\x1b[2~": "insert",
        #     "\x1b[3~": "delete",
        #     "\x1b[5~": "pageup",
        #     "\x1b[6~": "pagedown",

        def _gen_focus(target):
            self._activate_section(target)
            sshkeyboard.stop_listening()

        return {
            "f1": lambda: _gen_focus(self._MENU),
            "f2": lambda: _gen_focus(self._SOURCE),
            "f3": lambda: _gen_focus(self._CONTEXT),
        }

    def _create_menu_keymap(self):
        return {}

    def _create_source_keymap(self):
        return {}

    def _create_context_keymap(self):
        return {}

    def _activate_section(self, target):
        self._active_layout = target

        for section in [self._MENU, self._SOURCE, self._CONTEXT]:
            def content():
                if self._active_layout == section:
                    return Text("*")
                return Text("")

            self._root[f"{section}#active"].update(content())

    @property
    def _active_keymap(self):
        return self._keymaps.get(self._active_layout, {})

    def _update(self):
        self._root.split_column(
            Layout(name=self._MENU, size=1),
            Layout(name=self._SOURCE),
            Layout(name="#rule", size=1),
            Layout(name=self._CONTEXT)
        )

        self._root["#rule"].update(Rule())

        self._root[self._MENU].split_row(
            Layout(name=f"{self._MENU}#active", size=1),
            Layout(name=f"{self._MENU}#content"),
        )

        self._root[self._SOURCE].split_row(
            Layout(name=f"{self._SOURCE}#active", size=1),
            Layout(name=f"{self._SOURCE}#content"),
        )

        self._root[self._CONTEXT].split_row(
            Layout(name=f"{self._CONTEXT}#active", size=1),
            Layout(name=f"{self._CONTEXT}#content"),
            Layout(name=f"{self._CONTEXT}#scrollbar", size=1),
        )

        self._root[f"{self._CONTEXT}#content"].split_row(
            Layout(name=f"{self._CONTEXT}#content#left"),
            Layout(name=f"{self._CONTEXT}#content#right"),
        )

        self._update_menu()
        self._update_source()
        self._update_context()
        self._activate_section(self._active_layout)

    def _update_menu(self):
        def content():
            if self._active_layout == self._MENU:
                return Text("[F]ile", style="bold magenta", justify="left")
            return Text("File", style="magenta", justify="left")
        self._root[f"{self._MENU}#content"].update(content())

    def _update_source(self):
        self._editor.render(self._console, self._root, f"{self._SOURCE}#content")

    def _update_context(self):
        registers = self._context.registers
        num_items = len(registers)

        left = self._root[f"{self._CONTEXT}#content#left"]
        right = self._root[f"{self._CONTEXT}#content#right"]
        right.visible = False
        render_map = self._root.render(self._console, self._console.options)

        region = render_map[left].region
        max_width = region.width

        last_item = min(num_items, self._context_start + region.height)
        @console.group()
        def get_registers():
            for reg in registers[self._context_start:last_item]:
                yield Text.assemble((f"{reg.name:>5}", "cyan"), f" {reg.x:f}, {reg.y:f}, {reg.z:f}, {reg.w:f}")

        self._root[f"{self._CONTEXT}#content#left"].update(get_registers())

    def render(self):
        """Draws the application to the console."""
        rich.print(self._root)

    def _handle_key(self, key):
        if key == "esc":
            self._running = False
            sshkeyboard.stop_listening()

        keymap = self._active_keymap
        action = keymap.get(key, None)
        if action:
            action()
            return

        default_keymap = self._keymaps[""]
        action = default_keymap.get(key, None)
        if action:
            action()
        print(f"Unhandled key {key}")

    def run(self):
        self._running = True
        with self._console.screen() as screen:
            screen.update(self._root)

            try:
                while self._running:
                    sshkeyboard.listen_keyboard(on_press=self._handle_key, until=None)
                    if self._running:
                        self._update()
                        screen.update(self._root)
            except KeyboardInterrupt:
                return


def _emit_input_template():
    ctx = simulator.Context()
    values = ctx.to_dict(True)
    json.dump(values, sys.stdout, indent=2, sort_keys=True)


def _main(args):
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if args.emit_inputs:
        _emit_input_template()
        return 0

    inputs = {}
    if args.inputs:
        if not os.path.isfile(args.inputs):
            print(f"Failed to open input definition file '{args.inputs}'", file=sys.stderr)
            return 1
        with open(args.inputs, encoding="ascii") as infile:
            inputs = json.load(infile)

    shader = simulator.Shader()
    shader.set_initial_state(inputs)

    if args.source:
        if not os.path.isfile(args.source):
            print(f"Failed to open source file '{args.source}'", file=sys.stderr)
            return 1

        with open(args.source, encoding="utf-8") as infile:
            source = infile.read()
        shader.set_source(source)

    if args.json:
        output = shader.explain()
        # DONOTSUBMIT
        # json.dump(output, sys.stdout, indent=2, sort_keys=True)
        return 0

    app = _App()
    app.run()

    return 0


def entrypoint():
    """The main entrypoint for this program."""

    def _parse_args():
        parser = argparse.ArgumentParser()

        parser.add_argument(
            "source",
            nargs="?",
            metavar="source_path",
            help="Source file to assemble.",
        )

        parser.add_argument(
            "-i",
            "--inputs",
            metavar="json_inputs",
            help="Use the JSON content of the given file as the shader input state."
        )

        parser.add_argument(
            "--emit-inputs",
            action="store_true",
            help="Emit a template JSON file that may be used to modify the inputs to the shader."
        )

        parser.add_argument(
            "-j",
            "--json",
            action="store_true",
            help="Emit a JSON document capturing the context at each instruction in the source."
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
