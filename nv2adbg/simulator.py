"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

from typing import Any, List, Tuple

import nv2avsh

OUTPUT_TO_INDEX = {
    "oPos": 0,
    "oD0": 3,
    "oD1": 4,
    "oFog": 5,
    "oPts": 6,
    "oB0": 7,
    "oB1": 8,
    "oT0": 9,
    "oT1": 10,
    "oT2": 11,
    "oT3": 12,
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
        from nv2adbg.py_nv2a_vsh_emu import Nv2aVshEmuState

        self._state = Nv2aVshEmuState()

    def from_dict(self, registers: dict):
        """Populates this context from the given dictionary of register states."""

        input = registers.get("input", [])
        context = registers.get("constant", [])
        temp = registers.get("temp", [])
        output = registers.get("output", [])
        address = registers.get("address", [])

        self._state.set_state(input, context, temp, output, address)

    def to_dict(self, inputs_only: bool = False):
        """Returns a dictionary representation of this context."""
        return self._state.to_dict(inputs_only)

    def apply(self, step):
        self._state.apply(step)

    # @property
    # def registers(self):
    #     return self._flat_registers
    #
    # @property
    # def input_registers(self):
    #     return self._input_registers
    #
    # @property
    # def constant_registers(self):
    #     return self._constant_registers

    def duplicate(self):
        new = Context()
        new.from_dict(self.to_dict())
        return new

    # def _reg_by_name(self, name: str) -> Register:
    #     name = name.replace("[", "").replace("]", "")
    #     if name == "R12":
    #         name = "oPos"
    #     for reg in self._flat_registers:
    #         if reg.name == name:
    #             return reg
    #     raise Exception(f"Unknown register {name}")
    #
    # def _get_reg_and_mask(
    #     self, masked_reg: str, extend: bool = False
    # ) -> Tuple[Register, str]:
    #     vals = masked_reg.split(".")
    #     reg = self._reg_by_name(vals[0])
    #     if len(vals) == 1:
    #         return reg, "xyzw"
    #
    #     mask = vals[1]
    #     if extend:
    #         while len(mask) < 4:
    #             mask += mask[-1]
    #     return reg, mask
    #
    # def set(self, target: str, value: Tuple[float, float, float, float]):
    #     reg, mask = self._get_reg_and_mask(target)
    #     reg.set(mask, value)
    #
    # def get(self, source: str) -> Tuple[float, float, float, float]:
    #     negate = False
    #     if source[0] == "-":
    #         negate = True
    #         source = source[1:]
    #     reg, mask = self._get_reg_and_mask(source, True)
    #
    #     ret = reg.get(mask)
    #     if negate:
    #         ret = [-1 * val for val in ret]
    #     return ret[0], ret[1], ret[2], ret[3]


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

        from nv2adbg.py_nv2a_vsh_emu import Nv2aVshStep

        self._instructions = [Nv2aVshStep(token) for token in machine_code]
        self._reformatted_source = [ins.source() for ins in self._instructions]
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

    def _apply(self, instruction, input: Context) -> Context:
        output = input.duplicate()
        output.apply(instruction)
        return output

    def _simulate(self) -> Tuple[List[Tuple[str, Context, Any]], Context]:
        active_state = self._input_context
        states = []
        for line, instruction in zip(self._reformatted_source, self._instructions):
            active_state = self._apply(instruction, active_state)
            states.append((line, active_state, instruction))

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
