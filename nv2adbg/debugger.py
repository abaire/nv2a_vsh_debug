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
from rich.layout import Layout
from rich.text import Text

from nv2adbg import simulator
from nv2adbg._editor import _Editor
from nv2adbg._file_menu import _FileMenu
from nv2adbg._shader_program import _ShaderProgram


class _App:
    """Main application."""

    _MENU = "menu"
    _CONTENT = "content"

    def __init__(self, program: _ShaderProgram):
        self._program = program
        self._console = console.Console()
        self._shader_trace: dict = {}
        self._root = Layout()
        self._editor = _Editor()
        self._file_menu = _FileMenu(program)
        self._active_layout = self._CONTENT
        self._active_content = self._editor if program.loaded else self._file_menu

        self._running = False

        self._update()

        self.set_shader_trace(program.shader_trace)

        self._keymaps = {
            "": self._create_global_keymap(),
            self._MENU: self._create_menu_keymap(),
            self._CONTENT: (
                self._editor.create_keymap()
                if program.loaded
                else self._file_menu.create_keymap(self._activate_program())
            ),
        }

    def _activate_program(self):
        if not self._program.loaded:
            return
        self._program.build_shader()
        self.set_shader_trace(self._program.shader_trace)
        self._keymaps[self._CONTENT] = self._editor.create_keymap()
        self._active_content = self._editor

    def set_shader_trace(self, shader_trace: dict):
        if not shader_trace:
            self._editor.clear()
        else:
            steps = shader_trace["steps"]
            self._editor.set_source(
                [(step["source"], step["instruction"]) for step in steps],
                [step["state"] for step in steps],
            )
        self._update()

    def _create_global_keymap(self):
        def _gen_focus(target):
            self._activate_section(target)

        return {
            "f1": lambda: _gen_focus(self._MENU),
            "1": lambda: _gen_focus(self._MENU),
            "f2": lambda: _gen_focus(self._CONTENT),
            "2": lambda: _gen_focus(self._CONTENT),
        }

    def _export(self):
        # TODO: Pop a text input dialog and capture a filename.
        filename = ""
        for index in range(1000):
            filename = f"export{index:04}.vsh"
            if not os.path.exists(filename):
                break
        if os.path.exists(filename):
            raise Exception("Failed to find an unused export filename.")

        def resolve(input):
            return self._program.shader.initial_state.get(input)

        self._editor.export(filename, resolve)

    def _create_menu_keymap(self):
        def handle_file():
            self._active_layout = self._CONTENT
            self._active_content = self._file_menu
            self._keymaps[self._CONTENT] = self._file_menu.create_keymap(
                self._activate_program
            )

        def handle_export():
            self._export()
            self._active_layout = self._CONTENT

        return {
            "f": handle_file,
            "e": handle_export,
        }

    def _activate_section(self, target):
        self._active_layout = target

        for section in [self._MENU, self._CONTENT]:

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
            Layout(name=self._CONTENT),
        )

        self._root[self._MENU].split_row(
            Layout(name=f"{self._MENU}#active", size=1),
            Layout(name=f"{self._MENU}#content"),
        )

        self._root[self._CONTENT].split_row(
            Layout(name=f"{self._CONTENT}#active", size=1),
            Layout(name=f"{self._CONTENT}#content"),
        )

        self._update_menu()
        self._active_content.render(
            self._console, self._root, f"{self._CONTENT}#content"
        )
        self._activate_section(self._active_layout)

    def _update_menu(self):
        menu_spacing = "    "
        menu_items = ["File", "Export"]

        def content():
            if self._active_layout == self._MENU:
                elements = []
                for title in menu_items:
                    elements.append((f"[{title[0]}]", "bold magenta"))
                    elements.append(title[1:])
                    elements.append(menu_spacing)
                return Text.assemble(*elements)
            return Text(menu_spacing.join(menu_items), style="magenta", justify="left")

        self._root[f"{self._MENU}#content"].update(content())

    def render(self):
        """Draws the application to the console."""
        rich.print(self._root)

    def _handle_key(self, key):
        if key == "esc" or key == "q":
            self._running = False
            return

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

        input_queue = []

        def handle_key(key):
            input_queue.append(key)
            sshkeyboard.stop_listening()

        self._running = True
        with self._console.screen() as screen:
            screen.update(self._root)

            try:
                while self._running:
                    input_queue.clear()
                    sshkeyboard.listen_keyboard(
                        on_press=handle_key,
                        until=None,
                        sequential=True,
                        delay_second_char=10,
                    )
                    for key in input_queue:
                        self._handle_key(key)
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

    if args.inputs and not os.path.isfile(args.inputs):
        print(f"Failed to open input definition file '{args.inputs}'", file=sys.stderr)
        return 1
    if args.renderdoc_mesh and not os.path.isfile(args.renderdoc_mesh):
        print(
            f"Failed to open RenderDoc input definition file '{args.renderdoc_mesh}'",
            file=sys.stderr,
        )
        return 1

    if args.renderdoc_constants and not os.path.isfile(args.renderdoc_constants):
        print(
            f"Failed to open RenderDoc constant definition file '{args.renderdoc_constants}'",
            file=sys.stderr,
        )
        return 1

    if args.source and not os.path.isfile(args.source):
        print(f"Failed to open source file '{args.source}'", file=sys.stderr)
        return 1

    program = _ShaderProgram(
        args.source, args.inputs, args.renderdoc_mesh, args.renderdoc_constants
    )

    if args.json:
        json.dump(program.shader_trace, sys.stdout, indent=2, sort_keys=True)
        return 0

    app = _App(program)
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
            help="Use the JSON content of the given file as the shader input state.",
        )

        parser.add_argument(
            "--renderdoc-mesh",
            metavar="renderdoc_csv_export",
            help="Use the v* registers in the given RenderDoc CSV file as the shader input state.",
        )

        parser.add_argument(
            "--renderdoc-constants",
            metavar="renderdoc_csv_export",
            help="Use the c* values in the given RenderDoc CSV file as the shader input state.",
        )

        parser.add_argument(
            "--emit-inputs",
            action="store_true",
            help="Emit a template JSON file that may be used to modify the inputs to the shader.",
        )

        parser.add_argument(
            "-j",
            "--json",
            action="store_true",
            help="Emit a JSON document capturing the context at each instruction in the source.",
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
