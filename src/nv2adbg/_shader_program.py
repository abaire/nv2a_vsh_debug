"""Internal model of an nv2a shader program."""

import csv
import json
import re
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional

from nv2adbg import simulator

# c[123]
_CONSTANT_NAME_RE = re.compile(r"c\[(\d+)]")


class _ShaderProgram:
    """Models an nv2a shader program."""

    def __init__(
        self,
        source_file: str,
        inputs_json_file: Optional[str],
        renderdoc_mesh_csv: Optional[str],
        renderdoc_constants_csv: Optional[str],
    ):
        """Initializes this _ShaderProgram.

        Arguments:
            source_file: Path to a file containing the vertex shader source.
            inputs_json_file: Optional path to a JSON formatted file containing the initial state of the shader.
            renderdoc_mesh_csv: Optional path to a CSV file containing mesh vertices as exported from RenderDoc.
            renderdoc_constants_csv: Optional path to a CSV file containing the constant register values as exported
                                     from RenderDoc.
        """
        self._shader = None
        self._shader_trace = None

        self._vertex_inputs: List[Dict] = []
        self._active_vertex: Optional[Dict] = None

        self.inputs_file = inputs_json_file
        self.mesh_inputs_file = renderdoc_mesh_csv
        self.constants_file = renderdoc_constants_csv
        self.source_file = source_file

        self.build_shader()

    @property
    def loaded(self) -> bool:
        return bool(self._source_file)

    @property
    def shader(self) -> simulator.Shader:
        return self._shader

    @property
    def shader_trace(self) -> simulator.Trace:
        return self._shader_trace

    @property
    def source_file(self) -> str:
        return self._source_file

    @source_file.setter
    def source_file(self, val: str):
        self._source_file = val
        if val:
            with open(val, encoding="utf-8") as infile:
                self._source_code = infile.read()
        else:
            self._source_code = ""

    @property
    def inputs_file(self) -> str:
        return self._inputs_json_file

    @inputs_file.setter
    def inputs_file(self, val: str):
        self._inputs_json_file = val
        if val:
            with open(val, encoding="ascii") as infile:
                self._inputs = json.load(infile)
        else:
            self._inputs = {}

    @property
    def mesh_inputs_file(self) -> str:
        return self._renderdoc_mesh_csv

    @mesh_inputs_file.setter
    def mesh_inputs_file(self, val: str):
        self._renderdoc_mesh_csv = val
        self._vertex_inputs.clear()
        self._active_vertex = None
        if val:
            with open(val, newline="", encoding="ascii") as csvfile:
                for row in csv.DictReader(csvfile):
                    if not row:
                        break
                    row = {key.strip(): val.strip() for key, val in row.items()}
                    self._vertex_inputs.append(row)
            if self._vertex_inputs:
                self._active_vertex = self._vertex_inputs[0]

    @property
    def vertex_inputs(self):
        return self._vertex_inputs

    def get_deduped_ordered_vertices(self) -> List[Dict]:
        deduped_vertices = {}
        for vertex in self._vertex_inputs:
            deduped_vertices[int(vertex["IDX"])] = vertex

        return [deduped_vertices[idx] for idx in sorted(deduped_vertices.keys())]

    @property
    def constants_file(self) -> str:
        return self._renderdoc_constants_csv

    @constants_file.setter
    def constants_file(self, val: str):
        self._renderdoc_constants_csv = val
        if val:
            with open(val, newline="", encoding="ascii") as csvfile:
                self._constants = list(csv.DictReader(csvfile))
        else:
            self._constants = []

    def set_active_vertex_index(self, index: int) -> bool:
        """Selects a new vertex to use as inputs. Returns True if the shader was rebuilt as a result."""
        return self.set_active_vertex(self._vertex_inputs[index])

    def set_active_vertex(self, vertex: Dict) -> bool:
        """Selects a new vertex to use as inputs. Returns True if the shader was rebuilt as a result."""
        if vertex == self._active_vertex:
            return False

        self._active_vertex = vertex
        self.build_shader()
        return True

    def build_shader(self):
        self._shader = simulator.Shader()
        self._shader.set_initial_state(self._inputs)

        _merge_inputs(self._active_vertex, self._shader)

        if self._constants:
            _merge_constants(self._constants, self._shader)

        errors = self._shader.set_source(self._source_code)
        if errors:
            error_messsage = [f"Assembly failed due to errors in {self._source_code}:"]
            error_messsage.extend(errors)
            raise Exception("\n".join(error_messsage))

        self._shader_trace = self._shader.explain()


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
    """Loads constants into the given shader."""
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
