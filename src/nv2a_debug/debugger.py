#!/usr/bin/env python3

"""Assembles nv2a vertex shader machine code."""

# ruff: noqa: T201 `print` found
# ruff: noqa: RUF012 Mutable class attributes should be annotated with `typing.ClassVar`

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import ContentSwitcher, Footer, Header, TabbedContent, TabPane

from nv2a_debug import simulator
from nv2a_debug._editor import _Editor
from nv2a_debug._error_message import _CenteredErrorMessage
from nv2a_debug._file_menu import _FileMenu
from nv2a_debug._program_inputs_viewer import _ProgramInputsViewer
from nv2a_debug._program_outputs_viewer import _ProgramOutputsViewer
from nv2a_debug._program_vertex_viewer import _ProgramVertexViewer
from nv2a_debug._shader_program import _ShaderProgram


class _AppScreen(Screen):
    BINDINGS = [
        ("f1", "open_file", "Open file"),
        ("f5", "reload_files", "Reload files"),
        ("f10", "app.toggle_dark", "Toggle dark mode"),
        ("escape,q", "app.quit", "Quit"),
    ]

    def __init__(self, program: _ShaderProgram):
        super().__init__()
        self._program = program
        self._editor: _Editor = _Editor()
        self._program_inputs = _ProgramInputsViewer()
        self._program_outputs = _ProgramOutputsViewer()
        self._program_vertices = _ProgramVertexViewer()
        self._editor_content_switcher = ContentSwitcher()

    def on_mount(self) -> None:
        self._load_program()
        self._editor_content_switcher.current = self._active_content

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()

        with self._editor_content_switcher:
            yield _CenteredErrorMessage(
                "No trace available, load a source file via the File menu.",
                id="no-content",
            )

            with TabbedContent(id="content"):
                with TabPane("Editor"):
                    yield self._editor
                with TabPane("Inputs"):
                    yield self._program_inputs
                with TabPane("Outputs"):
                    yield self._program_outputs
                with TabPane("Vertices"):
                    yield self._program_vertices

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
            self._load_program()
            self.app.pop_screen()

        def on_cancel():
            self.app.pop_screen()

        self.app.push_screen(
            _FileMenu(
                on_accept,
                on_cancel,
                self._program.source_file,
                self._program.inputs_file,
                self._program.mesh_inputs_file,
                self._program.constants_file,
            )
        )

    def action_reload_files(self) -> None:
        self._program.reload()
        self._load_program()

    def _load_program(self):
        if not self._program.loaded:
            self.sub_title = ""
            self._active_content = "no-content"
            self._program_vertices.set_program(None)
            return

        self.sub_title = self._program.source_file
        self._program.build_shader()
        self.set_shader_trace(self._program.shader_trace)
        self._active_content = "content"
        self._program_vertices.set_program(self._program)

    def set_shader_trace(self, shader_trace: simulator.Trace):
        self._editor.set_shader_trace(shader_trace)
        self._program_inputs.set_context(shader_trace.input_context)
        self._program_outputs.set_context(shader_trace.input_context, shader_trace.output_context)

    def _watch__active_content(self, _old_val: str, new_val: str):
        del _old_val
        self._editor_content_switcher.current = new_val

    def _on__program_vertex_viewer_active_vertex_changed(self, event: _ProgramVertexViewer.ActiveVertexChanged):
        del event
        self.set_shader_trace(self._program.shader_trace)


class _App(App):
    """Main application."""

    TITLE = "nv2a Debugger"

    CSS = """
    /* Workaround for Textualize#2408 */
    TabbedContent ContentSwitcher {
        height: 1fr;
    }
    """

    _active_content = reactive("no-content", init=False)

    def __init__(self, program: _ShaderProgram):
        super().__init__()
        self._program = program
        self._app_screen: _AppScreen

    def on_mount(self) -> None:
        self._app_screen = _AppScreen(self._program)
        self.push_screen(self._app_screen)


def _emit_input_template():
    ctx = simulator.Context()
    values = ctx.to_dict(inputs_only=True)
    json.dump(values, sys.stdout, indent=2, sort_keys=True)


def _main(args):
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if args.emit_inputs:
        _emit_input_template()
        return 0

    inputs = os.path.abspath(os.path.expanduser(args.inputs)) if args.inputs else None
    if inputs and not os.path.isfile(inputs):
        print(f"Failed to open input definition file '{inputs}'", file=sys.stderr)
        return 1

    renderdoc_mesh = os.path.abspath(os.path.expanduser(args.renderdoc_mesh)) if args.renderdoc_mesh else None
    if renderdoc_mesh and not os.path.isfile(renderdoc_mesh):
        print(
            f"Failed to open RenderDoc input definition file '{args.renderdoc_mesh}'",
            file=sys.stderr,
        )
        return 1

    renderdoc_constants = (
        os.path.abspath(os.path.expanduser(args.renderdoc_constants)) if args.renderdoc_constants else None
    )
    if renderdoc_constants and not os.path.isfile(renderdoc_constants):
        print(
            f"Failed to open RenderDoc constant definition file '{args.renderdoc_constants}'",
            file=sys.stderr,
        )
        return 1

    source = os.path.abspath(os.path.expanduser(args.source)) if args.source else None
    if source and not os.path.isfile(source):
        print(f"Failed to open source file '{args.source}'", file=sys.stderr)
        return 1

    program = _ShaderProgram(source, inputs, renderdoc_mesh, renderdoc_constants)

    if args.json:
        json.dump(program.shader_trace.to_dict(), sys.stdout, indent=2, sort_keys=True)
        return 0

    if args.simulate:
        _dump_all_results(program)
        return 0

    app = _App(program)
    app.run()

    return 0


def _dump_all_results(program: _ShaderProgram) -> None:
    all_results = []
    ordered_vertices = program.get_deduped_ordered_vertices()
    print(
        f"Simulating {len(ordered_vertices)} runs, this may take some time...",
        file=sys.stderr,
    )

    for vertex in ordered_vertices:
        program.set_active_vertex(vertex)
        result = {
            "vertex": vertex,
            "input": program.shader_trace.inputs,
            "output": program.shader_trace.output,
        }
        all_results.append(result)

    json.dump(all_results, sys.stdout, indent=2, sort_keys=True)


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
            help="Emit a JSON document capturing the context at each instruction in the source. Requires <source>.",
        )

        parser.add_argument(
            "-v",
            "--verbose",
            help="Enables verbose logging information",
            action="store_true",
        )

        parser.add_argument(
            "-s",
            "--simulate",
            action="store_true",
            help="Emit a JSON document capturing the end results for each vertex in the mesh. Requires <source>.",
        )

        return parser.parse_args()

    sys.exit(_main(_parse_args()))


if __name__ == "__main__":
    entrypoint()
