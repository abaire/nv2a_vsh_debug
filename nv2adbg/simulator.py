"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

import collections
import copy

import nv2avsh

Register = collections.namedtuple("Register", ["name", "x", "y", "z", "w"])

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

class Context:
    """Holds the current register context."""
    def __init__(self):
        self._temp_registers = []
        for i in range(12):
            self._temp_registers.append(Register(f"r{i}", 0, 0, 0, 1))

        self._input_registers = []
        for i in range(16):
            self._input_registers.append(Register(f"v{i}", 0, 0, 0, 0))

        self._address_register = Register(f"a0", 0, 0, 0, 0)

        self._constant_registers = []
        for i in range(192):
            self._constant_registers.append(Register(f"c{i}", 0, 0, 0, 0))

        self._output_registers = []
        for name in _OUTPUTS:
            self._output_registers.append(Register(name, 0, 0, 0, 0))

        self._flat_registers = []
        self._flat_registers.extend(self._output_registers)
        self._flat_registers.extend(self._temp_registers)
        self._flat_registers.extend(self._input_registers)
        self._flat_registers.append(self._address_register)
        self._flat_registers.extend(self._constant_registers)

    @property
    def registers(self):
        return self._flat_registers

    def duplicate(self):
        return copy.deepcopy(self)

class Shader:
    def __init__(self):
        self._source = []
        self._contexts = []

    def process(self, source_code):
        self._source = source_code.split("\n")
        asm = nv2avsh.nv2a_vsh_asm.Assembler(source_code)
        asm.assemble()
