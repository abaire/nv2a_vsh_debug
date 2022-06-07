#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

import argparse
import csv
import json
import logging
import os
import re
import sys
from typing import Iterable, List, Set, Tuple

import sshkeyboard

import rich
from rich import console
from rich.jupyter import JupyterMixin
from rich.layout import Layout
from rich.rule import Rule
from rich.text import Text

import simulator


_CONSTANT_NAME_RE = re.compile(r"c\[(\d+)]")

# c[12]
# -R1.xyz
# oD0.w
_RAW_REGISTER_RE = re.compile(r"-?(.+?)(?:\.(.*))?$")


def clamp(val: int, min_val: int, max_val: int) -> int:
    if val < min_val:
        return min_val
    if val > max_val:
        return max_val
    return val


def _find_ancestors(source: List[Tuple[str, dict]]) -> Tuple[dict, Set[str]]:
    """Returns ([highlights for contributing lines], [program inputs]) for the last entry in 'source'."""
    if not source:
        return {}, set()

    source = list(enumerate(source))
    source.reverse()
    instruction_dict = source[0][1][1]

    def _strip(element: str) -> str:
        match = _RAW_REGISTER_RE.match(element)
        if not match:
            raise Exception(f"Failed to parse register {element}")
        # For now, just strip any mask/swizzle. Ideally these should be tracked so that writes to ignored components
        # are not flagged as ancestors.
        return match.group(1)

    def _extract(ins: dict, key: str) -> Set[str]:
        ret: Set[str] = set()
        mac = ins.get("mac")
        if mac:
            for element in mac[key]:
                ret.add(_strip(element))

        ilu = ins.get("ilu")
        if ilu:
            for element in ilu[key]:
                ret.add(_strip(element))
        return ret

    inputs = _extract(instruction_dict, "inputs")
    highlights = {}
    for line_num, (source_text, instruction_dict) in source[1:]:
        outputs = _extract(instruction_dict, "outputs")
        contributing = outputs.intersection(inputs)
        if not contributing:
            continue

        highlights[line_num] = 0, -1
        inputs -= outputs
        inputs |= _extract(instruction_dict, "inputs")

    return highlights, inputs


class _Editor:
    def __init__(self):
        self._scroll_start: int = 0
        self._cursor_pos_row: int = 0
        self._cursor_pos_col: int = 0
        self._ancestors_row: int = -1
        self._source: List[Tuple[str, dict]] = []
        self._hide_untagged_rows = False

        # State for ancestor highlighting.
        self._highlights: dict = {}
        self._highlighted_inputs: Set[str] = set()

    def set_source(self, source: List[Tuple[str, dict]]):
        """Sets the source code in this editor to the given list of (text, instruction_info) tuples."""
        self._source = source

    def navigate(self, delta: int):
        self._cursor_pos_row = clamp(
            self._cursor_pos_row + delta, 0, len(self._source) - 1
        )

    @property
    def show_instruction_ancestors(self):
        return self._ancestors_row >= 0

    @show_instruction_ancestors.setter
    def show_instruction_ancestors(self, enable: bool):
        if not enable:
            self._ancestors_row = -1
        else:
            self._ancestors_row = self._cursor_pos_row
            self._highlights, self._highlighted_inputs = _find_ancestors(
                self._source[: self._cursor_pos_row + 1]
            )

    def toggle_instruction_ancestors(self):
        """Toggles highlighting of instructions that mutate the arguments of the current instruction."""
        if self._ancestors_row == self._cursor_pos_row:
            self.show_instruction_ancestors = False
            return
        self.show_instruction_ancestors = True

    def render(self, con: console.Console, root: Layout, target_name: str):
        """Renders this editor instance to the given Console with the given root Layout."""
        render_map = root.render(con, con.options)

        target = root[target_name]
        region = render_map[target].region
        visible_rows = region.height

        middle_row = visible_rows // 2
        if self._cursor_pos_row < middle_row:
            self._scroll_start = 0
        elif self._cursor_pos_row >= len(self._source) - middle_row:
            self._scroll_start = len(self._source) - visible_rows
        else:
            self._scroll_start = self._cursor_pos_row - middle_row

        target.split_row(
            Layout(name=f"{target.name}#line", size=4),
            Layout(name=f"{target.name}#content"),
            Layout(name=f"{target.name}#scrollbar", size=1),
        )

        @console.group()
        def get_line_numbers():
            for i in range(
                self._scroll_start + 1, self._scroll_start + 1 + visible_rows
            ):
                yield Text(f"{i:>3}")

        root[f"{target.name}#line"].update(get_line_numbers())

        @console.group()
        def get_source():
            for i in range(self._scroll_start, self._scroll_start + visible_rows):
                if i < len(self._source):
                    line = self._source[i][0]
                    ret = Text(f"{self._get_cursor(i)}{line}")
                    self._stylize_line(i, ret)
                    yield ret
                else:
                    yield Text("")

        root[f"{target.name}#content"].update(get_source())

    def _get_cursor(self, row: int) -> str:
        elements = []
        if self._ancestors_row == row:
            elements.append("=")
        elif row in self._highlights:
            elements.append("A")
        if self._cursor_pos_row == row:
            elements.append(">")

        ret = "".join(elements)
        return f"{ret:<3}"

    def _stylize_line(self, line_num: int, line: Text):
        style = set()
        if line_num == self._cursor_pos_row:
            style.add("bold")
            style.add("underline")
        if line_num in self._highlights:
            style.add("italic")

        if not style:
            return

        line.stylize(" ".join(style))


class _App:
    _MENU = "menu"
    _SOURCE = "source"
    _CONTEXT = "context"

    def __init__(self, shader_trace: dict):
        self._context = simulator.Context()
        self._console = console.Console()
        self._shader_trace: dict = {}
        self._root = Layout()
        self._editor = _Editor()
        self._active_layout = self._SOURCE if shader_trace else self._MENU

        self._source_start = 0
        self._context_start = 0
        self._running = False

        self._update()

        self.set_shader_trace(shader_trace)

        self._keymaps = {
            "": self._create_global_keymap(),
            self._MENU: self._create_menu_keymap(),
            self._SOURCE: self._create_source_keymap(),
            self._CONTEXT: self._create_context_keymap(),
        }

    def set_shader_trace(self, shader_trace: dict):
        steps = shader_trace["steps"]
        self._editor.set_source(
            [(step["source"], step["instruction"]) for step in steps]
        )
        self._update()

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
        def navigate(delta: int):
            self._editor.navigate(delta)
            sshkeyboard.stop_listening()

        def toggle_ancestors():
            self._editor.toggle_instruction_ancestors()
            sshkeyboard.stop_listening()

        return {
            "up": lambda: navigate(-1),
            "down": lambda: navigate(1),
            "pageup": lambda: navigate(-5),
            "pagedown": lambda: navigate(5),
            "a": toggle_ancestors,
        }

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
            Layout(name=self._CONTEXT),
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
            for reg in registers[self._context_start : last_item]:
                yield Text.assemble(
                    (f"{reg.name:>5}", "cyan"),
                    f" {reg.x:f}, {reg.y:f}, {reg.z:f}, {reg.w:f}",
                )

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


def _merge_inputs(row: dict, shader: simulator.Shader):
    inputs = []
    for index in range(0, 16):
        key_base = f"v{index}"
        keys = [f"{key_base}.{component}" for component in "xyzw"]

        valid = False
        register = [key_base]
        for value in [row.get(key, None) for key in keys]:
            if value is not None:
                valid = True
                value = float(value)
            else:
                value = 0.0
            register.append(value)
        if not valid:
            continue

        inputs.append(register)

    shader.merge_initial_state({"inputs": inputs})


def _merge_constants(rows: Iterable, shader: simulator.Shader):
    registers = []
    for row in rows:
        name = row.get("Name", "")
        match = _CONSTANT_NAME_RE.match(name)
        if not match:
            return
        register = [match.group(1)]

        values = row.get("Value")
        if not values:
            raise Exception(f"Invalid constant entry {row}")

        for value in values.split(", "):
            register.append(float(value))
        registers.append(register)

    if registers:
        shader.merge_initial_state({"inputs": registers})


def _main(args):
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if args.emit_inputs:
        _emit_input_template()
        return 0

    inputs = {}
    if args.inputs:
        if not os.path.isfile(args.inputs):
            print(
                f"Failed to open input definition file '{args.inputs}'", file=sys.stderr
            )
            return 1
        with open(args.inputs, encoding="ascii") as infile:
            inputs = json.load(infile)

    shader = simulator.Shader()
    shader.set_initial_state(inputs)

    if args.renderdoc_mesh:
        if not os.path.isfile(args.renderdoc_mesh):
            print(
                f"Failed to open RenderDoc input definition file '{args.renderdoc_mesh}'",
                file=sys.stderr,
            )
            return 1

        with open(args.renderdoc_mesh, newline="", encoding="ascii") as csvfile:
            reader = csv.DictReader(csvfile)
            row = next(reader)
            row = {key.strip(): val.strip() for key, val in row.items()}
            _merge_inputs(row, shader)

    if args.renderdoc_constants:
        if not os.path.isfile(args.renderdoc_constants):
            print(
                f"Failed to open RenderDoc constant definition file '{args.renderdoc_constants}'",
                file=sys.stderr,
            )
            return 1

        with open(args.renderdoc_constants, newline="", encoding="ascii") as csvfile:
            reader = csv.DictReader(csvfile)
            _merge_constants(reader, shader)

    if args.source:
        if not os.path.isfile(args.source):
            print(f"Failed to open source file '{args.source}'", file=sys.stderr)
            return 1

        with open(args.source, encoding="utf-8") as infile:
            source = infile.read()
        shader.set_source(source)

    shader_trace = shader.explain()
    if args.json:
        json.dump(shader_trace, sys.stdout, indent=2, sort_keys=True)
        return 0

    app = _App(shader_trace)
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
