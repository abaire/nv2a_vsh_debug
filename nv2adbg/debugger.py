#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

import argparse
import collections
import csv
import json
import logging
import os
import re
import sys
import textwrap
from typing import Dict, Iterable, List, Set, Tuple

import sshkeyboard

import rich
from rich import console
from rich.layout import Layout
from rich.rule import Rule
from rich.text import Text

from nv2adbg import simulator

# Mapping of register name to a set of the masked components
RegisterDictT = Dict[str, Set[str]]

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


def _strip_register_name(element: str) -> Tuple[str, Set[str]]:
    match = _RAW_REGISTER_RE.match(element)
    if not match:
        raise Exception(f"Failed to parse register {element}")

    mask = match.group(2)
    if not mask:
        mask = "xyzw"
    return match.group(1), set(mask)


def _extract_register_dict(ins: Dict[str, dict], key: str) -> Dict[str, RegisterDictT]:
    """Creates a {mac|ilu: {register: mask_set}} dict for the given instruction dict."""
    ret = collections.defaultdict(dict)
    mac = ins.get("mac")
    if mac:
        for element in mac[key]:
            reg, mask = _strip_register_name(element)
            if reg in ret["mac"]:
                ret["mac"][reg].update(mask)
            else:
                ret["mac"][reg] = mask

    ilu = ins.get("ilu")
    if ilu:
        for element in ilu[key]:
            reg, mask = _strip_register_name(element)
            if reg in ret["ilu"]:
                ret["ilu"][reg].update(mask)
            else:
                ret["ilu"][reg] = mask
    return ret


def _merge_register_dict_into(into: RegisterDictT, new_regs: RegisterDictT):
    """Merges a second {register: mask} dict into the first."""
    for reg, mask in new_regs.items():
        new_mask = into.get(reg, set())
        new_mask.update(mask)
        into[reg] = new_mask


def _merge_register_dicts(reg_a: RegisterDictT, reg_b: RegisterDictT) -> RegisterDictT:
    """Merges two {register: mask} dicts."""
    ret = dict(reg_a)
    _merge_register_dict_into(ret, reg_b)
    return ret


def _flatten_register_dicts(regs: Dict[str, RegisterDictT]) -> RegisterDictT:
    """Merge MAC and ILU registers into a single {register: mask} dict."""
    return _merge_register_dicts(regs.get("mac", {}), regs.get("ilu", {}))


def _register_dict_subtract(reg_a: RegisterDictT, reg_b: RegisterDictT):
    """Removes any keys/masks in reg_a that are present in reg_b."""
    for reg, mask in reg_b.items():
        current_mask = reg_a.get(reg, set())
        if not current_mask:
            continue

        new_mask = current_mask - mask
        if not new_mask:
            del reg_a[reg]
            continue
        reg_a[reg] = new_mask


def _register_dict_intersection(
    reg_a: RegisterDictT, reg_b: RegisterDictT
) -> RegisterDictT:
    """Returns a {register: mask} dict containing the intersection of the two dicts."""
    ret = {}
    for reg, mask in reg_b.items():
        current_mask = reg_a.get(reg, set())
        if not current_mask:
            continue

        intersection = current_mask & mask
        if not intersection:
            continue
        ret[reg] = intersection
    return ret


def _resolve_r12_alias(regs: RegisterDictT):
    """Updates the given dictionary by replacing any R12 references with oPos."""
    if "R12" not in regs:
        return

    mask = regs["R12"]
    if "oPos" in regs:
        regs["oPos"].update(mask)
    else:
        regs["oPos"] = mask
    del regs["R12"]


def _discover_inputs(source: List[Tuple[int, Tuple[str, dict]]]) -> RegisterDictT:
    """Returns a set of all inputs into the given list of source lines."""
    ret = {}
    outputs = {}

    for _, (_, instruction_dict) in source:
        instruction_inputs = _extract_register_dict(instruction_dict, "inputs")
        flat_ins = _flatten_register_dicts(instruction_inputs)
        _resolve_r12_alias(flat_ins)

        # Merge in any inputs for which there are no known outputs.
        _register_dict_subtract(flat_ins, outputs)
        _merge_register_dict_into(ret, flat_ins)

        instruction_outputs = _flatten_register_dicts(
            _extract_register_dict(instruction_dict, "outputs")
        )
        _merge_register_dict_into(outputs, instruction_outputs)

    return ret


def _find_ancestors(
    source: List[Tuple[int, Tuple[str, dict]]]
) -> Tuple[dict, RegisterDictT]:
    """Returns ([highlights for contributing lines], [program inputs]) for the last entry in 'source'."""
    if not source:
        return {}, {}

    source = list(source)
    source.reverse()
    instruction_dict = source[0][1][1]

    step_inputs = _extract_register_dict(instruction_dict, "inputs")
    step_inputs = _flatten_register_dicts(step_inputs)
    _resolve_r12_alias(step_inputs)

    highlights = {}
    for line_num, (_, instruction_dict) in source[1:]:
        ins_outs = _extract_register_dict(instruction_dict, "outputs")
        ins_ins = _extract_register_dict(instruction_dict, "inputs")
        mac_outputs = ins_outs.get("mac", {})
        ilu_outputs = ins_outs.get("ilu", {})
        contributing_mac = _register_dict_intersection(mac_outputs, step_inputs)
        contributing_ilu = _register_dict_intersection(ilu_outputs, step_inputs)
        if not (contributing_mac or contributing_ilu):
            continue
        if contributing_mac:
            highlights[line_num] = 0, -1
            _register_dict_subtract(step_inputs, mac_outputs)
            _merge_register_dict_into(step_inputs, ins_ins.get("mac", {}))

        if contributing_ilu:
            highlights[line_num] = 0, -1
            _register_dict_subtract(step_inputs, ilu_outputs)
            _merge_register_dict_into(step_inputs, ins_ins.get("ilu", {}))

    return highlights, step_inputs


_WRITEMASK = {
    "x": 0,
    "y": 1,
    "z": 2,
    "w": 3,
}


def _extract_output(register, active_state) -> Tuple[Tuple[float], List[int]]:
    """Returns ((register_value), [modified_indices])"""
    components = register.split(".")
    if components[0] == "a0":
        return active_state["address"]

    if len(components) > 1:
        writemask = [_WRITEMASK[item] for item in components[1]]
    else:
        writemask = [0, 1, 2, 3]

    def fetch(regname, reg_set):
        for reg in reg_set:
            if reg[0] == regname:
                return (tuple(reg[1:]), writemask)
        raise Exception(f"Failed to retrieve register {regname}")

    if register[0] == "c":
        return fetch(components[0], active_state["constant"])
    if register[0] == "R":
        return fetch(components[0], active_state["temp"])
    if register[0] == "o":
        reg_name = f"o{simulator.OUTPUT_TO_INDEX[components[0]]}"
        return fetch(reg_name, active_state["output"])

    raise Exception(f"Invalid register: {register}")


class _Editor:
    def __init__(self):
        self._scroll_start: int = 0
        self._display_cursor_row: int = 0
        self._cursor_pos_col: int = 0
        self._ancestors_row: int = -1
        self._source: List[Tuple[int, Tuple[str, dict]]] = []
        self._show_outputs = True

        self._filtered_source: List[Tuple[int, Tuple[str, dict]]] = []
        self._filter_untagged_rows = False
        self._data_cursor_row: int = 0

        # State for ancestor highlighting.
        self._highlights: dict = {}
        self._highlighted_inputs: RegisterDictT = {}
        self._used_inputs: RegisterDictT = {}

    def set_source(self, source: List[Tuple[str, dict]], states: List[dict]):
        """Sets the source code in this editor to the given list of (text, instruction_info) tuples."""
        self._source = list(enumerate(source))
        self._states = states
        self._used_inputs = _discover_inputs(self._source)
        self._highlights.clear()
        self._highlighted_inputs.clear()
        self._update_filter()

    def export(self, filename: str, input_resolver):
        with open(filename, "w", encoding="ascii") as outfile:
            print("; Inputs:", file=outfile)
            for input in sorted(self._active_inputs.keys()):
                value = ""
                if input_resolver:
                    value = f" = {input_resolver(input)}"
                print(f"; {input}{value}", file=outfile)

            print("", file=outfile)

            for line in self._active_source:
                print(line[1][0], file=outfile)

    def _update_filter(self):
        self._filtered_source = self._source
        if not self._ancestors_row:
            return

        def _keep(entry: Tuple[int, Tuple[str, dict]]) -> bool:
            line_num = entry[0]
            if line_num == self._ancestors_row:
                return True
            if line_num in self._highlights:
                return True
            return False

        self._filtered_source = [entry for entry in self._source if _keep(entry)]

    def navigate(self, delta: int):
        source = self._active_source
        self._display_cursor_row = clamp(
            self._display_cursor_row + delta, 0, len(source) - 1
        )
        self._data_cursor_row = source[self._display_cursor_row][0]

    @property
    def filter_untagged_rows(self) -> bool:
        return self._filter_untagged_rows

    @filter_untagged_rows.setter
    def filter_untagged_rows(self, enable: bool):
        self._filter_untagged_rows = enable
        if enable:
            i = 0
            num_rows = len(self._filtered_source)
            while i < num_rows and self._filtered_source[i][0] != self._data_cursor_row:
                i += 1
            self._display_cursor_row = clamp(i, 0, num_rows - 1)
        else:
            self._display_cursor_row = self._data_cursor_row

    @property
    def show_instruction_ancestors(self):
        return self._ancestors_row >= 0

    @show_instruction_ancestors.setter
    def show_instruction_ancestors(self, enable: bool):
        if not enable:
            self._ancestors_row = -1
        else:
            self._ancestors_row = self._data_cursor_row
            self._highlights, self._highlighted_inputs = _find_ancestors(
                self._source[: self._data_cursor_row + 1]
            )
            self._update_filter()

    def toggle_output_display(self):
        self._show_outputs = not self._show_outputs

    def toggle_instruction_ancestors(self):
        """Toggles highlighting of instructions that mutate the arguments of the current instruction."""
        if self._ancestors_row == self._data_cursor_row:
            self.show_instruction_ancestors = False
            return
        self.show_instruction_ancestors = True

    @staticmethod
    def build_output_line(outs):
        elements = [("Result: ", "bold")]
        prefix = ""
        for key in sorted(outs.keys()):
            elements.append(f"{prefix}{key}: ")
            prefix = "; "

            val_prefix = ""
            vals, modified = outs[key]
            for index, val in enumerate(vals):
                elements.append(val_prefix)
                val_prefix = ", "
                if index in modified:
                    elements.append((f"{val}", "bold underline bright_green"))
                else:
                    elements.append(f"{val}")

        return Text.assemble(*elements)

    def render(self, con: console.Console, root: Layout, target_name: str):
        """Renders this editor instance to the given Console with the given root Layout."""
        render_map = root.render(con, con.options)

        target = root[target_name]
        region = render_map[target].region
        visible_rows = region.height
        visible_columns = region.width

        source_region_name = f"{target.name}#src"
        inputs_region_name = f"{target.name}#inputs"
        outputs_region_name = f"{target.name}#outputs"

        inputs = textwrap.fill(
            ", ".join(sorted(self._active_inputs.keys())), visible_columns
        )
        num_input_lines = inputs.count("\n") + 1

        outs = self._active_outputs
        reg_states = [f"{k}: {outs[k][0]}" for k in sorted(outs.keys())]
        outputs = textwrap.fill("Result: " + "; ".join(reg_states), visible_columns)
        num_output_lines = outputs.count("\n") + 1

        input = Text(inputs)
        input.highlight_words(
            self._highlighted_inputs.keys(), "bold italic bright_blue"
        )

        target.split_column(
            Layout(name=source_region_name),
            Layout(name=inputs_region_name, size=num_input_lines + 1),
            Layout(name=outputs_region_name, size=num_output_lines + 1),
        )

        if not self._active_inputs:
            target[inputs_region_name].visible = False
        else:
            target[inputs_region_name].split_column(
                Layout(Rule(), size=1),
                Layout(input),
            )
            visible_rows -= num_input_lines + 1

        target[outputs_region_name].visible = self._show_outputs
        if self._show_outputs:
            output = self.build_output_line(outs)
            target[outputs_region_name].split_column(
                Layout(Rule(), size=1),
                Layout(output),
            )
            visible_rows -= num_output_lines + 1

        middle_row = visible_rows // 2
        active_source_len = len(self._active_source)
        if self._display_cursor_row < middle_row:
            self._scroll_start = 0
        elif self._display_cursor_row > active_source_len - visible_rows:
            self._scroll_start = max(0, active_source_len - visible_rows)
        else:
            self._scroll_start = self._display_cursor_row - middle_row

        target[source_region_name].split_row(
            Layout(name=f"{source_region_name}#line", size=4),
            Layout(name=f"{source_region_name}#content"),
            # Layout(name=f"{target.name}#scrollbar", size=1),
        )

        @console.group()
        def get_line_numbers():
            for line, _ in self._get_active_source_region(visible_rows):
                yield Text(f"{line:>3}")

        root[f"{target.name}#src#line"].update(get_line_numbers())

        @console.group()
        def get_source():
            for line_num, (source_code, _) in self._get_active_source_region(
                visible_rows
            ):
                ret = Text(f"{self._get_cursor(line_num)}{source_code}")
                self._stylize_line(line_num, ret)
                yield ret

        root[f"{target.name}#src#content"].update(get_source())

    @property
    def _active_inputs(self) -> RegisterDictT:
        return (
            self._highlighted_inputs
            if self._filter_untagged_rows
            else self._used_inputs
        )

    @property
    def _active_outputs(self) -> Dict[str, Tuple[Tuple[float], List[int]]]:
        """Returns a dictionary with the outputs of the active cursor."""
        if not self._source:
            return {}

        _, (_, active_step) = self._source[self._data_cursor_row]
        active_state = self._states[self._data_cursor_row]

        ret = {}

        def process(op):
            for output in op["outputs"]:
                ret[output] = _extract_output(output, active_state)

        mac = active_step.get("mac")
        if mac:
            process(mac)
        ilu = active_step.get("ilu")
        if ilu:
            process(ilu)
        return ret

    @property
    def _active_source(self) -> List[Tuple[int, Tuple[str, dict]]]:
        return self._filtered_source if self._filter_untagged_rows else self._source

    def _get_active_source_region(
        self, visible_rows: int
    ) -> List[Tuple[int, Tuple[str, dict]]]:
        source = self._active_source
        end = min(self._scroll_start + visible_rows, len(source))
        return source[self._scroll_start : end]

    def _get_cursor(self, row: int) -> str:
        elements = []
        if self._ancestors_row == row:
            elements.append("=")
        elif row in self._highlights and self._ancestors_row >= 0:
            elements.append("A" if self._filter_untagged_rows else "a")
        if self._data_cursor_row == row:
            elements.append(">")

        ret = "".join(elements)
        return f"{ret:<3}"

    def _stylize_line(self, line_num: int, line: Text):
        style = set()
        if line_num == self._data_cursor_row:
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

    def __init__(self, shader: simulator.Shader, shader_trace: dict):
        self._shader = shader
        self._console = console.Console()
        self._shader_trace: dict = {}
        self._root = Layout()
        self._editor = _Editor()
        self._active_layout = self._SOURCE if shader_trace else self._MENU

        self._running = False

        self._update()

        self.set_shader_trace(shader_trace)

        self._keymaps = {
            "": self._create_global_keymap(),
            self._MENU: self._create_menu_keymap(),
            self._SOURCE: self._create_source_keymap(),
        }

    def set_shader_trace(self, shader_trace: dict):
        steps = shader_trace["steps"]
        self._editor.set_source(
            [(step["source"], step["instruction"]) for step in steps],
            [step["state"] for step in steps],
        )
        self._update()

    def _create_global_keymap(self):
        def _gen_focus(target):
            self._activate_section(target)
            sshkeyboard.stop_listening()

        return {
            "f1": lambda: _gen_focus(self._MENU),
            "1": lambda: _gen_focus(self._MENU),
            "f2": lambda: _gen_focus(self._SOURCE),
            "2": lambda: _gen_focus(self._SOURCE),
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
            return self._shader.initial_state.get(input)

        self._editor.export(filename, resolve)

    def _create_menu_keymap(self):
        def handle_file():
            pass

        return {
            "f": handle_file,
            "e": self._export,
        }

    def _create_source_keymap(self):
        def navigate(delta: int):
            self._editor.navigate(delta)
            sshkeyboard.stop_listening()

        def toggle_ancestors():
            self._editor.toggle_instruction_ancestors()
            sshkeyboard.stop_listening()

        def toggle_filtering():
            self._editor.filter_untagged_rows = not self._editor.filter_untagged_rows
            sshkeyboard.stop_listening()

        def toggle_output_display():
            self._editor.toggle_output_display()
            sshkeyboard.stop_listening()

        return {
            "up": lambda: navigate(-1),
            "down": lambda: navigate(1),
            "pageup": lambda: navigate(-5),
            "pagedown": lambda: navigate(5),
            "home": lambda: navigate(-1000000000),
            "end": lambda: navigate(1000000000),
            "a": toggle_ancestors,
            "f": toggle_filtering,
            "o": toggle_output_display,
        }

    def _activate_section(self, target):
        self._active_layout = target

        for section in [self._MENU, self._SOURCE]:

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
        )

        self._root[self._MENU].split_row(
            Layout(name=f"{self._MENU}#active", size=1),
            Layout(name=f"{self._MENU}#content"),
        )

        self._root[self._SOURCE].split_row(
            Layout(name=f"{self._SOURCE}#active", size=1),
            Layout(name=f"{self._SOURCE}#content"),
        )

        self._update_menu()
        self._update_source()
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

    def _update_source(self):
        self._editor.render(self._console, self._root, f"{self._SOURCE}#content")

    def render(self):
        """Draws the application to the console."""
        rich.print(self._root)

    def _handle_key(self, key):
        if key == "esc" or key == "q":
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

    shader.merge_initial_state({"input": inputs})


def _merge_constants(rows: Iterable, shader: simulator.Shader):
    registers = []
    for row in rows:
        name = row.get("Name", "")
        match = _CONSTANT_NAME_RE.match(name)
        if not match:
            continue
        register = [f"c{match.group(1)}"]

        values = row.get("Value")
        if not values:
            raise Exception(f"Invalid constant entry {row}")

        for value in values.split(", "):
            register.append(float(value))
        registers.append(register)

    if registers:
        shader.merge_initial_state({"constant": registers})


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

    shader_trace = {}
    if args.source:
        if not os.path.isfile(args.source):
            print(f"Failed to open source file '{args.source}'", file=sys.stderr)
            return 1

        with open(args.source, encoding="utf-8") as infile:
            source = infile.read()
        errors = shader.set_source(source)
        if errors:
            print(f"Assembly failed due to errors in {args.source}:", file=sys.stderr)
            for message in errors:
                print(f"{args.source}:{message}", file=sys.stderr)
            return 2
        shader_trace = shader.explain()

    if args.json:
        json.dump(shader_trace, sys.stdout, indent=2, sort_keys=True)
        return 0

    app = _App(shader, shader_trace)
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
