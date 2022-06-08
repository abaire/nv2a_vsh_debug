"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

import copy
import functools
import math
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
    "oT0",
    "oT1",
    "oT2",
    "oT3",
]

_OUTPUT_TO_INDEX = {
    "oPos": 0,
    "oD0": 1,
    "oD1": 2,
    "oFog": 3,
    "oPts": 4,
    "oB0": 5,
    "oB1": 6,
    "oT0": 7,
    "oT1": 8,
    "oT2": 9,
    "oT3": 10,
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

    def get(self, mask: str) -> List[float]:
        ret = []
        for field in mask:
            if field == "x":
                ret.append(self.x)
            elif field == "y":
                ret.append(self.y)
            elif field == "z":
                ret.append(self.z)
            elif field == "w":
                ret.append(self.w)
            else:
                raise Exception(f"Invalid mask component {field}")
        return ret

    def set(self, mask: str, value: Tuple[float, float, float, float]):
        for field in mask:
            if field == "x":
                self.x = value[0]
            elif field == "y":
                self.y = value[1]
            elif field == "z":
                self.z = value[2]
            elif field == "w":
                self.w = value[3]
            else:
                raise Exception(f"Invalid mask component {field}")

    def __str__(self):
        return f"{self.name}[{self.x:f},{self.y:f},{self.z:f},{self.w:f}]"


class Context:
    """Holds the current register context."""

    def __init__(self):
        self._temp_registers = []
        for i in range(12):
            self._temp_registers.append(Register(f"R{i}"))

        self._input_registers = []
        for i in range(16):
            self._input_registers.append(Register(f"v{i}"))

        self._address_register = Register(f"A0")

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
        for k, target in [
            ("input", self._input_registers),
            ("constant", self._constant_registers),
            ("temp", self._temp_registers),
        ]:
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

    def _reg_by_name(self, name: str) -> Register:
        name = name.replace("[", "").replace("]", "")
        if name == "R12":
            name = "oPos"
        for reg in self._flat_registers:
            if reg.name == name:
                return reg
        raise Exception(f"Unknown register {name}")

    def _get_reg_and_mask(
        self, masked_reg: str, extend: bool = False
    ) -> Tuple[Register, str]:
        vals = masked_reg.split(".")
        reg = self._reg_by_name(vals[0])
        if len(vals) == 1:
            return reg, "xyzw"

        mask = vals[1]
        if extend:
            while len(mask) < 4:
                mask += mask[-1]
        return reg, mask

    def set(self, target: str, value: Tuple[float, float, float, float]):
        reg, mask = self._get_reg_and_mask(target)
        reg.set(mask, value)

    def get(self, source: str) -> Tuple[float, float, float, float]:
        negate = False
        if source[0] == "-":
            negate = True
            source = source[1:]
        reg, mask = self._get_reg_and_mask(source, True)

        ret = reg.get(mask)
        if negate:
            ret = [-1 * val for val in ret]
        return ret[0], ret[1], ret[2], ret[3]


def _arl(inst: dict, input: Context, output: Context):
    # TODO: Validate this behavior on HW.
    val = input.get(inst["inputs"][0])[0]
    val = int(math.floor(val + 0.001))
    output.set(inst["output"], (val, val, val, val))


def _mov(inst: dict, input: Context, output: Context):
    for reg in inst["outputs"]:
        output.set(reg, input.get(inst["inputs"][0]))


def _mac_mul(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val * b_val for a_val, b_val in zip(a, b)]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_add(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val + b_val for a_val, b_val in zip(a, b)]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_mad(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val * b_val for a_val, b_val in zip(a, b)]
    c = input.get(inst["inputs"][2])
    result = [a_val + b_val for a_val, b_val in zip(result, c)]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_dp3(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val * b_val for a_val, b_val in zip(a[:3], b[:3])]

    val = functools.reduce(lambda x, y: x + y, result)
    result = [val] * 4
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_dph(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val * b_val for a_val, b_val in zip(a[:3], b[:3])]

    val = functools.reduce(lambda x, y: x + y, result)
    val += b[4]
    result = [val] * 4
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_dp4(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val * b_val for a_val, b_val in zip(a[:4], b[:4])]

    val = functools.reduce(lambda x, y: x + y, result)
    result = [val] * 4
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_dst(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = (1.0, a[1] * b[1], a[2], b[3])
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_min(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val if a_val < b_val else b_val for a_val, b_val in zip(a[:4], b[:4])]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_max(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [a_val if a_val >= b_val else b_val for a_val, b_val in zip(a[:4], b[:4])]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_slt(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [1.0 if a_val < b_val else 0.0 for a_val, b_val in zip(a[:4], b[:4])]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


def _mac_sge(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    b = input.get(inst["inputs"][1])
    result = [1.0 if a_val >= b_val else 0.0 for a_val, b_val in zip(a[:4], b[:4])]
    for reg in inst["outputs"]:
        output.set(reg, tuple(result))


_MAC_HANDLERS = {
    nv2avsh.vsh_instruction.MAC.MAC_MOV: _mov,
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
    nv2avsh.vsh_instruction.MAC.MAC_ARL: _arl,
}


def _ilu_rcp(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])

    def compute(val):
        if val == 1.0:
            return 1.0

        if val == 0.0:
            return math.inf

        return 1.0 / val

    result = [compute(val) for val in a[:4]]
    for reg in inst["outputs"]:
        output.set(reg, (result[0], result[1], result[2], result[3]))


def _ilu_rcc(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])

    def compute(input):
        if input < -1.84467e19:
            input = -1.84467e19
        elif input > -5.42101e-20 and input < 0:
            input = -5.42101e-020
        elif input >= 0 and input < 5.42101e-20:
            input = 5.42101e-20
        elif input > 1.84467e19:
            input = 1.84467e19

        if input == 1.0:
            return 1.0

        return 1.0 / input

    result = [compute(val) for val in a[:4]]
    for reg in inst["outputs"]:
        output.set(reg, (result[0], result[1], result[2], result[3]))


def _ilu_rsq(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])

    def compute(input):
        if input == 1.0:
            return 1.0

        if input == 0:
            return math.inf

        return 1.0 / math.sqrt(input)

    result = [compute(abs(val)) for val in a[:4]]
    for reg in inst["outputs"]:
        output.set(reg, (result[0], result[1], result[2], result[3]))


def _ilu_exp(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])

    tmp = math.floor(a[0])
    x = math.pow(2, tmp)
    y = a[0] - tmp
    z = math.pow(2, a[0])
    w = 1.0

    for reg in inst["outputs"]:
        output.set(reg, (x, y, z, w))


def _ilu_log(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])

    tmp = math.floor(a[0])
    if tmp == 0.0:
        x = -math.inf
        y = 1.0
        z = -math.inf
        w = 1.0
    else:
        x = math.floor(math.log2(tmp))
        y = tmp / math.pow(2, math.floor(math.log2(tmp)))
        z = math.log2(tmp)
        w = 1.0

    for reg in inst["outputs"]:
        output.set(reg, (x, y, z, w))


def _clamp(val, min_val, max_val):
    return max(min(val, max_val), min_val)


def _ilu_lit(inst: dict, input: Context, output: Context):
    a = input.get(inst["inputs"][0])
    epsilon = 1.0 / 256.0

    sx = max(a[0], 0.0)
    sy = max(a[1], 0.0)
    sw = _clamp(a[3], -(128 - epsilon), 128 - epsilon)

    x = 1.0
    y = sx
    z = 0.0
    if sx > 0:
        z = math.pow(2, sw * math.log2(sy))
    w = 1.0

    output.set(inst["output"], (x, y, z, w))


_ILU_HANDLERS = {
    nv2avsh.vsh_instruction.ILU.ILU_MOV: _mov,
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

    def set_source(self, source_code: str) -> List[str]:
        """Sets the source code for this shader."""
        machine_code, errors = nv2avsh.assemble.assemble(source_code)
        if errors:
            return [f"{error.line}:{error.column}: {error.message}" for error in errors]

        self._instructions = nv2avsh.disassemble.disassemble_to_instructions(
            machine_code
        )
        self._reformatted_source = nv2avsh.disassemble.disassemble(machine_code, False)
        return []

    def set_initial_state(self, state: dict):
        """Sets the initial register state for this shader."""
        ctx = Context()
        ctx.from_dict(state)
        self._input_context = ctx

    def merge_initial_state(self, state: dict):
        """Merges values from the given dictionary into the current initial context."""
        self._input_context.from_dict(state)

    @property
    def initial_state(self) -> Context:
        return self._input_context

    def _apply(
        self, instruction: nv2avsh.vsh_instruction.VshInstruction, input: Context
    ) -> Tuple[Context, dict]:
        output = input.duplicate()

        commands = instruction.disassemble_to_dict()
        mac = instruction.mac
        if mac:
            _MAC_HANDLERS[mac](commands["mac"], input, output)
        ilu = instruction.ilu
        if ilu:
            _ILU_HANDLERS[ilu](commands["ilu"], input, output)

        return output, commands

    def _simulate(self) -> Tuple[List[Tuple[str, Context, dict]], Context]:
        active_state = self._input_context
        states = []
        for line, instruction in zip(self._reformatted_source, self._instructions):
            active_state, command_dict = self._apply(instruction, active_state)
            states.append((line, active_state, command_dict))

        return states, active_state

    def explain(self) -> dict:
        """Returns a dictionary providing details about the execution state of this shader."""
        ret = {}

        ret["input"] = self._input_context.to_dict()

        steps, output = self._simulate()
        step_dicts = []
        for line, step_output, step_dict in steps:
            entry = {
                "source": line,
                "state": step_output.to_dict(),
                "instruction": step_dict,
            }
            step_dicts.append(entry)
        ret["steps"] = step_dicts
        ret["output"] = output.to_dict()

        return ret
