#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

import argparse
import json
import logging
import os
import sys
from typing import Optional

from textual.app import App
from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Footer
from textual.widgets import Header
from textual.widgets import Label
from textual.widgets import TabbedContent
from textual.widgets import TabPane

from nv2adbg import simulator
from nv2adbg._editor import _Editor
from nv2adbg._file_menu import _FileMenu
from nv2adbg._program_inputs_viewer import _ProgramInputsViewer
from nv2adbg._program_outputs_viewer import _ProgramOutputsViewer
from nv2adbg._shader_program import _ShaderProgram


class _NoTraceErrorScreen(ModalScreen):
    """Screen used to display message when there is no trace."""

    DEFAULT_CSS = """
    _NoTraceErrorScreen {
        align: center middle;
    }

    #dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        min-width: 60;
        min-height: 11;
        border: thick $background 80%;
        background: $surface;
    }

    #message {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
    }
    """

    BINDINGS = [
        ("f1", "app.open_file", "File menu"),
        ("f10", "app.toggle_dark", "Toggle dark mode"),
        ("escape,q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(
            Label(
                "No trace available, load a source file via the File menu.",
                id="message",
            ),
            id="dialog",
        )
        yield Footer()


class _App(App):
    """Main application."""

    TITLE = "nv2a Debugger"
    BINDINGS = [
        ("f1", "open_file", "File menu"),
        ("f10", "app.toggle_dark", "Toggle dark mode"),
        ("escape,q", "app.quit", "Quit"),
    ]

    CSS = """
    /* Workaround for Textualize#2408 */
    TabbedContent ContentSwitcher {
        height: 1fr;
    }
    """

    def __init__(self, program: _ShaderProgram):
        super().__init__()
        self._program = program
        self._editor = _Editor()
        self._program_inputs = _ProgramInputsViewer()
        self._program_outputs = _ProgramOutputsViewer()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with TabbedContent():
            with TabPane("Editor"):
                yield self._editor
            with TabPane("Inputs"):
                yield self._program_inputs
            with TabPane("Outputs"):
                yield self._program_outputs
        yield Footer()

    def action_open_file(self) -> None:
        def on_accept(
            source_file: str,
            inputs_file: str,
            mesh_inputs_file: str,
            constants_file: str,
        ):
            self._program.source_file = source_file
            self._program.inputs_file = inputs_file
            self._program.mesh_inputs_file = mesh_inputs_file
            self._program.constants_file = constants_file
            self.pop_screen()
            self._load_program()

        def on_cancel():
            self.pop_screen()

        self.push_screen(
            _FileMenu(
                on_accept,
                on_cancel,
                self._program.source_file,
                self._program.inputs_file,
                self._program.mesh_inputs_file,
                self._program.constants_file,
            )
        )

    def on_mount(self) -> None:
        self._load_program()

    def _load_program(self):
        if not self._program.loaded:
            self.sub_title = ""
            if not isinstance(self.screen, _NoTraceErrorScreen):
                self.push_screen(_NoTraceErrorScreen(id="notraceerror"))
            return
        if isinstance(self.screen, _NoTraceErrorScreen):
            self.pop_screen()
        self.sub_title = self._program.source_file
        self._program.build_shader()
        self.set_shader_trace(self._program.shader_trace)

    def set_shader_trace(self, shader_trace: simulator.Trace):
        self._editor.set_shader_trace(shader_trace)
        self._program_inputs.set_context(shader_trace.input_context)
        self._program_outputs.set_context(
            shader_trace.input_context, shader_trace.output_context
        )

    # def _export(self):
    #     # TODO: Pop a text input dialog and capture a filename.
    #     filename = ""
    #     for index in range(1000):
    #         filename = f"export{index:04}.vsh"
    #         if not os.path.exists(filename):
    #             break
    #     if os.path.exists(filename):
    #         raise Exception("Failed to find an unused export filename.")
    #
    #     def resolve(input):
    #         return self._program.shader.initial_state.get(input)
    #
    #     self._editor.export(filename, resolve)


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
        json.dump(program.shader_trace.to_dict(), sys.stdout, indent=2, sort_keys=True)
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
