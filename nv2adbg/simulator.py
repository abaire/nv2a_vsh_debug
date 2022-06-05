"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

import copy

import nv2avsh

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

_OUTPUT_TO_INDEX = {
    "oPos": 0,
    "oD0": 1,
    "oD1": 2,
    "oFog": 3,
    "oPts": 4,
    "oB0": 5,
    "oB1": 6,
    "oTex0": 7,
    "oTex1": 8,
    "oTex2": 9,
    "oTex3": 10,
}

class Register:
    """Holds the state of a single nv2a register."""
    def __init__(self, name: str, x=0, y=0, z=0, w=0):
        self.name = name
        self.x = x
        self.y = y
        self.z = z
        self.w = w


class Context:
    """Holds the current register context."""
    def __init__(self):
        self._temp_registers = []
        for i in range(12):
            self._temp_registers.append(Register(f"r{i}"))

        self._input_registers = []
        for i in range(16):
            self._input_registers.append(Register(f"v{i}"))

        self._address_register = Register(f"a0")

        self._constant_registers = []
        for i in range(192):
            self._constant_registers.append(Register(f"c{i}"))

        self._output_registers = []
        for name in _OUTPUTS:
            self._output_registers.append(Register(name))

        self._flat_registers = []
        self._flat_registers.extend(self._output_registers)
        self._flat_registers.extend(self._temp_registers)
        self._flat_registers.extend(self._input_registers)
        self._flat_registers.append(self._address_register)
        self._flat_registers.extend(self._constant_registers)

    def from_dict(self, registers: dict):
        """Populates this context from the given dictionary of register states."""
        for k, target in [("input", self._input_registers), ("constant", self._constant_registers), ("temp", self._temp_registers)]:
            values = registers.get(k)
            if not values:
                continue

            for name, x, y, z, w in values:
                index = int(name[1:])
                target[index].x = x
                target[index].y = y
                target[index].z = z
                target[index].w = w

        values = registers.get("address")
        if values:
            self._address_register.x = values[1]
            self._address_register.y = values[2]
            self._address_register.z = values[3]
            self._address_register.w = values[4]

        values = registers.get("output")
        if values:
            for name, x, y, z, w in values:
                index = _OUTPUT_TO_INDEX[name]
                self._output_registers[index].x = x
                self._output_registers[index].y = y
                self._output_registers[index].z = z
                self._output_registers[index].w = w

    def to_dict(self, inputs_only: bool = False):
        """Returns a dictionary representation of this context."""
        ret = {
            "input": self._input_registers,
            "constant": self._constant_registers,
        }

        if not inputs_only:
            ret["address"] = self._address_register
            ret["temp"] = self._temp_registers
            ret["output"] = self._output_registers

        return ret

    @property
    def registers(self):
        return self._flat_registers

    @property
    def input_registers(self):
        return self._input_registers

    @property
    def constant_registers(self):
        return self._constant_registers

    def duplicate(self):
        return copy.deepcopy(self)

class Shader:
    def __init__(self):
        self._reformatted_source = []
        self._instructions = []
        self._contexts = []

    def set_source(self, source_code: str):
        """Sets the source code for this shader."""
        machine_code = nv2avsh.assemble.assemble(source_code)
        self._instructions = nv2avsh.disassemble.disassemble_to_instructions(machine_code)
        self._reformatted_source = nv2avsh.disassemble.disassemble(machine_code, False)

    def set_initial_state(self, state: dict):
        """Sets the initial register state for this shader."""
        ctx = Context()
        ctx.from_dict(state)
        if not self._contexts:
            self._contexts = [ctx]
            return
        self._contexts[0] = ctx

    def explain(self) -> dict:
        """Returns a dictionary providing details about the execution state of this shader."""
        return {}
