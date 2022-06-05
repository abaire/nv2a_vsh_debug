"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

import copy
from typing import List, Tuple

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

    def to_json(self) -> List:
        return [self.name, self.x, self.y, self.z, self.w]


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
            "input": [x.to_json() for x in self._input_registers],
            "constant": [x.to_json() for x in self._constant_registers],
        }

        if not inputs_only:
            ret["address"] = self._address_register.to_json()
            ret["temp"] = [x.to_json() for x in self._temp_registers]
            ret["output"] = [x.to_json() for x in self._output_registers]

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

def _mac_mov(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_mul(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_add(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_mad(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_dp3(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_dph(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_dp4(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_dst(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_min(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_max(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_slt(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_sge(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _mac_arl(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


_MAC_HANDLERS = {
    nv2avsh.vsh_instruction.MAC.MAC_MOV: _mac_mov,
    nv2avsh.vsh_instruction.MAC.MAC_MUL: _mac_mul,
    nv2avsh.vsh_instruction.MAC.MAC_ADD: _mac_add,
    nv2avsh.vsh_instruction.MAC.MAC_MAD: _mac_mad,
    nv2avsh.vsh_instruction.MAC.MAC_DP3: _mac_dp3,
    nv2avsh.vsh_instruction.MAC.MAC_DPH: _mac_dph,
    nv2avsh.vsh_instruction.MAC.MAC_DP4: _mac_dp4,
    nv2avsh.vsh_instruction.MAC.MAC_DST: _mac_dst,
    nv2avsh.vsh_instruction.MAC.MAC_MIN: _mac_min,
    nv2avsh.vsh_instruction.MAC.MAC_MAX: _mac_max,
    nv2avsh.vsh_instruction.MAC.MAC_SLT: _mac_slt,
    nv2avsh.vsh_instruction.MAC.MAC_SGE: _mac_sge,
    nv2avsh.vsh_instruction.MAC.MAC_ARL: _mac_arl,
}


def _ilu_mov(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_rcp(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_rcc(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_rsq(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_exp(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_log(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


def _ilu_lit(instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context, output: Context):
    pass


_ILU_HANDLERS = {
    nv2avsh.vsh_instruction.ILU.ILU_MOV: _ilu_mov,
    nv2avsh.vsh_instruction.ILU.ILU_RCP: _ilu_rcp,
    nv2avsh.vsh_instruction.ILU.ILU_RCC: _ilu_rcc,
    nv2avsh.vsh_instruction.ILU.ILU_RSQ: _ilu_rsq,
    nv2avsh.vsh_instruction.ILU.ILU_EXP: _ilu_exp,
    nv2avsh.vsh_instruction.ILU.ILU_LOG: _ilu_log,
    nv2avsh.vsh_instruction.ILU.ILU_LIT: _ilu_lit,
}


class Shader:
    """Models an nv2a vertex shader."""
    def __init__(self):
        self._reformatted_source = []
        self._instructions = []
        self._input_context = Context()

    def set_source(self, source_code: str):
        """Sets the source code for this shader."""
        machine_code = nv2avsh.assemble.assemble(source_code)
        self._instructions = nv2avsh.disassemble.disassemble_to_instructions(machine_code)
        self._reformatted_source = nv2avsh.disassemble.disassemble(machine_code, False)

    def set_initial_state(self, state: dict):
        """Sets the initial register state for this shader."""
        ctx = Context()
        ctx.from_dict(state)
        self._input_context = ctx

    def _apply(self, instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context):
        output = input.duplicate()

        mac = instruction.mac
        if mac:
            _MAC_HANDLERS[mac](instruction, input, output)
        ilu = instruction.ilu
        if ilu:
            _ILU_HANDLERS[ilu](instruction, input, output)

        return output

    def _simulate(self) -> Tuple[List[Tuple[str, Context]], Context]:
        active_state = self._input_context
        states = []
        for line, instruction in zip(self._reformatted_source, self._instructions):
            active_state = self._apply(instruction, active_state)
            states.append((line, active_state))

        return states, active_state

    def explain(self) -> dict:
        """Returns a dictionary providing details about the execution state of this shader."""
        ret = {}

        ret["input"] = self._input_context.to_dict()

        steps, output = self._simulate()
        step_dicts = []
        for line, output in steps:
            entry = {
                "source": line,
                "state": output.to_dict()
            }
            step_dicts.append(entry)
        ret["steps"] = step_dicts
        ret["output"] = output.to_dict()

        return ret
